import asyncio
import base64
import logging
import os
import re
import time
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class EbayScraper(BaseScraper):
    """Scraper ibrido per eBay: usa le REST API ufficiali se configurate, oppure scraping web via browser impersonation."""

    def __init__(self):
        super().__init__(name="ebay")
        self.base_url = "https://www.ebay.it/sch/i.html"
        self.client_id = os.getenv("EBAY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("EBAY_CLIENT_SECRET", "").strip()
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    async def _get_oauth_token(self) -> Optional[str]:
        if not self.client_id or not self.client_secret:
            return None
        now = time.time()
        if self._token and now < self._token_expiry - 60:
            return self._token

        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        url = "https://api.ebay.com/identity/v1/oauth2/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_header}"
        }
        data = {
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, headers=headers, data=data)
                if r.status_code == 200:
                    token_data = r.json()
                    self._token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 7200)
                    self._token_expiry = now + expires_in
                    return self._token
                else:
                    logger.warning(f"[eBay API] Errore token OAuth ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            logger.error(f"[eBay API] Eccezione OAuth: {e}")
        return None

    async def _search_api(self, query: str, token: str, max_results: int = 25) -> List[DealItem]:
        url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_IT",
            "Accept": "application/json",
        }
        params = {
            "q": query,
            "limit": str(min(max_results, 50)),
            "sort": "newlyListed",
        }
        results: List[DealItem] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(url, headers=headers, params=params)
                if r.status_code == 200:
                    items = r.json().get("itemSummaries", [])
                    for it in items:
                        item_id = it.get("itemId", "")
                        title = it.get("title", "").strip()
                        price_val = float(it.get("price", {}).get("value", 0.0))

                        shipping_opts = it.get("shippingOptions", [])
                        ship_cost = 0.0
                        if shipping_opts:
                            ship_cost = float(shipping_opts[0].get("shippingCost", {}).get("value", 0.0))

                        image_url = it.get("image", {}).get("imageUrl")
                        item_url = it.get("itemWebUrl", "")
                        country = it.get("itemLocation", {}).get("country", "IT")
                        is_international = (country.upper() != "IT")

                        deal = DealItem(
                            id=f"ebay_{item_id}",
                            title=title,
                            price=price_val,
                            shipping_cost=ship_cost,
                            total_price=round(price_val + ship_cost, 2),
                            url=item_url,
                            image_url=image_url,
                            source="ebay",
                            description=title,
                            location=f"eBay ({country})",
                            is_international=is_international,
                            condition_text=it.get("condition", ""),
                            search_query=query
                        )
                        results.append(deal)
                    return results
        except Exception as e:
            logger.error(f"[eBay API] Errore search API: {e}")
        return []

    def _search_sync(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote(query)
        url = f"{self.base_url}?_nkw={encoded_query}&_sop=12"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.google.it/",
        }

        results: List[DealItem] = []
        try:
            response = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
            if response.status_code == 403 or "challenge" in response.text.lower() or response.status_code == 307:
                logger.info(f"[eBay] Bloccato da protezione anti-bot Akamai (Status: {response.status_code}) per '{query}'")
                return []
            elif response.status_code != 200:
                logger.warning(f"[eBay] Status code anomalo: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("li.s-item")

            for it in items:
                if len(results) >= max_results:
                    break

                title_el = it.select_one(".s-item__title")
                if not title_el:
                    continue

                title = title_el.text.strip()
                if "Risultati corrispondenti" in title or not title or title.lower() == "shop on ebay":
                    continue

                price_el = it.select_one(".s-item__price")
                if not price_el:
                    continue

                raw_price = price_el.text.strip()
                price_match = re.search(r'([\d\.,]+)', raw_price.replace(' ', ''))
                if not price_match:
                    continue

                price_str = price_match.group(1).replace(".", "").replace(",", ".")
                try:
                    price_val = float(price_str)
                except ValueError:
                    continue

                shipping_val = 0.0
                ship_el = it.select_one(".s-item__shipping, .s-item__logisticsCost")
                if ship_el:
                    ship_text = ship_el.text.strip().lower()
                    if "gratuita" in ship_text or "gratis" in ship_text or "free" in ship_text:
                        shipping_val = 0.0
                    else:
                        ship_match = re.search(r'([\d\.,]+)', ship_text.replace(' ', ''))
                        if ship_match:
                            try:
                                shipping_val = float(ship_match.group(1).replace(".", "").replace(",", "."))
                            except ValueError:
                                shipping_val = 5.90
                else:
                    shipping_val = 0.0

                loc_el = it.select_one(".s-item__itemLocation, .s-item__location")
                location = loc_el.text.strip() if loc_el else "Italia"
                is_international = not ("italia" in location.lower())

                if is_international and shipping_val == 0.0:
                    shipping_val = 9.90

                link_el = it.select_one("a.s-item__link")
                deal_url = link_el["href"] if link_el and "href" in link_el.attrs else ""
                if "?" in deal_url:
                    deal_url = deal_url.split("?")[0]

                img_el = it.select_one(".s-item__image-img, img")
                image_url = img_el.get("src") or img_el.get("data-src") if img_el else None

                item_id_match = re.search(r'/itm/(\d+)', deal_url)
                deal_id = item_id_match.group(1) if item_id_match else str(abs(hash(deal_url)))

                deal = DealItem(
                    id=f"ebay_{deal_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=round(price_val + shipping_val, 2),
                    url=deal_url,
                    image_url=image_url,
                    source="ebay",
                    description=title,
                    location=location,
                    is_international=is_international,
                    condition_text="",
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[eBay] Errore durante la ricerca per '{query}': {e}", exc_info=True)

        return results

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        # Se sono configurate le credenziali API ufficiali di eBay, usiamo le REST API
        token = await self._get_oauth_token()
        if token:
            api_results = await self._search_api(query, token, max_results=max_results)
            if api_results:
                return api_results

        # Fallback su scraping HTML web
        return await asyncio.to_thread(self._search_sync, query, max_results)
