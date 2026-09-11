import logging
import re
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
)

from core.database import db
from core.config import settings
from scrapers.manager import scraper_manager
from bot.formatters import format_deal_message, get_deal_keyboard

logger = logging.getLogger(__name__)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🏆 Migliori Offerte", callback_data="menu:offers"),
            InlineKeyboardButton("📋 Le Mie Ricerche", callback_data="menu:searches")
        ],
        [
            InlineKeyboardButton("🔍 Cerca Subito una Console", callback_data="menu:quick_search_menu"),
        ],
        [
            InlineKeyboardButton("⚙️ Impostazioni", callback_data="menu:settings"),
            InlineKeyboardButton("❓ Guida Comandi", callback_data="menu:help")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def get_quick_search_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("🎮 New 3DS XL", callback_data="qsearch:New Nintendo 3DS XL"),
            InlineKeyboardButton("🎮 New 2DS XL", callback_data="qsearch:New Nintendo 2DS XL")
        ],
        [
            InlineKeyboardButton("🎮 New 3DS", callback_data="qsearch:New Nintendo 3DS"),
            InlineKeyboardButton("🎮 3DS XL", callback_data="qsearch:Nintendo 3DS XL")
        ],
        [
            InlineKeyboardButton("🎮 3DS Standard", callback_data="qsearch:Nintendo 3DS"),
            InlineKeyboardButton("🎮 PS Vita", callback_data="qsearch:PS Vita")
        ],
        [
            InlineKeyboardButton("🔙 Torna al Menu Principale", callback_data="menu:main")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📱 <b>PANNELLO DI CONTROLLO - OFFERTEBOT</b> 🤖\n\n"
        "Seleziona un'azione rapida toccando i pulsanti qui sotto:"
    )
    markup = get_main_menu_keyboard()
    if update.message:
        await update.message.reply_text(msg, reply_markup=markup, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=markup, parse_mode=ParseMode.HTML)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name if update.effective_user else "Utente"
    msg = (
        f"👋 Ciao <b>{user_name}</b>! Benvenuto su <b>OfferteBot</b> 🤖\n\n"
        f"Questo bot monitora per te le migliori offerte su <b>usato e nuovo</b> "
        f"(Subito.it, Vinted, eBay, Wallapop e siti esteri) con <b>filtro rigoroso anti-giochi e anti-cover</b>!\n\n"
        f"<b>Funzionalità principali:</b>\n"
        f"• 💰 <b>Prezzo Totale Trasparente</b>: calcola sempre prezzo articolo + spedizione.\n"
        f"• 🔍 <b>Analisi Danni e Tasti</b>: rileva tasti rotti, stick drift o danni da riparare.\n"
        f"• 🏆 <b>Voto da 1 a 10</b>: calcola la convenienza reale dell'offerta.\n"
        f"• 🚨 <b>Alert Automatici</b>: ti avvisa all'istante quando esce un affare.\n\n"
        f"<b>Comandi principali:</b>\n"
        f"📱 /menu — <b>Menu interattivo a pulsanti</b>\n"
        f"⭐ /offerte — Mostra le migliori occasioni trovate\n"
        f"🔍 /cerca <code>&lt;console&gt; [budget]</code> — Cerca subito dal vivo\n"
        f"📌 /traccia <code>&lt;console&gt; [budget]</code> — Aggiunge monitoraggio automatico\n"
        f"📋 /mieicerche — Gestisci le ricerche attive\n"
        f"⚙️ /impostazioni — Mostra parametri e filtri\n\n"
        f"<i>Tocca il pulsante qui sotto per aprire il menu rapido:</i>"
    )
    await update.message.reply_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Specifica cosa cercare!\n"
            "Esempio: <code>/cerca iPhone 13 350</code> oppure <code>/cerca PlayStation 5</code>",
            parse_mode=ParseMode.HTML
        )
        return

    # Estrazione query e opzionale prezzo target
    full_text = " ".join(context.args)
    target_price: Optional[float] = None

    match = re.search(r'\s+(\d+(?:[\.,]\d+)?)$', full_text)
    if match:
        try:
            target_price = float(match.group(1).replace(",", "."))
            query = full_text[:match.start()].strip()
        except ValueError:
            query = full_text
    else:
        query = full_text

    status_msg = await update.message.reply_text(
        f"🔎 Cerco <b>'{query}'</b> su Subito, Vinted, eBay e Wallapop...\n"
        f"<i>Analisi difetti e calcolo convenienza in corso...</i>",
        parse_mode=ParseMode.HTML
    )

    try:
        min_price = (target_price * 0.35) if (target_price and target_price >= 50.0) else None
        deals = await scraper_manager.search_all(
            query=query,
            target_price=target_price,
            min_price=min_price,
            exclude_broken=False,
            max_results_per_platform=10
        )

        if not deals:
            await status_msg.edit_text(
                f"❌ Nessuna offerta trovata per <b>'{query}'</b> al momento.",
                parse_mode=ParseMode.HTML
            )
            return

        await status_msg.delete()

        # Invia le migliori 5 offerte trovate
        top_deals = deals[:5]
        for deal in top_deals:
            text = format_deal_message(deal, target_price=target_price, is_alert=False)
            markup = get_deal_keyboard(deal.url)
            await update.message.reply_text(
                text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )

    except Exception as e:
        logger.error(f"Errore durante /cerca: {e}", exc_info=True)
        await status_msg.edit_text("❌ Si è verificato un errore durante la ricerca.")


