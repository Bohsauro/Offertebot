import asyncio
import logging
import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class RebuyScraper(BaseScraper):
    """Scraper per Rebuy (Germania / Europa), negozio leader di usato ricondizionato garantito."""

    def __init__(self):
        super().__init__(name="rebuy")
        self.base_url = "https://www.rebuy.de"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,it;q=0.7",
        }

    def _search_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"{self.base_url}/kaufen/suchen?q={encoded_query}"

        results: List[DealItem] = []
        try:
            resp = requests.get(url, headers=self.headers, impersonate="chrome124", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[Rebuy] Risposta HTTP anomala: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=re.compile(r"/i,\d+/"))

            seen_ids = set()
            for a in links:
                if len(results) >= max_results:
                    break

                href = a.get("href", "")
                m_id = re.search(r"/i,(\d+)/", href)
                if not m_id:
                    continue

                item_id = m_id.group(1)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                grand = a.find_parent("div", attrs={"data-cy": re.compile(r"product")})
                if not grand:
                    grand = a.parent

                # Estrazione titolo pulito dallo slug dell'URL
                # es. /i,1926034/nintendo-3ds/nintendo-3ds-kosmos-schwarz -> Nintendo 3ds Kosmos Schwarz
                slug = href.split("/")[-1].replace("-", " ").title()
                title = slug if len(slug) > 3 else "Prodotto Rebuy"

                # Estrazione prezzo
                price_val = 0.0
                m_price = re.search(r'([\d\.,]+)\s*€', grand.text)
                if m_price:
                    try:
                        price_val = float(m_price.group(1).replace(".", "").replace(",", "."))
                    except ValueError:
                        pass

                if price_val <= 0.0:
                    continue

                img = grand.find("img")
                image_url = img.get("src") if img else None

                # Spedizione standard verso Italia da Rebuy ~4.99€
                shipping_val = 4.99
                total_val = round(price_val + shipping_val, 2)
                item_url = f"{self.base_url}{href}" if href.startswith("/") else href

                deal = DealItem(
                    id=f"rebuy_{item_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=total_val,
                    url=item_url,
                    image_url=image_url,
                    source="rebuy",
                    description=f"{title} (Usato ricondizionato con garanzia Rebuy)",
                    location="Rebuy (Germania / UE)",
                    is_international=True,
                    condition_text="Ricondizionato garantito",
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Rebuy] Errore scraping per '{query}': {e}", exc_info=True)

        return results

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        return await asyncio.to_thread(self._search_sync, query, max_results)
