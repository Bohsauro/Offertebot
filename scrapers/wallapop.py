import logging
import urllib.parse
from typing import List
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class WallapopScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="wallapop")
        self.api_url = "https://api.wallapop.com/api/v3/general/search"

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        params = {
            "keywords": query,
            "filters_source": "search_box",
            "country_code": "IT"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "it-IT,it;q=0.9",
            "Origin": "https://it.wallapop.com",
            "Referer": "https://it.wallapop.com/",
            "X-DeviceOS": "0"
        }

        results: List[DealItem] = []
        try:
            response = requests.get(self.api_url, params=params, headers=headers, impersonate="chrome124", timeout=15)
            if response.status_code != 200:
                logger.info(f"[Wallapop] Endpoint non disponibile o bloccato (Status: {response.status_code})")
                return []

            data = response.json()
            items = data.get("search_objects", [])

            for it in items:
                if len(results) >= max_results:
                    break

                title = it.get("title", "").strip()
                if not title:
                    continue

                item_id = str(it.get("id", ""))
                price_val = float(it.get("price", 0.0))

                # Spedizione Wallapop
                shipping_data = it.get("shipping", {})
                has_shipping = shipping_data.get("user_has_shipping", False)
                shipping_cost = 3.99 if has_shipping else 0.0

                desc = it.get("description", "") or ""
                web_slug = it.get("web_slug", "")
                url = f"https://it.wallapop.com/item/{web_slug}" if web_slug else f"https://it.wallapop.com/item/{item_id}"

                images = it.get("images", [])
                image_url = images[0].get("original") if images else None

                location_data = it.get("location", {})
                city = location_data.get("city", "Italia")

                deal = DealItem(
                    id=f"wallapop_{item_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_cost,
                    total_price=round(price_val + shipping_cost, 2),
                    url=url,
                    image_url=image_url,
                    source="wallapop",
                    description=desc,
                    location=f"{city} (Wallapop)",
                    is_international=False,
                    condition_text="",
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Wallapop] Errore durante la ricerca: {e}")

        return results
