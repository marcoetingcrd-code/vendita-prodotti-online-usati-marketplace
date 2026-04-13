import json
import base64
from pathlib import Path
import google.generativeai as genai
from app.config import GEMINI_API_KEY, BASE_DIR

_configured = False


def _ensure_configured():
    global _configured
    if not _configured and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        _configured = True


async def analyze_product_image(image_path: str, user_description: str = "") -> dict:
    """Analizza un'immagine prodotto con Gemini Vision.
    Restituisce: oggetto riconosciuto, categoria, condizione, dimensioni stimate, prezzo suggerito."""
    _ensure_configured()

    p = Path(image_path)
    full_path = p if p.is_absolute() else (BASE_DIR / p).resolve()
    img_bytes = full_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()
    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

    model = genai.GenerativeModel("gemini-2.0-flash")

    user_hint = f"\n\nL'utente ha scritto: \"{user_description}\"" if user_description else ""

    prompt = f"""Sei un esperto di marketplace dell'usato in Italia. Analizza questa foto per identificare il PRODOTTO IN VENDITA.

ATTENZIONE:
- Identifica l'OGGETTO da vendere, NON le persone nella foto. Le persone possono essere presenti per scala/contesto ma il prodotto è la cosa da vendere.
- Se ci sono persone sedute su una panchina, il prodotto è la PANCHINA, non le persone.
- Se qualcuno indossa un capo, il prodotto è il CAPO DI ABBIGLIAMENTO.
- Concentrati sull'oggetto/mobile/prodotto principale.{user_hint}

Per il PREZZO SUGGERITO:
- Cerca di stimare un prezzo realistico per il mercato dell'usato italiano (Subito, eBay, Vinted, Facebook Marketplace)
- Considera: marca, condizione, età stimata, domanda tipica, stagionalità
- Dai anche un range (prezzo_min e prezzo_max)

Per lo SCONTORNAMENTO:
- Decidi se ha senso scontornare la prima foto (rimuovere sfondo per foto pulita prodotto)
- Rispondi "yes" se il prodotto è un oggetto isolabile (borsa, scarpe, sedia, elettronica...)
- Rispondi "no" se il prodotto è ambientato e lo scontornamento rovinerebbe la foto (stanza, giardino con panchina e persone, cucina installata...)

Rispondi SOLO con un JSON valido (senza markdown, senza ```), con questi campi:
{{
  "object": "nome preciso dell'oggetto in vendita",
  "category": "categoria (Arredamento, Elettronica, Abbigliamento, Sport, Casa, Giardino, Altro)",
  "condition": "nuovo | come_nuovo | buono | usato | difettoso",
  "condition_score": 1-5,
  "defects": "eventuali difetti visibili o null",
  "dimensions_estimate": "dimensioni stimate o null",
  "materials": "materiali identificati o null",
  "brand": "marca se riconoscibile o null",
  "color": "colore principale o null",
  "suggested_price_eur": prezzo suggerito numerico (migliore stima),
  "price_range_min": prezzo minimo ragionevole,
  "price_range_max": prezzo massimo ragionevole,
  "confidence": 0.0-1.0,
  "key_features": ["feature1", "feature2", "feature3"],
  "should_remove_bg": true o false,
  "questions": ["domanda 1 per ottenere info mancanti", "domanda 2", "domanda 3"]
}}

Il campo "questions" deve contenere 2-4 domande utili da fare all'utente per completare l'annuncio (es: marca, difetti nascosti, anno acquisto, motivo vendita, disponibilità spedizione)."""

    response = await model.generate_content_async([
        prompt,
        {"mime_type": mime, "data": img_b64}
    ])

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    return json.loads(text)


async def generate_listing_descriptions(
    object_name: str,
    category: str,
    condition: str,
    defects: str | None,
    dimensions: str | None,
    materials: str | None,
    features: list[str] | None,
    price: float | None,
    location: str | None = None,
) -> dict:
    """Genera descrizioni ottimizzate per Subito, eBay e Vinted."""
    _ensure_configured()

    model = genai.GenerativeModel("gemini-2.0-flash")

    details = f"""Oggetto: {object_name}
Categoria: {category}
Condizione: {condition}
Difetti: {defects or 'Nessuno'}
Dimensioni: {dimensions or 'Non specificate'}
Materiali: {materials or 'Non specificati'}
Caratteristiche: {', '.join(features) if features else 'N/A'}
Prezzo: {'€' + str(price) if price else 'Da definire'}
Zona ritiro: {location or 'Da specificare'}"""

    prompt = f"""Sei un esperto di annunci per marketplace dell'usato in Italia.
Genera 5 versioni dell'annuncio per lo stesso prodotto, ciascuna ottimizzata per la piattaforma.

DATI PRODOTTO:
{details}

Rispondi SOLO con un JSON valido (senza markdown), con questa struttura:
{{
  "title": "titolo accattivante generale (max 60 caratteri)",
  "subito": {{
    "title": "titolo per Subito.it (max 50 char, diretto, pratico)",
    "description": "descrizione per Subito.it (tono diretto, prezzo in evidenza, zona ritiro, max 800 char)"
  }},
  "ebay": {{
    "title": "titolo per eBay (max 80 char, dettagliato con keyword SEO)",
    "description": "descrizione per eBay (dettagliata, specifiche tecniche, condizioni precise, spedizione, max 1200 char)"
  }},
  "vinted": {{
    "title": "titolo per Vinted (max 50 char, casual, trendy)",
    "description": "descrizione per Vinted (tono casual, emotivo, hashtag alla fine, max 600 char)"
  }},
  "facebook": {{
    "title": "titolo per Facebook Marketplace (max 60 char, diretto)",
    "description": "descrizione per Facebook Marketplace (colloquiale, disponibilità ritiro, max 600 char)"
  }},
  "vestiaire": {{
    "title": "titolo per Vestiaire Collective (max 60 char, elegante, luxury-oriented)",
    "description": "descrizione per Vestiaire Collective (tono curato, focus su brand/materiali/condizioni, autenticità, max 800 char)"
  }}
}}"""

    response = await model.generate_content_async(prompt)

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]

    return json.loads(text)
