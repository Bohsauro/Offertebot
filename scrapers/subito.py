import json
import logging
import urllib.parse
from typing import List
from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class SubitoScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="subito")
        self.base_url = "https://www.subito.it/annunci-italia/vendita/usato/"

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote(query)
        url = f"{self.base_url}?q={encoded_query}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        results: List[DealItem] = []
        try:
            # Esecuzione della richiesta con impersonificazione browser TLS
            response = requests.get(url, headers=headers, impersonate="chrome124", timeout=15)
            if response.status_code != 200:
                logger.warning(f"[Subito] Risposta HTTP anomala: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.warning("[Subito] Tag __NEXT_DATA__ non trovato nella pagina.")
                return []

            data = json.loads(script.string)
            items_list = (
                data.get("props", {})
                .get("pageProps", {})
                .get("initialState", {})
                .get("items", {})
                .get("originalList", [])
            )

            for raw in items_list:
                if len(results) >= max_results:
                    break

                subject = raw.get("subject", "").strip()
                if not subject:
                    continue

                urn = raw.get("urn", "")
                deal_id = urn.split(":")[-1] if ":" in urn else str(raw.get("id", urn))

                # Estrazione Prezzo
                features = raw.get("features", {})
                price_val = 0.0
                price_data = features.get("/price", {}).get("values", [])
                if price_data:
                    raw_price_str = price_data[0].get("key", "0").replace(".", "").replace(",", ".")
                    try:
                        price_val = float(raw_price_str)
                    except ValueError:
                        price_val = 0.0

                # Estrazione Spedizione TuttoSubito
                shipping_val = 0.0
                ship_data = features.get("/item_shipping_cost_tuttosubito", {}).get("values", [])
                if ship_data:
                    raw_ship_str = ship_data[0].get("key", "0").replace(".", "").replace(",", ".")
                    try:
                        shipping_val = float(raw_ship_str)
                    except ValueError:
                        shipping_val = 0.0
                else:
                    # Verifica se la spedizione è dichiarata disponibile
                    ship_allowed = features.get("/item_shipping_allowed", {}).get("values", [])
                    if ship_allowed and ship_allowed[0].get("key") == "1":
                        shipping_val = 4.99  # Stima spedizione standard TuttoSubito
                    else:
                        shipping_val = 0.0

                # Condizione dichiarata
                condition_text = ""
                cond_data = features.get("/item_condition", {}).get("values", [])
                if cond_data:
                    cond_val = cond_data[0].get("value", "")
                    cond_desc = cond_data[0].get("description", "")
                    condition_text = f"{cond_val}. {cond_desc}".strip()

                # Descrizione e Località
                body = raw.get("body", "") or ""
                geo = raw.get("geo", {})
                city = geo.get("city", {}).get("value", "")
                town = geo.get("town", {}).get("value", "")
                region = geo.get("region", {}).get("value", "")
                loc_parts = [p for p in [town, city, region] if p]
                location = ", ".join(loc_parts) if loc_parts else "Italia"

                # Immagini e URL
                images = raw.get("images", [])
                image_url = None
                if images and isinstance(images, list):
                    scales = images[0].get("scale", [])
                    if scales:
                        image_url = scales[-1].get("uri")

                urls = raw.get("urls", {})
                deal_url = urls.get("default", "")

                deal = DealItem(
                    id=f"subito_{deal_id}",
                    title=subject,
                    price=price_val,
                    shipping_cost=shipping_val,
                    total_price=round(price_val + shipping_val, 2),
                    url=deal_url,
                    image_url=image_url,
                    source="subito",
                    description=body,
                    location=location,
                    is_international=False,
                    condition_text=condition_text,
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Subito] Errore durante lo scraping per '{query}': {e}", exc_info=True)

        return results