async def track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Indica il prodotto e opzionalmente il prezzo massimo desiderato!\n"
            "Esempi:\n"
            "• <code>/traccia iPhone 13 350</code>\n"
            "• <code>/traccia Nintendo Switch OLED 200</code>",
            parse_mode=ParseMode.HTML
        )
        return

    chat_id = str(update.effective_chat.id)
    full_text = " ".join(context.args)
    target_price: Optional[float] = None

    match = re.search(r'\s+(\d+(?:[\.,]\d+)?)$', full_text)
    if match:
        try:
            target_price = float(match.group(1).replace(",", "."))
            query = full_text[:match.start()].strip()
        except ValueError:
            query = full_text
    else:
        query = full_text

    search_id = await db.add_search(
        chat_id=chat_id,
        query=query,
        target_price=target_price,
        min_score=settings.min_alert_score,
        exclude_broken=settings.exclude_broken
    )

    price_desc = f"a max <b>€ {target_price:.2f}</b>" if target_price else "a qualsiasi prezzo conveniente"
    await update.message.reply_text(
        f"✅ Ricerca monitorata aggiunta con successo!\n\n"
        f"📌 <b>ID:</b> #{search_id}\n"
        f"📦 <b>Prodotto:</b> {query}\n"
        f"🎯 <b>Budget target:</b> {price_desc}\n"
        f"⭐ <b>Voto minimo per alert:</b> {settings.min_alert_score}/10\n\n"
        f"OfferteBot ti invierà un messaggio non appena verrà trovato un affare!",
        parse_mode=ParseMode.HTML
    )


