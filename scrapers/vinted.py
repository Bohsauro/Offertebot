import logging
import urllib.parse
from typing import List, Optional
from curl_cffi import requests

from scrapers.base import BaseScraper, DealItem

logger = logging.getLogger(__name__)


class VintedScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="vinted")
        self.session: Optional[requests.Session] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    def _get_session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
            try:
                # Richiesta iniziale per ottenere i cookie di sessione validi
                self.session.get("https://www.vinted.it", headers=self.headers, impersonate="chrome124", timeout=15)
            except Exception as e:
                logger.warning(f"[Vinted] Errore inizializzazione sessione/cookie: {e}")
        return self.session

    async def search(self, query: str, max_results: int = 25) -> List[DealItem]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://www.vinted.it/api/v2/catalog/items?search_text={encoded_query}&order=newest_first"

        results: List[DealItem] = []
        try:
            session = self._get_session()
            response = session.get(url, headers=self.headers, impersonate="chrome124", timeout=15)

            # Se la sessione è scaduta o ritorna 401/403, rigeneriamo la sessione una volta
            if response.status_code in (401, 403):
                logger.info("[Vinted] Cookie di sessione scaduti, rigenerazione in corso...")
                self.session = requests.Session()
                self.session.get("https://www.vinted.it", headers=self.headers, impersonate="chrome124", timeout=15)
                response = self.session.get(url, headers=self.headers, impersonate="chrome124", timeout=15)

            if response.status_code != 200:
                logger.warning(f"[Vinted] Risposta API non valida: {response.status_code}")
                return []

            data = response.json()
            raw_items = data.get("items", [])

            for it in raw_items:
                if len(results) >= max_results:
                    break

                title = it.get("title", "").strip()
                if not title:
                    continue

                item_id = str(it.get("id", ""))
                price_dict = it.get("price", {})
                price_val = 0.0
                try:
                    price_val = float(price_dict.get("amount", "0"))
                except ValueError:
                    price_val = 0.0

                # Commissione protezione acquisti Vinted
                service_fee_dict = it.get("service_fee", {})
                fee_val = 0.0
                try:
                    fee_val = float(service_fee_dict.get("amount", "0"))
                except ValueError:
                    fee_val = 0.0

                # Stima spedizione Vinted (punto di ritiro medio IT/EU ~3.50€)
                estimated_shipping = 3.50
                total_shipping_and_fees = round(fee_val + estimated_shipping, 2)
                total_price = round(price_val + total_shipping_and_fees, 2)

                # Foto
                photo_obj = it.get("photo", {}) or {}
                image_url = photo_obj.get("url")

                # URL articolo
                item_url = it.get("url", "")
                if item_url and not item_url.startswith("http"):
                    item_url = f"https://www.vinted.it{item_url}"

                brand = it.get("brand_title", "")
                condition_desc = f"Brand: {brand}" if brand else ""

                deal = DealItem(
                    id=f"vinted_{item_id}",
                    title=title,
                    price=price_val,
                    shipping_cost=total_shipping_and_fees,
                    total_price=total_price,
                    url=item_url,
                    image_url=image_url,
                    source="vinted",
                    description=title,
                    location="Vinted (IT / Europa)",
                    is_international=True,
                    condition_text=condition_desc,
                    search_query=query
                )
                results.append(deal)

        except Exception as e:
            logger.error(f"[Vinted] Errore durante la ricerca per '{query}': {e}", exc_info=True)

        return results
