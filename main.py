import asyncio
import logging
import sys
from pathlib import Path
from telegram.ext import Application

# Assicura codifica UTF-8 su console Windows e Linux
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.config import settings
from core.database import db
from core.monitor import DealsMonitor
from bot.handlers import register_handlers
from scrapers.manager import scraper_manager

# Configurazione Logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=getattr(logging, settings.log_level, logging.INFO),
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.db_path.parent / "offertebot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("OfferteBot")


async def run_cli_test():
    """Esegue una scansione dimostrativa da riga di comando senza richiedere token Telegram."""
    logger.info("=== AVVIO MODALITÀ TEST RIGA DI COMANDO ===")
    await db.init_db()
    query = "iPhone 13"
    target = 350.0
    logger.info(f"Ricerca di prova: '{query}' (Target: €{target})")
    
    deals = await scraper_manager.search_all(query, target_price=target, max_results_per_platform=5)
    logger.info(f"Trovati {len(deals)} risultati analizzati:")
    for d in deals:
        logger.info(
            f"[{d.score}/10] {d.source.upper()} - {d.title[:50]} | "
            f"Prezzo: €{d.price:.2f} + Sped: €{d.shipping_cost:.2f} = €{d.total_price:.2f} | "
            f"Condizioni: {d.defect_severity} ({', '.join(d.defect_labels) if d.defect_labels else 'Nessun difetto'})"
        )
        logger.info(f"  Link: {d.url}")


async def main():
    if "--test" in sys.argv:
        await run_cli_test()
        return

    # Inizializzazione Database
    await db.init_db()

    token = settings.telegram_bot_token
    if not token or token == "inserisci_qui_il_tuo_token_bot":
        logger.error(
            "\n"
            "===============================================================\n"
            "❌ ERRORE: TELEGRAM_BOT_TOKEN non configurato!\n"
            "1. Crea un bot su Telegram parlando con @BotFather\n"
            "2. Copia il token nel file .env (es. TELEGRAM_BOT_TOKEN=123456:ABC-DEF)\n"
            "3. Se vuoi testare solo lo scraping e il voto da terminale, avvia con:\n"
            "   python main.py --test\n"
            "==============================================================="
        )
        sys.exit(1)

    # Costruzione applicazione Telegram
    app = Application.builder().token(token).build()
    register_handlers(app)

    # Avvio Monitor di background
    monitor = DealsMonitor(bot_app=app)
    
    logger.info("Avvio di OfferteBot...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    # Avvio loop di monitoraggio periodico
    monitor_task = asyncio.create_task(monitor.start())

    logger.info("Bot Telegram avviato e in ascolto.")
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Arresto in corso...")
        monitor.stop()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("OfferteBot terminato.")