async def my_searches_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    searches = await db.get_searches_by_chat_id(chat_id)

    if not searches:
        await update.message.reply_text(
            "ℹ️ Non hai ancora ricerche attive.\n"
            "Usa <code>/traccia &lt;prodotto&gt; [prezzo]</code> per aggiungerne una!",
            parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text("📋 <b>Le tue ricerche monitorate:</b>", parse_mode=ParseMode.HTML)

    for s in searches:
        status_icon = "🟢 Attivo" if s["is_active"] else "⏸️ In Pausa"
        budget = f"€ {s['target_price']:.2f}" if s["target_price"] else "N/D"
        text = (
            f"📌 <b>#{s['id']} — {s['query']}</b>\n"
            f"🎯 Target: <b>{budget}</b> | Stato: {status_icon}\n"
            f"⭐ Voto minimo: {s['min_score']}/10"
        )
        toggle_label = "⏸️ Metti in Pausa" if s["is_active"] else "▶️ Riattiva"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(toggle_label, callback_data=f"toggle:{s['id']}"),
                InlineKeyboardButton("🗑️ Elimina", callback_data=f"delete:{s['id']}")
            ]
        ])
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def offers_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None
    deals = await db.get_top_deals(query=query, min_score=6.0, limit=8)

    if not deals:
        filter_text = f" per '<b>{query}</b>'" if query else ""
        await update.message.reply_text(
            f"ℹ️ Nessuna offerta registrata attualmente{filter_text}.\n"
            f"Usa <code>/cerca &lt;prodotto&gt;</code> per effettuare una scansione live!",
            parse_mode=ParseMode.HTML
        )
        return

    await update.message.reply_text(
        f"🏆 <b>Migliori Offerte Attuali nel Database:</b>",
        parse_mode=ParseMode.HTML
    )

    for d in deals:
        from scrapers.base import DealItem
        import json

        item = DealItem(
            id=d["id"],
            title=d["title"],
            price=d["price"],
            shipping_cost=d["shipping_cost"],
            total_price=d["total_price"],
            url=d["url"],
            image_url=d["image_url"],
            source=d["source"],
            description=d["description"],
            location=d["location"] or "Italia",
            score=d["score"],
            defect_severity=d["defect_severity"] or "NONE",
            defect_labels=json.loads(d["defect_labels"]) if d["defect_labels"] else []
        )
        text = format_deal_message(item, is_alert=False)
        markup = get_deal_keyboard(item.url)
        await update.message.reply_text(
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"⚙️ <b>Impostazioni Attuali di OfferteBot:</b>\n\n"
        f"⏱️ <b>Frequenza Scansioni:</b> ogni {settings.check_interval_minutes} minuti\n"
        f"⭐ <b>Soglia Minima Alert:</b> {settings.min_alert_score}/10\n"
        f"🛡️ <b>Escludi Prodotti Rotti:</b> {'Sì' if settings.exclude_broken else 'No (penalizzati nel voto)'}\n"
        f"📦 <b>Stima Spedizione Estera:</b> € {settings.default_estimated_shipping_international:.2f}\n\n"
        f"<i>Puoi modificare questi valori nel file <code>.env</code> o <code>config.yaml</code> sul tuo server Ubuntu.</i>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = str(update.effective_chat.id)

    if data == "menu:main":
        msg = (
            "📱 <b>PANNELLO DI CONTROLLO - OFFERTEBOT</b> 🤖\n\n"
            "Seleziona un'azione rapida toccando i pulsanti qui sotto:"
        )
        await query.edit_message_text(msg, reply_markup=get_main_menu_keyboard(), parse_mode=ParseMode.HTML)

    elif data == "menu:quick_search_menu":
        msg = (
            "🔍 <b>RICERCA RAPIDA CONSOLE</b> 🎮\n\n"
            "Tocca una delle console qui sotto per scansionare istantaneamente tutti i marketplace:"
        )
        await query.edit_message_text(msg, reply_markup=get_quick_search_keyboard(), parse_mode=ParseMode.HTML)

    elif data.startswith("qsearch:"):
        console_name = data.split(":", 1)[1]
        await query.edit_message_text(
            f"🔎 Scansione in corso per <b>'{console_name}'</b>...\n"
            f"<i>Controllo Subito, Vinted, eBay e Wallapop con filtro anti-giochi...</i>",
            parse_mode=ParseMode.HTML
        )
        try:
            deals = await scraper_manager.search_all(
                query=console_name,
                exclude_broken=False,
                max_results_per_platform=10
            )
            if not deals:
                back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Ricerca Rapida", callback_data="menu:quick_search_menu")]])
                await query.edit_message_text(
                    f"❌ Nessuna offerta trovata per <b>'{console_name}'</b> al momento.",
                    reply_markup=back_keyboard,
                    parse_mode=ParseMode.HTML
                )
                return

            await query.edit_message_text(
                f"✅ Scansione completata per <b>'{console_name}'</b>! Ecco i migliori risultati:",
                parse_mode=ParseMode.HTML
            )
            for d in deals[:5]:
                text = format_deal_message(d, is_alert=False)
                markup = get_deal_keyboard(d.url)
                await query.message.reply_text(
                    text,
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Errore durante quick search {console_name}: {e}", exc_info=True)
            await query.edit_message_text("❌ Si è verificato un errore durante la ricerca.")

    elif data == "menu:offers":
        deals = await db.get_top_deals(min_score=6.0, limit=6)
        if not deals:
            back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Principale", callback_data="menu:main")]])
            await query.edit_message_text(
                "ℹ️ Nessuna offerta registrata attualmente nel database.\n"
                "Usa 🔍 <b>Cerca Subito una Console</b> per scansionare dal vivo!",
                reply_markup=back_keyboard,
                parse_mode=ParseMode.HTML
            )
            return

        await query.edit_message_text("🏆 <b>Migliori Offerte Attuali:</b>", parse_mode=ParseMode.HTML)
        for d in deals:
            from scrapers.base import DealItem
            import json

            item = DealItem(
                id=d["id"],
                title=d["title"],
                price=d["price"],
                shipping_cost=d["shipping_cost"],
                total_price=d["total_price"],
                url=d["url"],
                image_url=d["image_url"],
                source=d["source"],
                description=d["description"],
                location=d["location"] or "Italia",
                score=d["score"],
                defect_severity=d["defect_severity"] or "NONE",
                defect_labels=json.loads(d["defect_labels"]) if d["defect_labels"] else []
            )
            text = format_deal_message(item, is_alert=False)
            markup = get_deal_keyboard(item.url)
            await query.message.reply_text(
                text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )

    elif data == "menu:searches":
        searches = await db.get_searches_by_chat_id(chat_id)
        if not searches:
            back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Principale", callback_data="menu:main")]])
            await query.edit_message_text(
                "ℹ️ Non hai ancora ricerche attive.\n"
                "Usa <code>/traccia &lt;prodotto&gt; [prezzo]</code> per aggiungerne una!",
                reply_markup=back_keyboard,
                parse_mode=ParseMode.HTML
            )
            return

        await query.edit_message_text("📋 <b>Le tue ricerche monitorate:</b>", parse_mode=ParseMode.HTML)
        for s in searches:
            status_icon = "🟢 Attivo" if s["is_active"] else "⏸️ In Pausa"
            budget = f"€ {s['target_price']:.2f}" if s["target_price"] else "N/D"
            text = (
                f"📌 <b>#{s['id']} — {s['query']}</b>\n"
                f"🎯 Target: <b>{budget}</b> | Stato: {status_icon}\n"
                f"⭐ Voto minimo: {s['min_score']}/10"
            )
            toggle_label = "⏸️ Metti in Pausa" if s["is_active"] else "▶️ Riattiva"
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(toggle_label, callback_data=f"toggle:{s['id']}"),
                    InlineKeyboardButton("🗑️ Elimina", callback_data=f"delete:{s['id']}")
                ]
            ])
            await query.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    elif data == "menu:settings":
        msg = (
            f"⚙️ <b>Impostazioni Attuali di OfferteBot:</b>\n\n"
            f"⏱️ <b>Frequenza Scansioni:</b> ogni {settings.check_interval_minutes} minuti\n"
            f"⭐ <b>Soglia Minima Alert:</b> {settings.min_alert_score}/10\n"
            f"🛡️ <b>Escludi Prodotti Rotti:</b> {'Sì' if settings.exclude_broken else 'No (penalizzati nel voto)'}\n"
            f"📦 <b>Stima Spedizione Estera:</b> € {settings.default_estimated_shipping_international:.2f}\n\n"
            f"<i>Configurabile dal file .env sul server.</i>"
        )
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Principale", callback_data="menu:main")]])
        await query.edit_message_text(msg, reply_markup=back_keyboard, parse_mode=ParseMode.HTML)

    elif data == "menu:help":
        msg = (
            f"❓ <b>GUIDA COMANDI OFFERTEBOT:</b>\n\n"
            f"📱 /menu — Menu interattivo completo a pulsanti\n"
            f"⭐ /offerte — Mostra le migliori occasioni nel database\n"
            f"🔍 /cerca <code>&lt;console&gt; [budget]</code> — Ricerca istantanea su tutti i marketplace\n"
            f"📌 /traccia <code>&lt;console&gt; [budget]</code> — Aggiunge un prodotto da monitorare ogni 15 min\n"
            f"📋 /mieicerche — Visualizza e gestisci i tuoi monitoraggi attivi\n"
            f"⚙️ /impostazioni — Parametri e filtri correnti\n\n"
            f"<i>💡 Esempio: <code>/traccia New Nintendo 3DS XL 170</code></i>"
        )
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu Principale", callback_data="menu:main")]])
        await query.edit_message_text(msg, reply_markup=back_keyboard, parse_mode=ParseMode.HTML)

    elif data.startswith("toggle:"):
        search_id = int(data.split(":")[1])
        new_state = await db.toggle_search(search_id, chat_id)
        if new_state is not None:
            status_str = "riattivato 🟢" if new_state else "messo in pausa ⏸️"
            await query.edit_message_text(f"✅ Monitoraggio #{search_id} {status_str}.")
        else:
            await query.edit_message_text("❌ Ricerca non trovata.")

    elif data.startswith("delete:"):
        search_id = int(data.split(":")[1])
        deleted = await db.delete_search(search_id, chat_id)
        if deleted:
            await query.edit_message_text(f"🗑️ Ricerca #{search_id} eliminata definitivamente.")
        else:
            await query.edit_message_text("❌ Ricerca non trovata o già eliminata.")


def register_handlers(app):
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", menu_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("cerca", search_handler))
    app.add_handler(CommandHandler("traccia", track_handler))
    app.add_handler(CommandHandler("mieicerche", my_searches_handler))
    app.add_handler(CommandHandler("offerte", offers_handler))
    app.add_handler(CommandHandler("impostazioni", settings_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
