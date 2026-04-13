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


async def analyze_product_image(image_path: str) -> dict:
    """Analizza un'immagine prodotto con Gemini Vision.
    Restituisce: oggetto riconosciuto, categoria, condizione, dimensioni stimate, prezzo suggerito."""
    _ensure_configured()

    p = Path(image_path)
    full_path = p if p.is_absolute() else (BASE_DIR / p).resolve()
    img_bytes = full_path.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode()
    mime = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"

    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = """Analizza questa foto di un oggetto in vendita su un marketplace dell'usato.
Rispondi SOLO con un JSON valido (senza markdown, senza ```), con questi campi:
{
  "object": "nome dell'oggetto identificato",
  "category": "categoria merceologica (Arredamento, Elettronica, Abbigliamento, Sport, Casa, Altro)",
  "condition": "nuovo | come_nuovo | buono | usato | difettoso",
  "condition_score": 1-5,
  "defects": "eventuali difetti visibili o null",
  "dimensions_estimate": "dimensioni stimate o null",
  "materials": "materiali identificati o null",
  "suggested_price_eur": prezzo suggerito numerico,
  "confidence": 0.0-1.0,
  "key_features": ["feature1", "feature2"]
}"""

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
