import json
import uuid
import logging
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
from app.config import GEMINI_API_KEY, BASE_DIR, PROCESSED_DIR

logger = logging.getLogger(__name__)

_client = None
TEXT_MODEL = "gemini-2.0-flash"
IMAGE_MODEL = "gemini-2.5-flash-image"


def _get_client():
    global _client
    if _client is None and GEMINI_API_KEY:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _load_image(image_path: str) -> Image.Image:
    p = Path(image_path)
    full_path = p if p.is_absolute() else (BASE_DIR / p).resolve()
    return Image.open(str(full_path))


def _extract_text(response) -> str:
    for part in response.candidates[0].content.parts:
        if part.text:
            return part.text
    return ""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


async def analyze_product_image(image_path: str, user_description: str = "") -> dict:
    """Analizza un'immagine prodotto con Gemini Vision.
    Restituisce: oggetto riconosciuto, categoria, condizione, dimensioni stimate, prezzo suggerito."""
    client = _get_client()
    img = _load_image(image_path)

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
  "questions": ["domanda 1 per ottenere info mancanti", "domanda 2", "domanda 3"]
}}

Il campo "questions" deve contenere 2-4 domande utili da fare all'utente per completare l'annuncio (es: marca, difetti nascosti, anno acquisto, motivo vendita, disponibilità spedizione)."""

    response = await client.aio.models.generate_content(
        model=TEXT_MODEL,
        contents=[prompt, img],
    )

    text = _extract_text(response)
    return _parse_json(text)


async def generate_product_image(image_paths: list[str], analysis: dict, user_description: str = "") -> str | None:
    """Genera un'immagine professionale del prodotto usando Gemini Image Generation.
    Combina le foto fornite, rimuove sfondo, ricostruisce il prodotto completo su sfondo neutro.
    Restituisce il path dell'immagine salvata o None se fallisce."""
    client = _get_client()

    images = []
    for ip in image_paths[:4]:
        try:
            images.append(_load_image(ip))
        except Exception as e:
            logger.warning(f"Errore caricamento immagine {ip}: {e}")

    if not images:
        return None

    obj_name = analysis.get("object", "prodotto")
    materials = analysis.get("materials", "")
    color = analysis.get("color", "")
    dims = analysis.get("dimensions_estimate", "")

    extra_context = ""
    if user_description:
        extra_context = f"\nL'utente ha descritto il prodotto come: \"{user_description}\""

    multi_photo_note = ""
    if len(images) > 1:
        multi_photo_note = f"\nHo fornito {len(images)} foto dello stesso prodotto da angolazioni diverse. Usale tutte per ricostruire il prodotto completo e preciso."

    prompt = f"""Sei un fotografo professionista di e-commerce. Genera un'immagine professionale di questo prodotto per un annuncio di vendita online.

PRODOTTO: {obj_name}
MATERIALI: {materials or 'vedi dalle foto'}
COLORE: {color or 'vedi dalle foto'}
DIMENSIONI: {dims or 'stima dalle foto'}{extra_context}{multi_photo_note}

ISTRUZIONI CRITICHE:
1. RICONOSCI il prodotto nelle foto e GENERA un'immagine pulita professionale
2. MANTIENI tutti i dettagli reali: texture del legno, colore del metallo, usura naturale, venature, graffi se presenti
3. SFONDO: grigio chiaro neutro da studio fotografico (#F5F5F5)
4. ANGOLAZIONE: 3/4 prospettica, come foto da catalogo IKEA
5. Il prodotto deve essere mostrato COMPLETO e ASSEMBLATO anche se le foto lo mostrano smontato o da angolazioni parziali
6. ILLUMINAZIONE: morbida e uniforme, no ombre dure
7. NON inventare dettagli che non esistono nelle foto originali
8. NON aggiungere testo, watermark, prezzi o etichette sull'immagine
9. L'immagine deve essere FOTOREALISTICA, non un rendering 3D o un disegno"""

    try:
        contents = [prompt] + images
        response = await client.aio.models.generate_content(
            model=IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                filename = f"{uuid.uuid4().hex}_ai_gen.png"
                output_path = (PROCESSED_DIR / filename).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)

                img_data = part.inline_data.data
                with open(str(output_path), "wb") as f:
                    f.write(img_data)

                return str(output_path.relative_to(BASE_DIR.resolve()))

    except Exception as e:
        logger.error(f"Errore generazione immagine Gemini: {e}")

    return None


async def refine_product_image(
    original_image_paths: list[str],
    current_generated_path: str | None,
    refinement_request: str,
    analysis: dict,
) -> dict:
    """Raffina l'immagine generata basandosi sulle istruzioni dell'utente.
    Restituisce {"image_path": str|None, "text": str}."""
    client = _get_client()

    images = []
    for ip in original_image_paths[:4]:
        try:
            images.append(_load_image(ip))
        except Exception:
            pass

    if current_generated_path:
        try:
            images.append(_load_image(current_generated_path))
        except Exception:
            pass

    obj_name = analysis.get("object", "prodotto")

    prompt = f"""Sei un fotografo professionista di e-commerce. Stai lavorando alla foto di un prodotto: {obj_name}.

L'utente ha richiesto questa modifica sull'immagine generata:
"{refinement_request}"

ISTRUZIONI:
1. Applica la modifica richiesta mantenendo la qualità professionale
2. MANTIENI tutti i dettagli reali: texture, colore, usura
3. SFONDO: grigio chiaro neutro (#F5F5F5) salvo diversa indicazione
4. NON aggiungere testo, watermark, prezzi sull'immagine
5. L'immagine deve essere FOTOREALISTICA
6. Se la richiesta è impossibile, genera comunque la migliore versione possibile e spiega nel testo

Genera l'immagine modificata."""

    result = {"image_path": None, "text": ""}

    try:
        contents = [prompt] + images
        response = await client.aio.models.generate_content(
            model=IMAGE_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.text:
                result["text"] = part.text
            elif part.inline_data is not None:
                filename = f"{uuid.uuid4().hex}_ai_refined.png"
                output_path = (PROCESSED_DIR / filename).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(str(output_path), "wb") as f:
                    f.write(part.inline_data.data)

                result["image_path"] = str(output_path.relative_to(BASE_DIR.resolve()))

    except Exception as e:
        logger.error(f"Errore raffinamento immagine: {e}")
        result["text"] = f"Errore durante il raffinamento: {str(e)}"

    return result


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
    """Genera descrizioni ottimizzate per Subito, eBay, Vinted, Facebook, Vestiaire."""
    client = _get_client()

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

    response = await client.aio.models.generate_content(
        model=TEXT_MODEL,
        contents=[prompt],
    )

    text = _extract_text(response)
    return _parse_json(text)
