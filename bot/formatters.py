import html
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from scrapers.base import DealItem


def get_score_badge(score: float) -> str:
    if score >= 9.0:
        return "⭐⭐⭐⭐⭐ [9-10/10] 🔥 AFFARE IMPERDIBILE!"
    elif score >= 8.0:
        return "⭐⭐⭐⭐☆ [8-9/10] 🚀 OTTIMO PREZZO!"
    elif score >= 7.0:
        return "⭐⭐⭐☆☆ [7-8/10] ✅ BUONA OPPORTUNITÀ"
    elif score >= 5.5:
        return "⭐⭐☆☆☆ [5.5-7/10] ⚖️ NELLA MEDIA"
    else:
        return "⭐☆☆☆☆ [<5.5/10] ⚠️ PREZZO O CONDIZIONE SFAVOREVOLE"


def format_deal_message(
    deal: DealItem,
    target_price: Optional[float] = None,
    is_alert: bool = False
) -> str:
    badge = get_score_badge(deal.score)
    prefix = "🚨 <b>NUOVA OFFERTA TROVATA!</b>\n\n" if is_alert else ""

    # Formattazione Spedizione
    if deal.shipping_cost == 0.0:
        shipping_text = "<b>Gratuita</b>"
    else:
        shipping_text = f"<b>€ {deal.shipping_cost:.2f}</b>"
        if deal.is_international:
            shipping_text += " <i>(Estero/Stima)</i>"

    # Risparmio rispetto al target
    target_comparison = ""
    ref_price = target_price or deal.score_breakdown.get("reference_price")
    if ref_price and ref_price > 0 and deal.total_price < ref_price:
        savings = ref_price - deal.total_price
        savings_pct = (savings / ref_price) * 100.0
        target_comparison = f"\n🎯 <b>Target:</b> € {ref_price:.2f} <i>(-€ {savings:.2f} / -{savings_pct:.0f}%)</i>"

    # Stato / Danni
    condition_section = ""
    if deal.defect_labels:
        condition_section = f"\n🔍 <b>Analisi Condizioni:</b> " + " ".join(deal.defect_labels)
    elif deal.defect_severity == "NONE":
        condition_section = "\n🔍 <b>Analisi Condizioni:</b> ✅ Nessun danno o difetto segnalato"

    if deal.condition_text:
        safe_cond = html.escape(deal.condition_text[:120])
        condition_section += f"\n📋 <i>Dichiarato: {safe_cond}</i>"

    source_icons = {
        "subito": "🟡 Subito.it",
        "vinted": "🔵 Vinted",
        "ebay": "🔴 eBay",
        "wallapop": "🟢 Wallapop",
    }
    source_str = source_icons.get(deal.source.lower(), f"🏪 {deal.source.capitalize()}")

    safe_title = html.escape(deal.title)
    safe_location = html.escape(deal.location)

    text = (
        f"{prefix}"
        f"<b>{safe_title}</b>\n\n"
        f"<b>Valutazione Offerta:</b>\n"
        f"🏆 <b>Voto: {deal.score}/10</b> — {badge}\n\n"
        f"💰 <b>Prezzo Articolo:</b> € {deal.price:.2f}\n"
        f"📦 <b>Spedizione:</b> {shipping_text}\n"
        f"🧾 <b>Costo Totale:</b> <b>€ {deal.total_price:.2f}</b>"
        f"{target_comparison}\n"
        f"{condition_section}\n\n"
        f"🏪 <b>Piattaforma:</b> {source_str}\n"
        f"📍 <b>Luogo:</b> {safe_location}\n"
    )
    return text


def get_deal_keyboard(deal_url: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔗 Vai all'Annuncio", url=deal_url)]
    ]
    return InlineKeyboardMarkup(buttons)
