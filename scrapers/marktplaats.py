import asyncio
import logging
import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class MarktplaatsScraper(BaseScraper):
    """Scraper per Marktplaats (Paesi Bassi), il marketplace #1 in Olanda per compravendita tra privati."""

    def __init__(self):
        super().__init__(name="marktplaats")
        self.base_url = "https://www.marktplaats.nl"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "nl-NL,nl;q=0.9,en-US;q=0.8,it;q=0.7",
        }

    def _search_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"{self.base_url}/q/{encoded_query}/"

        results: List[DealItem] = []
        try:
            resp = requests.get(url, headers=self.headers, impersonate="chrome124", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[Marktplaats] Risposta HTTP anomala: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("li", class_=re.compile("hz-Listing--list-item"))

            seen_ids = set()
            for it in items:
                if len(results) >= max_results:
                    break

                link_el = it.find("a", href=re.compile(r"/v/"))
                if not link_el:
                    continue

                href = link_el.get("href", "")
                m_id = re.search(r"/([am]\d+)-", href)
                item_id = m_id.group(1) if m_id else str(hash(href))
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                title_el = it.find(lambda t: t.name in ["span", "h3"] and any("title" in str(c).lower() for c in t.get("class", [])))
                if not title_el:
                    # Fallback al testo dello slug
                    title = href.split("/")[-1].replace("-", " ").title()
                else:
                    title = title_el.text.strip()

                if not title or len(title) < 3:
                    continue

                # Salta annunci di ricerca ("Gezocht")
                if title.lower().startswith("gezocht"):
                    continue

                price_el = it.find(lambda t: any("price" in str(c).lower() for c in t.get("class", [])))
                price_val = 0.0
                if price_el:
                    m_price = re.search(r'([\d\.,]+)', price_el.text)
                    if m_price:
                        try:
                            price_val = float(m_price.group(1).replace(".", "").replace(",", "."))
                        except ValueError:
                            pass

                if price_val <= 0.0:
                    continue

                img_el = it.find("img")
                image_url = img_el.get("src") if img_el else None

                item_url = f"{self.base_url}{href}" if href.startswith("/") else href
                shipping_val = 9.90
                total_val = round(price_val + shipping_val, 2)

                deal = DealItem(
                    id=f"marktplaats_{item_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=total_val,
                    url=item_url,
                    image_url=image_url,
                    source="marktplaats",
                    description=title,
                    location="Paesi Bassi (Marktplaats)",
                    is_international=True,
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Marktplaats] Errore scraping per '{query}': {e}", exc_info=True)

        return results

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        return await asyncio.to_thread(self._search_sync, query, max_results)
