import re
from typing import List, Dict, Tuple, Optional, Any
from scrapers.base import DealItem
from core.config import settings


class DealAnalyzer:
    """
    Analizzatore semantico per rilevare danni, difetti, condizioni di usura o pari al nuovo
    sia dal titolo che dalla descrizione, calcolando poi un voto di convenienza da 1.0 a 10.0.
    """

    # Negazioni comuni che annullano il significato di difetto (es. "senza graffi", "nessun difetto")
    NEGATION_PATTERNS = [
        r'\b(?:senza|nessun|nessuna|nessuni|zero|no|non ha|non presenta|privo di|priva di)\s+([a-zA-Z0-9_\s]{1,25})',
        r'\b(?:senza alcun|senza alcuna)\s+([a-zA-Z0-9_\s]{1,25})',
        r'\b(?:mai subito|mai rotto|mai caduto|mai bagnato)\b'
    ]

    # Parole che indicano accessori, cover o sole scatole (evita falsi positivi a basso costo)
    ACCESSORY_KEYWORDS = [
        "cover", "covers", "custodia", "custodie", "funda", "fundas", "case", "cases", "housse", "coque",
        "pellicola", "pellicole", "vetro temperato", "vetro protettivo", "screen protector",
        "scatola vuota", "solo scatola", "only box", "empty box", "boite vide",
        "cavo ricarica", "cavo usb", "cavo lightning", "adattatore", "adattatori", "docking station",
        "solo gioco", "solo cartuccia", "cartuccia", "cartucce", "gioco per", "giochi per",
        "grip", "pennino", "stylus", "memory card", "scheda sd"
    ]

    def __init__(self):
        self.categories = settings.damage_categories

    def is_negated(self, text: str, keyword: str) -> bool:
        """Verifica se la parola chiave è preceduta da una negazione (es. 'senza graffi')."""
        lower_text = text.lower()
        keyword_clean = keyword.lower()

        for pattern in self.NEGATION_PATTERNS:
            matches = re.finditer(pattern, lower_text)
            for m in matches:
                negated_segment = m.group(0)
                if keyword_clean in negated_segment:
                    return True
        return False

    def detect_conditions(self, item: DealItem) -> Tuple[List[str], str, float, float]:
        """
        Scansiona titolo e descrizione alla ricerca di danni o condizioni eccellenti.
        Ritorna:
        - lista etichette/difetti trovati
        - severità complessiva ('CRITICAL', 'MODERATE', 'MINOR', 'MINT', 'NONE')
        - penalità totale da sottrarre allo score
        - bonus totale da aggiungere allo score
        """
        combined_text = f"{item.title} {item.description} {item.condition_text}".lower()
        found_defects = []
        labels = []
        total_penalty = 0.0
        total_bonus = 0.0
        highest_severity = "NONE"

        # 1. Controllo Difetti Critici (Gravi / Per ricambi)
        critical_cat = self.categories.get("critical")
        if critical_cat:
            for kw in critical_cat.keywords:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, combined_text):
                    if not self.is_negated(combined_text, kw):
                        found_defects.append(kw)
                        if critical_cat.label not in labels:
                            labels.append(critical_cat.label)
                        total_penalty = max(total_penalty, critical_cat.penalty)
                        highest_severity = "CRITICAL"

        # 2. Controllo Difetti Riparabili (Tasti, analogici, pulizia contatti, batteria, scocca)
        repairable_cat = self.categories.get("repairable")
        if repairable_cat and highest_severity != "CRITICAL":
            for kw in repairable_cat.keywords:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, combined_text):
                    if not self.is_negated(combined_text, kw):
                        found_defects.append(kw)
                        if repairable_cat.label not in labels:
                            labels.append(repairable_cat.label)
                        total_penalty = max(total_penalty, repairable_cat.penalty)
                        if highest_severity in ("NONE", "MINOR"):
                            highest_severity = "REPAIRABLE"

        # 3. Controllo Difetti Moderati (Crepe, problemi display touch, ammaccature)
        if highest_severity not in ("CRITICAL", "MODERATE"):
            moderate_cat = self.categories.get("moderate")
            if moderate_cat:
                for kw in moderate_cat.keywords:
                    pattern = r'\b' + re.escape(kw) + r'\b'
                    if re.search(pattern, combined_text):
                        if not self.is_negated(combined_text, kw):
                            found_defects.append(kw)
                            if moderate_cat.label not in labels:
                                labels.append(moderate_cat.label)
                            total_penalty = max(total_penalty, moderate_cat.penalty)
                            highest_severity = "MODERATE"

        # 3. Controllo Segni di Usura Minori
        if highest_severity in ("NONE", "MODERATE"):
            minor_cat = self.categories.get("minor_wear")
            if minor_cat:
                for kw in minor_cat.keywords:
                    pattern = r'\b' + re.escape(kw) + r'\b'
                    if re.search(pattern, combined_text):
                        if not self.is_negated(combined_text, kw):
                            found_defects.append(kw)
                            if minor_cat.label not in labels:
                                labels.append(minor_cat.label)
                            total_penalty += minor_cat.penalty
                            if highest_severity == "NONE":
                                highest_severity = "MINOR"

        # 4. Controllo Condizioni Pari al Nuovo o Sigillato (Bonus)
        mint_cat = self.categories.get("mint_or_new")
        if mint_cat and highest_severity not in ("CRITICAL", "MODERATE"):
            for kw in mint_cat.keywords:
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, combined_text):
                    if not self.is_negated(combined_text, kw):
                        if mint_cat.label not in labels:
                            labels.append(mint_cat.label)
                        total_bonus += mint_cat.bonus
                        if highest_severity == "NONE":
                            highest_severity = "MINT"
                        break  # Un solo bonus mint è sufficiente

        return labels, highest_severity, total_penalty, total_bonus

    # Prefissi ammessi per una vera console (il titolo deve iniziare con uno di questi)
    CONSOLE_START_PATTERN = re.compile(
        r'^(?:console\b|nintendo\b|new\s+nintendo\b|new\s*3ds\b|new\s*2ds\b|3ds\b|2ds\b|ps\s*vita\b|psvita\b|playstation\s+vita\b|sony\s+ps\s*vita\b|sony\s+playstation\s+vita\b|sony\s+psvita\b|pch-\d+|lotto\s+console\b)',
        re.IGNORECASE
    )

    # Parole che indicano che NON è una console anche se contiene il nome console (scatole vuote, schede madri, cover plate, ecc.)
    ACCESSORY_DISQUALIFIERS = re.compile(
        r'\b(?:bo[iî]te\s+vide|scatola\s+vuota|empty\s+box|caja\s+vac[ií]a|solo\s+scatola|bo[iî]te\s+originale|motherboard|scheda\s+madre|carte\s+m[eè]re|placa\s+base|faceplate|cover\s+plate|plate\s+pour|piastra|alimentatore|caricabatterie|charger|chargeur|netzteil|custodia|funda|housse|pochette|cavo|cable|kabel|pennino|stylus|protector|pellicola|vetro\s+temperato|solo\s+gioco|solo\s+cartuccia|lotto\s+videogiochi|lotto\s+giochi|lot\s+de\s+jeux|lot\s+jeux|lote\s+juegos)\b',
        re.IGNORECASE
    )

    # Termini che indicano che è un videogioco
    GAME_INDICATORS = re.compile(
        r'\b(?:videogioco|videogiochi|videgame|videogames|jeu\s+vid[eé]o|jeux\s+vid[eé]o|videojuego|videojuegos|cartuccia|cartucce|cartridge|cib|loose|steelbook)\b',
        re.IGNORECASE
    )

    GAME_FRANCHISES = r'\b(?:pokemon|pok[eé]mon|mario|zelda|luigi|yo-kai|yokai|spider-?man|last of us|god of war|gran turismo|demon slayer|one punch|fist of the north star|attack on titan|a\.o\.t|inazuma|monster hunter|fifa|pes|call of duty|gta|grand theft auto|assassin|resident evil|final fantasy|dragon quest|kingdom hearts|kirby|metroid|fire emblem|layton|sonic|crash bandicoot|spyro|bionicle|ratatouille|star wars|dmc|devil may cry|tomodachi|disney|naruto|one piece|dragon ball|persona|uncharted|killzone|wipeout)\b'

    def is_accessory_or_game(self, title: str, price: float, query: str = "", ai_rules: Optional[Dict[str, Any]] = None) -> bool:
        """Verifica se l'annuncio riguarda un gioco, accessorio o prodotto non pertinente, supportando filtri AI o regole console."""
        lower_title = title.strip().lower()
        q = query.lower()

        # 1. Se sono presenti regole generate dall'AI (Gemini) per questa ricerca, applicale
        if ai_rules:
            # Prezzo minimo plausibile determinato da Gemini
            min_ai_price = float(ai_rules.get("min_price", 0.0))
            if min_ai_price > 0 and price < min_ai_price:
                return True

            # Parole chiave di esclusione da Gemini (cover, ricambi, scatole, ecc.)
            excluded_words = ai_rules.get("excluded_keywords", [])
            for kw in excluded_words:
                if kw and re.search(r'\b' + re.escape(kw.lower().strip()) + r'\b', lower_title):
                    return True

            # Se ci sono parole chiave obbligatorie (almeno una deve essere presente)
            req_any = ai_rules.get("required_any_keywords", [])
            if req_any and not any(r.lower() in lower_title for r in req_any):
                return True

        # 2. Controllo accessori generici sempre valido
        if self.is_accessory(title):
            return True

        # 3. Controllo specifico per console retrogaming
        is_console_query = any(k in q for k in ("3ds", "2ds", "vita", "psvita", "console", "switch", "ps5", "playstation"))
        if not is_console_query:
            return False

        # Modello esatto: evita che Nintendo DS Lite venga scambiato per 3DS
        if "3ds" in q and not re.search(r'\b(?:3ds|3dsxl)\b', lower_title):
            return True
        if "2ds" in q and not re.search(r'\b(?:2ds|2dsxl)\b', lower_title):
            return True
        if ("vita" in q or "psvita" in q) and not re.search(r'\b(?:ps\s*vita|psvita|playstation\s+vita|pch-\d+)\b', lower_title):
            return True

        # Prezzo minimo console: sotto i 45€ è al 99.9% un singolo gioco o accessorio
        if price < 45.0:
            return True

        # Controllo parole disqualificanti (scatole vuote, schede madri, cover plate, ecc.)
        if self.ACCESSORY_DISQUALIFIERS.search(lower_title):
            return True

        # Controllo indicatori generici di videogiochi
        if self.GAME_INDICATORS.search(lower_title):
            if not any(p in lower_title for p in ("console con", "console +", "console e ", "pack console", "bundle console")):
                return True

        # La console DEVE iniziare con il nome della console o "Console ..."
        if not self.CONSOLE_START_PATTERN.search(lower_title):
            return True

        # Se menziona franchise di videogiochi senza essere un bundle esplicito
        if re.search(self.GAME_FRANCHISES, lower_title):
            if not any(p in lower_title for p in ("console con", "console +", "console e ", "pack console", "bundle console")):
                if "console" not in lower_title:
                    return True

        return False

    def is_accessory(self, text: str) -> bool:
        """Verifica se l'annuncio riguarda solo un accessorio (es. cover, pellicola, scatola vuota)."""
        lower = text.lower()
        for kw in self.ACCESSORY_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', lower):
                return True
        return False

    def calculate_score(
        self,
        item: DealItem,
        target_price: Optional[float] = None,
        market_median_price: Optional[float] = None,
        min_price: Optional[float] = None,
        ai_rules: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calcola il voto da 1.0 a 10.0 sulla qualità complessiva dell'offerta.
        """
        # Assicuriamo che la spedizione sia calcolata
        if item.is_international and item.shipping_cost == 0.0:
            # Stima spedizione internazionale se non dichiarata
            item.shipping_cost = settings.default_estimated_shipping_international
            item.total_price = round(item.price + item.shipping_cost, 2)
        elif item.total_price <= 0:
            item.total_price = round(item.price + item.shipping_cost, 2)

        total_price = item.total_price
        if total_price <= 0:
            return 1.0

        # Prezzo minimo da ai_rules se disponibile
        effective_min_price = min_price
        if ai_rules and ai_rules.get("min_price"):
            effective_min_price = max(effective_min_price or 0.0, float(ai_rules["min_price"]))

        # Filtro soglia minima
        if effective_min_price and total_price < effective_min_price:
            item.score = 1.0
            item.defect_severity = "ACCESSORY"
            item.defect_labels = ["📦 PREZZO SOSPETTO / ACCESSORIO"]
            item.score_breakdown = {"reason": "prezzo troppo basso per essere il prodotto intero"}
            return 1.0

        # Controllo se è solo un gioco o un accessorio (con ai_rules)
        if self.is_accessory_or_game(item.title, price=total_price, query=item.search_query, ai_rules=ai_rules):
            item.score = 1.0
            item.defect_severity = "ACCESSORY"
            item.defect_labels = ["📦 ACCESSORIO / GIOCO / PARTE DI RICAMBIO"]
            item.score_breakdown = {"reason": "rilevato come accessorio, gioco o ricambio"}
            return 1.0

        # Analisi semantica dei difetti nella descrizione e nel titolo
        labels, severity, penalty, bonus = self.detect_conditions(item)

        item.defect_labels = labels
        item.defect_severity = severity

        # Prezzo di riferimento: target_price se impostato, altrimenti mediana di mercato
        reference_price = target_price or market_median_price

        if reference_price and reference_price > 0:
            ratio = total_price / reference_price
            if ratio <= 0.40:
                base_score = 10.0
            elif ratio <= 0.60:
                base_score = 9.5
            elif ratio <= 0.80:
                base_score = 9.0
            elif ratio <= 1.00:
                base_score = 8.0 - (ratio - 0.80) * 5.0
            elif ratio <= 1.20:
                base_score = 7.0 - (ratio - 1.00) * 10.0
            else:
                base_score = max(1.0, 3.5 - (ratio - 1.20) * 5.0)
        else:
            base_score = 6.5

        final_score = base_score - penalty + bonus

        if severity == "CRITICAL":
            final_score = min(final_score, 3.5)

        final_score = max(1.0, min(10.0, final_score))
        final_score = round(final_score, 1)

        item.score = final_score
        item.score_breakdown = {
            "base_score": round(base_score, 1),
            "penalty": penalty,
            "bonus": bonus,
            "severity": severity,
            "reference_price": reference_price,
            "total_price": total_price,
            "shipping_cost": item.shipping_cost
        }

        return final_score

    def analyze_batch(
        self,
        items: List[DealItem],
        target_price: Optional[float] = None,
        min_price: Optional[float] = None,
        ai_rules: Optional[Dict[str, Any]] = None
    ) -> List[DealItem]:
        """
        Analizza un insieme di offerte calcolando la mediana dei prezzi e assegnando i voti.
        """
        if not items:
            return []

        valid_prices = sorted([it.total_price for it in items if it.total_price > 0])
        market_median = None
        if valid_prices:
            mid = len(valid_prices) // 2
            market_median = valid_prices[mid] if len(valid_prices) % 2 != 0 else (valid_prices[mid - 1] + valid_prices[mid]) / 2.0

        for item in items:
            self.calculate_score(
                item,
                target_price=target_price,
                market_median_price=market_median,
                min_price=min_price,
                ai_rules=ai_rules
            )

        items.sort(key=lambda x: x.score, reverse=True)
        return items


analyzer = DealAnalyzer()
