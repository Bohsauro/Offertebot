# 🤖 OfferteBot — Telegram Deals Monitor & Analyzer

Bot Telegram avanzato progettato per girare su un server **Ubuntu Linux**, per monitorare offerte sia di prodotti **usati** che **nuovi** (Subito.it, Vinted, eBay, Wallapop).

Analizza automaticamente titolo e descrizione per rilevare **danni, difetti, guasti o usura**, include le **spese di spedizione** nel conteggio totale e assegna un **voto oggettivo da 1.0 a 10.0** sulla convenienza dell'affare.

---

## 🌟 Caratteristiche Principali

- 💰 **Prezzo Totale Trasparente**: calcola sempre `Prezzo Articolo + Spese di Spedizione` (anche per spedizioni dall'estero o con stima forfettaria).
- 🔍 **Rilevamento Danni & Usura con NLP**:
  - **Danni Critici / Per Ricambi**: *"rotto"*, *"non funzionante"*, *"per parti"*, *"bloccato icloud"*, *"non si accende"* (penalità severa, max voto 3.5).
  - **Danni Moderati**: *"crepa"*, *"linee su schermo"*, *"batteria da sostituire"*, *"ammaccatura"*.
  - **Segni di Usura**: *"micrograffi"*, *"leggeri segni di utilizzo"*.
  - **Condizioni Ottime**: *"nuovo"*, *"sigillato"*, *"come nuovo"*, *"con scontrino/fattura"*.
  - **Filtro Anti-Cover/Accessori**: scarta annunci ingannevoli (es. cover o scatola vuota a 5€ quando cerchi un iPhone).
- 🏆 **Algoritmo di Rating da 1.0 a 10.0**:
  - Confronta il costo complessivo con il tuo budget target o con la mediana dei prezzi di mercato.
  - Sottrae punti in base alla gravità dei difetti e aggiunge bonus per prodotti sigillati.
- 🚨 **Notifiche & Consultazione**:
  - Alert istantaneo non appena esce una nuova offerta con voto $\ge$ soglia minima (es. 7.0/10).
  - Comandi on-demand per vedere in qualunque momento le migliori offerte o fare ricerche dal vivo.
- 💾 **Database SQLite persistente** con deduplicazione automatica (nessuna notifica duplicata).

---

## 📋 Comandi Telegram

| Comando | Descrizione |
|---|---|
| `/start` o `/help` | Guida rapida e spiegazione funzioni |
| `/cerca <prodotto> [budget]` | Esegue una ricerca dal vivo istantanea e mostra le top offerte con voto 1-10 |
| `/traccia <prodotto> [budget]` | Aggiunge un prodotto al monitoraggio automatico in background |
| `/mieicerche` | Elenca le ricerche attive con pulsanti per metterle in pausa o eliminarle |
| `/offerte [filtro]` | Mostra le migliori offerte attualmente salvate nel database |
| `/impostazioni` | Mostra intervallo di scansione, voto minimo per gli alert e filtri |

---

## 🚀 Guida all'Installazione su Ubuntu Server

### 1. Prerequisiti: Crea il tuo Bot su Telegram
1. Apri Telegram e avvia una chat con [@BotFather](https://t.me/BotFather).
2. Invia `/newbot` e segui le istruzioni per scegliere un nome e uno username.
3. BotFather ti fornirà il **token segreto** (es. `7123456789:AAH...`).
4. Apri una chat con [@userinfobot](https://t.me/userinfobot) su Telegram per ottenere il tuo **Chat ID** numerico.

---

### Metodo A: Installazione con Docker (Consigliato)

1. **Clona o copia la cartella del progetto sul tuo server Ubuntu**:
   ```bash
   cd /home/ubuntu
   git clone <tuo-repo> OfferteBot
   cd OfferteBot
   ```

2. **Crea il file di configurazione `.env`**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Inserisci il tuo `TELEGRAM_BOT_TOKEN` e il tuo `TELEGRAM_CHAT_ID`.

3. **Avvia il container con Docker Compose**:
   ```bash
   docker compose up -d --build
   ```

4. **Visualizza i log in tempo reale**:
   ```bash
   docker compose logs -f
   ```

---

### Metodo B: Installazione Nativa con Systemd su Ubuntu

1. **Installa Python 3.11 e venv**:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-venv python3-pip curl
   ```

2. **Prepara l'ambiente**:
   ```bash
   cd /home/ubuntu/OfferteBot
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

3. **Configura il file `.env`**:
   ```bash
   cp .env.example .env
   nano .env
   ```

4. **Test rapido da riga di comando** (verifica che lo scraping funzioni sul tuo server):
   ```bash
   ./venv/bin/python main.py --test
   ```

5. **Installa il servizio di sistema per tenerlo sempre attivo in background**:
   ```bash
   sudo cp offertebot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable offertebot
   sudo systemctl start offertebot
   ```

6. **Comandi utili per gestire il servizio**:
   ```bash
   # Controlla lo stato del bot
   sudo systemctl status offertebot

   # Visualizza i log in tempo reale
   journalctl -u offertebot -f

   # Riavvia il bot dopo modifiche a config.yaml o .env
   sudo systemctl restart offertebot
   ```

---

## ⚙️ Personalizzazione Avanzata (`config.yaml`)

Nel file `config.yaml` puoi:
- Personalizzare i termini del dizionario danni (parole chiave critiche, moderate, usura o pari al nuovo).
- Modificare i pesi delle penalità e dei bonus.
- Inserire prodotti predefiniti da monitorare al primo avvio.
