import sqlite3, re

# Prefissi ammessi per una vera console (il titolo deve iniziare con uno di questi)
CONSOLE_START_PATTERN = re.compile(
    r'^(?:console\b|nintendo\b|new\s+nintendo\b|new\s*3ds\b|new\s*2ds\b|3ds\b|2ds\b|ps\s*vita\b|psvita\b|playstation\s+vita\b|sony\s+ps\s*vita\b|sony\s+playstation\s+vita\b|sony\s+psvita\b|pch-\d+|lotto\s+console\b)',
    re.IGNORECASE
)

# Parole che indicano che NON e la console anche se inizia col nome console (es. scatola vuota, scheda madre, custodia)
ACCESSORY_DISQUALIFIERS = re.compile(
    r'\b(?:bo[iî]te\s+vide|scatola\s+vuota|empty\s+box|caja\s+vac[ií]a|solo\s+scatola|bo[iî]te\s+originale|motherboard|scheda\s+madre|carte\s+m[eè]re|placa\s+base|faceplate|cover\s+plate|plate\s+pour|piastra|alimentatore|caricabatterie|charger|chargeur|netzteil|custodia|funda|housse|pochette|cavo|cable|kabel|pennino|stylus|protector|pellicola|vetro\s+temperato|solo\s+gioco|solo\s+cartuccia|lotto\s+videogiochi|lotto\s+giochi|lot\s+de\s+jeux|lot\s+jeux|lote\s+juegos)\b',
    re.IGNORECASE
)

# Termini che indicano che e un gioco
GAME_INDICATORS = re.compile(
    r'\b(?:videogioco|videogiochi|videogame|videogames|jeu\s+vid[eé]o|jeux\s+vid[eé]o|videojuego|videojuegos|cartuccia|cartucce|cartridge|cib|loose|steelbook)\b',
    re.IGNORECASE
)

def is_real_console(title: str, price: float, query: str = "") -> tuple[bool, str]:
    title_clean = title.strip()

    # 1. Prezzo minimo per console (almeno 45 euro)
    if price < 45.0:
        return False, "prezzo < 45 euro"

    # 2. Controllo parole disqualificanti (scatole vuote, schede madri, cover, alimentatori)
    if ACCESSORY_DISQUALIFIERS.search(title_clean):
        return False, "accessorio / scatola / ricambio"

    # 3. Controllo giochi
    if GAME_INDICATORS.search(title_clean):
        if not re.search(r'\b(?:console\s+\+|console\s+con|console\s+e\b|pack\s+console|bundle\s+console)\b', title_clean, re.I):
            return False, "gioco / cartuccia"

    # 4. DEVE iniziare con il nome della console o 'Console ...'
    if not CONSOLE_START_PATTERN.search(title_clean):
        return False, f"non inizia con console ('{title_clean}')"

    return True, "OK"
