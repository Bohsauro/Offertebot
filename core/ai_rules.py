import json
import logging
import re
from typing import Dict, Any, Optional
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-3.6-flash"

SYSTEM_INSTRUCTION = """
Sei un assistente esperto di e-commerce, compravendita di usato e tecnologia.
L'utente vuole monitorare offerte e annunci di compravendita (su Subito, Vinted, eBay) per un determinato prodotto/query di ricerca.
Il tuo compito è generare filtri semantici per escludere accessori, cover, scatole vuote, pezzi di ricambio o singoli giochi/gadget, e calcolare un prezzo minimo plausibile sotto il quale l'annuncio è quasi certamente un accessorio o un inganno.

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido (senza markdown o backtick `json) con questa struttura esatta:
{
    "category": "string (es. console, smartphone, gpu, camera, audio, tablet, shoes, generic)",
    "canonical_name": "string (nome pulito del prodotto)",
    "min_price": float (prezzo minimo sotto il quale e quasi certamente un accessorio, cavo, cover o pezzo di ricambio),
    "excluded_keywords": ["lista", "di", "parole", "o", "frasi", "di", "accessori", "o", "parti", "da", "escludere"],
    "required_any_keywords": ["parole", "chiave", "di", "cui", "almeno", "una", "deve", "comparire", "nel", "titolo"]
}
"""

async def generate_search_rules(query: str, target_price: Optional[float] = None) -> Dict[str, Any]:
    """Interroga Gemini per generare regole personalizzate di filtraggio per la query specificata."""
    api_key = settings.gemini_api_key
    if not api_key:
        logger.warning("GEMINI_API_KEY non configurata. Uso regole euristiche di default.")
        return _fallback_rules(query, target_price)

    prompt = f"Query di ricerca: '{query}'"
    if target_price:
        prompt += f", Prezzo target dell'utente: € {target_price:.2f}"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                rules = json.loads(text)
                logger.info(f"[Gemini AI] Regole generate con successo per '{query}': {rules.get('category')} (Min: €{rules.get('min_price')})")
                return rules
            else:
                logger.warning(f"[Gemini AI] Errore API ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[Gemini AI] Eccezione durante la chiamata: {e}")

    return _fallback_rules(query, target_price)

def _fallback_rules(query: str, target_price: Optional[float] = None) -> Dict[str, Any]:
    """Regole euristiche veloci in assenza di risposta dell'LLM."""
    q_lower = query.lower()
    min_p = (target_price * 0.30) if target_price and target_price >= 40 else 25.0
    
    excluded = [
        "scatola vuota", "empty box", "boite vide", "solo scatola",
        "custodia", "cover", "pellicola", "vetro temperato", "cavo",
        "alimentatore", "caricatore", "pezzi di ricambio", "solo pezzi"
    ]
    if any(k in q_lower for k in ("3ds", "2ds", "vita", "psvita", "switch", "playstation", "xbox", "console")):
        excluded.extend(["gioco", "giochi", "solo gioco", "cartuccia", "steelbook", "jeu", "jeux", "juego"])

    return {
        "category": "generic",
        "canonical_name": query,
        "min_price": round(min_p, 2),
        "excluded_keywords": excluded,
        "required_any_keywords": [word for word in query.split() if len(word) > 2]
    }
