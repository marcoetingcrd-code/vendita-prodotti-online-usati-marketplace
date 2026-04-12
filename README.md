# Unified Marketplace Hub

CRM operativo per la vendita di prodotti usati su marketplace multipli. Interfaccia primaria via Telegram Bot.

## Features

- **Telegram Bot** — Interfaccia principale: invia foto → ricevi scheda prodotto con AI
- **Gemini AI** — Riconoscimento oggetti, generazione descrizioni multi-piattaforma
- **Image Processing** — Rimozione sfondo automatica, crop, resize per piattaforma
- **Multi-utente** — Supporto N proprietari con notifiche real-time
- **Copy-Paste Kit** — Annunci pronti per Subito.it, eBay, Vinted
- **API REST** — FastAPI con docs automatiche su `/docs`

## Setup

### 1. Clona il repo
```bash
git clone https://github.com/marcoetingcrd-code/vendita-prodotti-online-usati-marketplace.git
cd vendita-prodotti-online-usati-marketplace
```

### 2. Configura .env
```bash
cp .env.example .env
# Modifica .env con le tue API keys
```

### 3. Avvia con Docker
```bash
docker-compose up -d
```

### 4. Oppure senza Docker
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Comandi Telegram Bot

| Comando | Descrizione |
|---------|-------------|
| `/start` | Menu principale |
| `/nuovo` | Aggiungi prodotto (seleziona owner → invia foto) |
| `/lista` | Mostra prodotti attivi |
| `/venduto <id> <prezzo>` | Segna come venduto |
| `/prezzo <id> <prezzo>` | Aggiorna prezzo |
| `/stats` | Statistiche vendite |

## API Endpoints

- `GET /docs` — Swagger UI
- `GET /api/products` — Lista prodotti
- `POST /api/products` — Crea prodotto
- `POST /api/products/{id}/upload` — Carica foto
- `POST /api/products/{id}/analyze` — Analisi AI
- `POST /api/products/{id}/generate-descriptions` — Genera annunci
- `POST /api/products/{id}/sold` — Segna venduto
- `GET /api/owners` — Lista proprietari
- `POST /api/owners` — Registra proprietario
- `GET /api/stats` — Statistiche

## Deploy su VPS

```bash
ssh root@165.245.222.192
git clone https://github.com/marcoetingcrd-code/vendita-prodotti-online-usati-marketplace.git
cd vendita-prodotti-online-usati-marketplace
cp .env.example .env
nano .env  # inserisci le tue API keys
docker-compose up -d
```

## Stack

- **Backend:** Python 3.12 + FastAPI
- **Database:** SQLite (MVP) → PostgreSQL (scaling)
- **AI:** Google Gemini 2.0 Flash
- **Immagini:** rembg + Pillow
- **Bot:** python-telegram-bot
- **Deploy:** Docker + DigitalOcean VPS
