import asyncio
import logging
from typing import List, Optional

from scrapers.base import DealItem, BaseScraper
from scrapers.subito import SubitoScraper
from scrapers.vinted import VintedScraper
from scrapers.ebay import EbayScraper
from scrapers.wallapop import WallapopScraper
from core.analyzer import analyzer

logger = logging.getLogger(__name__)


class ScraperManager:
    def __init__(self):
        self.scrapers: List[BaseScraper] = [
            SubitoScraper(),
            VintedScraper(),
            EbayScraper(),
            WallapopScraper(),
        ]

    async def search_all(
        self,
        query: str,
        target_price: Optional[float] = None,
        min_price: Optional[float] = None,
        exclude_broken: bool = False,
        max_results_per_platform: int = 20
    ) -> List[DealItem]:
        """
        Interroga tutti i marketplace in parallelo, raccoglie le offerte,
        esegue l'analisi difetti e il calcolo del voto (1-10), ordinandole per convenienza.
        """
        tasks = [
            s.search(query, max_results=max_results_per_platform)
            for s in self.scrapers
        ]

        # Esecuzione concorrente con gestione sicura degli errori per singola piattaforma
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        combined_deals: List[DealItem] = []
        seen_urls = set()

        for idx, resp in enumerate(responses):
            scraper_name = self.scrapers[idx].name
            if isinstance(resp, Exception):
                logger.error(f"Errore nello scraper '{scraper_name}': {resp}")
                continue
            if isinstance(resp, list):
                logger.info(f"[{scraper_name}] Trovati {len(resp)} annunci per '{query}'")
                for deal in resp:
                    if deal.url and deal.url not in seen_urls:
                        seen_urls.add(deal.url)
                        combined_deals.append(deal)

        # Analisi semantica difetti e calcolo voto 1-10
        analyzed_deals = analyzer.analyze_batch(combined_deals, target_price=target_price, min_price=min_price)

        # Se la ricerca punta a una console o se l'utente cerca l'hardware, escludiamo a priori giochi e cover
        analyzed_deals = [d for d in analyzed_deals if d.defect_severity != "ACCESSORY"]

        # Filtro per escludere articoli con danni critici se richiesto
        if exclude_broken:
            analyzed_deals = [d for d in analyzed_deals if d.defect_severity != "CRITICAL"]

        return analyzed_deals


scraper_manager = ScraperManager()
