import asyncio
import json
import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class WillhabenScraper(BaseScraper):
    """Scraper per Willhaben (Austria), il più grande marketplace di annunci dell'Austria."""

    def __init__(self):
        super().__init__(name="willhaben")
        self.base_url = "https://www.willhaben.at"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-AT,de;q=0.9,en-US;q=0.8,it;q=0.7",
        }

    def _search_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote_plus(query)
        url = f"{self.base_url}/iad/kaufen-und-verkaufen/marktplatz?keyword={encoded_query}"

        results: List[DealItem] = []
        try:
            resp = requests.get(url, headers=self.headers, impersonate="chrome124", timeout=15)
            if resp.status_code != 200:
                logger.warning(f"[Willhaben] Risposta HTTP anomala: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            tag = soup.find("script", id="__NEXT_DATA__")
            if not tag:
                return []

            data = json.loads(tag.text)
            page_props = data.get("props", {}).get("pageProps", {})
            search_result = page_props.get("searchResult", {})
            ads = search_result.get("advertSummaryList", {}).get("advertSummary", [])

            for ad in ads:
                if len(results) >= max_results:
                    break

                ad_id = str(ad.get("id") or "")
                raw_attrs = ad.get("attributes", {}).get("attribute", [])
                attrs = {
                    x.get("name"): x.get("values", [""])[0]
                    for x in raw_attrs
                    if x.get("values")
                }

                title = attrs.get("HEADING") or ad.get("description", "")
                if not title:
                    continue

                price_str = attrs.get("PRICE/AMOUNT", "0")
                try:
                    price_val = float(price_str)
                except ValueError:
                    price_val = 0.0

                if price_val <= 0.0:
                    continue

                description = attrs.get("BODY_DYN", "") or title
                seo_url = attrs.get("SEO_URL", "")
                if seo_url:
                    item_url = f"{self.base_url}/iad/{seo_url}"
                else:
                    item_url = f"{self.base_url}/iad/kaufen-und-verkaufen/d/-{ad_id}/"

                mmo_img = attrs.get("MMO", "")
                image_url = f"https://cache.willhaben.at/mmo/{mmo_img}" if mmo_img else None

                location_val = attrs.get("LOCATION", "Austria")
                shipping_val = 8.90
                total_val = round(price_val + shipping_val, 2)

                deal = DealItem(
                    id=f"willhaben_{ad_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=total_val,
                    url=item_url,
                    image_url=image_url,
                    source="willhaben",
                    description=description,
                    location=f"{location_val} (Willhaben AT)",
                    is_international=True,
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Willhaben] Errore scraping per '{query}': {e}", exc_info=True)

        return results

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        return await asyncio.to_thread(self._search_sync, query, max_results)
