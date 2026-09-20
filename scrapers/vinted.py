import asyncio
import logging
import re
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


def _parse_price(val: str) -> float:
    val = val.strip()
    if "," in val and "." in val:
        val = val.replace(".", "").replace(",", ".")
    elif "," in val:
        val = val.replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return 0.0


class VintedScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="vinted")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _scrape_catalog_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.vinted.it/catalog?search_text={encoded_query}&order=newest_first"

        try:
            session = requests.Session(impersonate="chrome124")
            resp = session.get(url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[Vinted] Risposta catalogo anomala: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            overlays = soup.find_all("a", attrs={"data-testid": re.compile(r"product-item-id-(\d+)--overlay-link")})

            results: List[DealItem] = []
            for a in overlays:
                if len(results) >= max_results:
                    break

                title_attr = a.get("title", "")
                href = a.get("href", "")
                m_id = re.search(r"product-item-id-(\d+)--overlay-link", a.get("data-testid", ""))
                item_id = m_id.group(1) if m_id else ""

                if not item_id or not title_attr:
                    continue

                card = a.find_parent("div", class_=re.compile(r"ItemBox|cell|feed-grid")) or a.parent
                if any(w in card.text.lower() for w in ["venduto", "vendu", "sold", "prenotato", "réservé", "reserved"]):
                    continue

                img = a.parent.find("img", attrs={"data-testid": re.compile(r"--image--img")})
                image_url = img.get("src") if img else None

                prices = re.findall(r"([\d\.,]+)\s*€", title_attr)
                price_val = _parse_price(prices[0]) if prices else 0.0
                total_price_val = _parse_price(prices[-1]) if len(prices) > 1 else price_val
                fee_val = round(max(0.0, total_price_val - price_val), 2)

                clean_title = title_attr
                cond_text = ""
                if "Brand:" in title_attr or "Condizioni:" in title_attr:
                    clean_title = re.split(r",\s*(?:Brand|Condizioni):", title_attr)[0].strip()
                    m_cond = re.search(r"Condizioni:\s*([^,]+)", title_attr)
                    if m_cond:
                        cond_text = m_cond.group(1).strip()

                estimated_shipping = 3.50
                total_shipping_and_fees = round(fee_val + estimated_shipping, 2)
                final_total = round(price_val + total_shipping_and_fees, 2)
                deal_url = f"https://www.vinted.it{href}" if href.startswith("/") else href

                deal = DealItem(
                    id=f"vinted_{item_id}",
                    title=clean_title,
                    price=price_val,
                    shipping_cost=total_shipping_and_fees,
                    total_price=final_total,
                    url=deal_url,
                    image_url=image_url,
                    source="vinted",
                    description=clean_title,
                    location="Vinted (IT / Europa)",
                    is_international=True,
                    condition_text=cond_text,
                    search_query=query
                )
                results.append(deal)

            return results

        except Exception as e:
            logger.error(f"[Vinted] Errore durante lo scraping per '{query}': {e}", exc_info=True)
            return []

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        """Esegue lo scraping su Vinted in un thread asincrono separato per non bloccare l'event loop."""
        return await asyncio.to_thread(self._scrape_catalog_sync, query, max_results)

