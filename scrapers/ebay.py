import re
import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class EbayScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="ebay")
        self.base_url = "https://www.ebay.it/sch/i.html"

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote(query)
        # _sop=12 = "Appena inseriti" (i migliori affari prima che vengano acquistati)
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
            if response.status_code != 200:
                logger.warning(f"[eBay] Status code: {response.status_code}")
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

                # Estrazione prezzo
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

                # Estrazione spedizione
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

                # Provenienza / Spedizione estera
                loc_el = it.select_one(".s-item__itemLocation, .s-item__location")
                location = loc_el.text.strip() if loc_el else "Italia"
                is_international = not ("italia" in location.lower())

                # Se estero e spedizione non indicata, applichiamo stima
                if is_international and shipping_val == 0.0:
                    shipping_val = 9.90

                # Link e Immagine
                link_el = it.select_one("a.s-item__link")
                deal_url = link_el["href"] if link_el and "href" in link_el.attrs else ""
                # Pulizia link dai parametri di tracking ebay
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
