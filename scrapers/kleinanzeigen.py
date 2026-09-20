import asyncio
import logging
import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class KleinanzeigenScraper(BaseScraper):
    """Scraper per Kleinanzeigen (Germania), il più grande marketplace di annunci e usato dell'Europa centrale."""

    def __init__(self):
        super().__init__(name="kleinanzeigen")
        self.base_url = "https://www.kleinanzeigen.de"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,it;q=0.7",
        }

    def _search_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        # Formato URL Kleinanzeigen: /s-termine-ricerca/k0
        clean_q = re.sub(r'[^a-zA-Z0-9\s-]', '', query).strip()
        slug_q = re.sub(r'\s+', '-', clean_q).lower()
        url = f"{self.base_url}/s-{slug_q}/k0"

        results: List[DealItem] = []
        try:
            resp = requests.get(url, headers=self.headers, impersonate="chrome124", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[Kleinanzeigen] Risposta HTTP anomala: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.find_all("article")

            for a in articles:
                if len(results) >= max_results:
                    break

                h3 = a.find("h3")
                if not h3:
                    continue

                title = h3.text.strip()
                # Salta annunci di tipo '!SUCHE!' (richieste di acquisto, non vendite)
                if title.startswith("!SUCHE!") or "suche" in title.lower()[:8]:
                    continue

                link_el = a.find("a", href=re.compile(r"/s-anzeige/"))
                if not link_el:
                    continue

                href = link_el.get("href", "")
                m_id = re.search(r"/(\d+)-", href)
                item_id = m_id.group(1) if m_id else str(hash(href))

                # Estrazione prezzo
                price_val = 0.0
                for p_el in a.find_all(["p", "span", "div"]):
                    txt = p_el.text.strip()
                    m_price = re.search(r'([\d\.,]+)\s*€', txt)
                    if m_price:
                        p_str = m_price.group(1).replace(".", "").replace(",", ".")
                        try:
                            price_val = float(p_str)
                            break
                        except ValueError:
                            pass

                if price_val <= 0.0:
                    continue

                img = a.find("img")
                image_url = img.get("src") if img else None

                # Spedizione standard da Germania verso Italia ~9.90€
                shipping_val = 9.90
                total_val = round(price_val + shipping_val, 2)
                item_url = f"{self.base_url}{href}" if href.startswith("/") else href

                deal = DealItem(
                    id=f"kleinanzeigen_{item_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=total_val,
                    url=item_url,
                    image_url=image_url,
                    source="kleinanzeigen",
                    description=title,
                    location="Germania (Kleinanzeigen)",
                    is_international=True,
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Kleinanzeigen] Errore scraping per '{query}': {e}", exc_info=True)

        return results

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        return await asyncio.to_thread(self._search_sync, query, max_results)
