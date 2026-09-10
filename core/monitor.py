import asyncio
import logging
from typing import Optional
from telegram.constants import ParseMode

from core.config import settings
from core.database import db
from scrapers.manager import scraper_manager
from bot.formatters import format_deal_message, get_deal_keyboard

logger = logging.getLogger(__name__)


class DealsMonitor:
    def __init__(self, bot_app=None):
        self.bot_app = bot_app
        self.is_running = False

    async def start(self):
        self.is_running = True
        logger.info(f"Monitor periodico avviato. Intervallo: {settings.check_interval_minutes} minuti.")

        while self.is_running:
            try:
                await self.run_check_cycle()
            except Exception as e:
                logger.error(f"Errore durante il ciclo di monitoraggio: {e}", exc_info=True)

            # Attesa prima della prossima iterazione
            wait_seconds = max(60, settings.check_interval_minutes * 60)
            await asyncio.sleep(wait_seconds)

    def stop(self):
        self.is_running = False
        logger.info("Monitor periodico arrestato.")

    async def run_check_cycle(self):
        active_searches = await db.get_all_active_searches()
        if not active_searches:
            logger.info("Nessuna ricerca attiva nel database.")
            return

        logger.info(f"Avvio scansione per {len(active_searches)} ricerche attive...")

        for search in active_searches:
            search_id = search["id"]
            query = search["query"]
            target_price = search["target_price"]
            min_score = search["min_score"]
            exclude_broken = bool(search["exclude_broken"])
            chat_id = search["chat_id"]

            if chat_id == "default" and settings.telegram_chat_id:
                chat_id = settings.telegram_chat_id

            logger.info(f"Controllo offerte per: '{query}' (Target: {target_price}€, MinScore: {min_score})")

            try:
                deals = await scraper_manager.search_all(
                    query=query,
                    target_price=target_price,
                    min_price=search.get("min_price"),
                    exclude_broken=exclude_broken,
                    max_results_per_platform=15
                )

                for deal in deals:
                    already_seen = await db.is_deal_seen(deal.id)
                    if already_seen:
                        continue

                    # Nuova offerta trovata!
                    should_alert = deal.score >= min_score
                    await db.save_deal(deal, notified=should_alert)

                    if should_alert and self.bot_app and chat_id and chat_id != "default":
                        await self.send_alert(chat_id, deal, target_price)

                await db.update_last_checked(search_id)

            except Exception as e:
                logger.error(f"Errore controllo ricerca '{query}': {e}")

            # Pausa cortese di 3 secondi tra una ricerca e l'altra
            await asyncio.sleep(3)

    async def send_alert(self, chat_id: str, deal, target_price: Optional[float] = None):
        try:
            text = format_deal_message(deal, target_price=target_price, is_alert=True)
            markup = get_deal_keyboard(deal.url)
            await self.bot_app.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            logger.info(f"Alert inviato a {chat_id} per '{deal.title}' (Voto: {deal.score}/10)")
        except Exception as e:
            logger.error(f"Impossibile inviare alert Telegram a {chat_id}: {e}")
