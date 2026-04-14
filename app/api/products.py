import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.product import Product, ProductImage, PriceHistory, ActivityLog, Publication
from app.models.owner import Owner
from app.models.event import Event
from app.services import gemini, image_processor
from app.services.notifications import notify_product_created, notify_product_sold

router = APIRouter(prefix="/api/products", tags=["products"])


class ProductCreate(BaseModel):
    owner_id: str
    title: str | None = None
    description_raw: str | None = None
    category: str | None = None
    condition: str | None = None
    price_initial: float | None = None
    pickup_location: str | None = None
    logistics_status: str | None = None
    measurements: str | None = None
    defects: str | None = None
    dimensions: str | None = None
    urgency: str = "low"
    notes: str | None = None


class ProductUpdate(BaseModel):
    title: str | None = None
    description_raw: str | None = None
    category: str | None = None
    condition: str | None = None
    price_initial: float | None = None
    price_listed: float | None = None
    status: str | None = None
    pickup_location: str | None = None
    logistics_status: str | None = None
    measurements: str | None = None
    defects: str | None = None
    dimensions: str | None = None
    urgency: str | None = None
    notes: str | None = None
    desc_subito: str | None = None
    desc_ebay: str | None = None
    desc_vinted: str | None = None
    desc_facebook: str | None = None
    desc_vestiaire: str | None = None
    platforms: list[str] | None = None
    platform_links: dict | None = None


class SoldRequest(BaseModel):
    price_sold: float


logger = logging.getLogger(__name__)


@router.post("/ai-draft")
async def ai_draft(
    files: list[UploadFile] = File(...),
    description: str = Form(""),
    owner_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Chat AI: riceve foto + testo, analizza, genera descrizioni per tutte le piattaforme."""
    owner = await db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(404, "Owner non trovato")

    # 1. Salva immagini originali
    image_paths = []
    for f in files:
        data = await f.read()
        ext = "." + (f.filename.rsplit(".", 1)[-1] if "." in (f.filename or "") else "jpg")
        original_path = image_processor.save_original(data, ext)
        image_paths.append(original_path)

    # 2. Analisi AI con Gemini Vision
    analysis = {}
    if image_paths:
        try:
            analysis = await gemini.analyze_product_image(image_paths[0], user_description=description)
        except Exception as e:
            logger.warning(f"Errore analisi Gemini: {e}")
            analysis = {
                "object": "Oggetto non riconosciuto",
                "category": "Altro",
                "condition": "buono",
                "condition_score": 3,
                "defects": None,
                "dimensions_estimate": None,
                "materials": None,
                "suggested_price_eur": None,
                "price_range_min": None,
                "price_range_max": None,
                "confidence": 0.0,
                "key_features": [],
                "questions": [],
            }

    # 3. Rimuovi sfondo con rembg (gratuito, locale)
    processed_path = None
    if image_paths:
        try:
            processed_path = image_processor.process_image(image_paths[0])
            logger.info("Sfondo rimosso con rembg")
        except Exception as e:
            logger.warning(f"Errore rembg: {e}")

    # 4. Genera descrizioni per tutte le piattaforme
    descriptions = {}
    try:
        combined_features = analysis.get("key_features", [])
        if description:
            combined_features.append(description)

        descriptions = await gemini.generate_listing_descriptions(
            object_name=analysis.get("object", "Oggetto"),
            category=analysis.get("category", "Altro"),
            condition=analysis.get("condition", "buono"),
            defects=analysis.get("defects"),
            dimensions=analysis.get("dimensions_estimate"),
            materials=analysis.get("materials"),
            features=combined_features,
            price=analysis.get("suggested_price_eur"),
            location=None,
        )
    except Exception as e:
        logger.warning(f"Errore generazione descrizioni: {e}")

    return {
        "image_paths": image_paths,
        "processed_path": processed_path,
        "analysis": analysis,
        "descriptions": descriptions,
        "owner_id": owner_id,
        "owner_name": owner.name,
    }


@router.post("/ai-refine-image")
async def ai_refine_image(
    refinement: str = Form(...),
    original_paths: str = Form(""),
    current_generated: str = Form(""),
    analysis_json: str = Form("{}"),
):
    """Raffina l'immagine AI generata con istruzioni dell'utente (es: 'togli il testo', 'aggiungi le gambe')."""
    import json as _json

    analysis = {}
    try:
        analysis = _json.loads(analysis_json)
    except Exception:
        pass

    orig_paths = [p.strip() for p in original_paths.split(",") if p.strip()]

    result = await gemini.refine_product_image(
        original_image_paths=orig_paths,
        current_generated_path=current_generated or None,
        refinement_request=refinement,
        analysis=analysis,
    )

    return {
        "processed_path": result.get("image_path"),
        "text": result.get("text", ""),
    }


@router.get("/")
async def list_products(
    owner_id: str | None = None,
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Product).order_by(Product.created_at.desc())
    if owner_id:
        query = query.where(Product.owner_id == owner_id)
    if status:
        query = query.where(Product.status == status)
    if search:
        query = query.where(Product.title.ilike(f"%{search}%"))
    result = await db.execute(query)
    products = result.scalars().all()
    return [_serialize_product(p) for p in products]


@router.get("/{product_id}")
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)
    return _serialize_product(product)


@router.post("/")
async def create_product(data: ProductCreate, db: AsyncSession = Depends(get_db)):
    owner = await db.get(Owner, data.owner_id)
    if not owner:
        raise HTTPException(404, "Owner non trovato")

    product = Product(**data.model_dump(exclude_none=True))
    db.add(product)
    await db.flush()

    if data.price_initial:
        db.add(PriceHistory(product_id=product.id, price=data.price_initial, reason="initial"))

    db.add(ActivityLog(product_id=product.id, owner_id=data.owner_id, action="created"))
    db.add(Event(event_type="product_created", product_id=product.id, source="user",
                 title=f"Prodotto creato: {data.title or 'Senza titolo'}",
                 description=f"Proprietario: {owner.name}, Prezzo: €{data.price_initial or 0}"))

    await db.commit()
    await db.refresh(product)

    await notify_product_created(
        product.title or "Prodotto senza titolo",
        owner.name,
        data.price_initial,
    )

    return _serialize_product(product)


@router.patch("/{product_id}")
async def update_product(product_id: str, data: ProductUpdate, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    if "price_listed" in update_data and data.price_listed is not None:
        db.add(PriceHistory(product_id=product_id, price=data.price_listed, reason="manual_update"))
        db.add(ActivityLog(product_id=product_id, owner_id=product.owner_id, action="price_changed",
                           details=f"Prezzo aggiornato a €{data.price_listed}"))

    if "status" in update_data:
        db.add(ActivityLog(product_id=product_id, owner_id=product.owner_id, action=data.status))

    await db.commit()
    await db.refresh(product)
    return _serialize_product(product)


@router.post("/{product_id}/sold")
async def mark_sold(product_id: str, data: SoldRequest, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)

    product.status = "sold"
    product.price_sold = data.price_sold
    product.sold_at = datetime.now(timezone.utc)

    db.add(PriceHistory(product_id=product_id, price=data.price_sold, reason="sale"))
    db.add(ActivityLog(product_id=product_id, owner_id=product.owner_id, action="sold",
                       details=f"Venduto a €{data.price_sold}"))

    await db.commit()
    await db.refresh(product)

    owner = await db.get(Owner, product.owner_id)
    await notify_product_sold(product.title or "Prodotto", owner.name if owner else "?", data.price_sold)

    return _serialize_product(product)


@router.post("/{product_id}/upload")
async def upload_image(
    product_id: str,
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_or_404(db, product_id)

    content = await file.read()
    ext = "." + (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    original_path = image_processor.save_original(content, ext)

    processed_path = image_processor.process_image(original_path)

    img = ProductImage(
        product_id=product_id,
        original_path=original_path,
        processed_path=processed_path,
        is_primary=is_primary,
    )
    db.add(img)
    db.add(Event(event_type="image_uploaded", product_id=product_id, source="user",
                 title=f"Immagine caricata per {product.title or product_id[:8]}"))
    await db.commit()
    await db.refresh(img)

    return {"id": img.id, "original": original_path, "processed": processed_path}


@router.post("/{product_id}/analyze")
async def analyze_with_ai(product_id: str, db: AsyncSession = Depends(get_db)):
    """Analizza il prodotto con Gemini Vision usando la foto primaria."""
    product = await _get_or_404(db, product_id)

    primary_img = next((img for img in product.images if img.is_primary), None)
    if not primary_img:
        primary_img = product.images[0] if product.images else None
    if not primary_img:
        raise HTTPException(400, "Nessuna immagine caricata per questo prodotto")

    analysis = await gemini.analyze_product_image(primary_img.original_path)

    product.ai_detected_object = analysis.get("object")
    product.ai_confidence = analysis.get("confidence")
    product.category = product.category or analysis.get("category")
    product.condition = product.condition or analysis.get("condition")
    product.condition_score = product.condition_score or analysis.get("condition_score")
    product.defects = product.defects or analysis.get("defects")
    product.dimensions = product.dimensions or analysis.get("dimensions_estimate")
    product.price_ai_suggested = analysis.get("suggested_price_eur")

    if not product.title:
        product.title = analysis.get("object")

    await db.commit()
    await db.refresh(product)

    return {"analysis": analysis, "product": _serialize_product(product)}


@router.post("/{product_id}/generate-descriptions")
async def generate_descriptions(product_id: str, db: AsyncSession = Depends(get_db)):
    """Genera descrizioni multi-piattaforma con Gemini."""
    product = await _get_or_404(db, product_id)

    if not product.title and not product.ai_detected_object:
        raise HTTPException(400, "Prima analizza il prodotto con /analyze")

    descriptions = await gemini.generate_listing_descriptions(
        object_name=product.title or product.ai_detected_object or "Oggetto",
        category=product.category or "Altro",
        condition=product.condition or "usato",
        defects=product.defects,
        dimensions=product.dimensions,
        materials=None,
        features=None,
        price=product.price_listed or product.price_initial or product.price_ai_suggested,
        location=product.pickup_location,
    )

    product.title = product.title or descriptions.get("title")
    product.desc_subito = descriptions.get("subito", {}).get("description")
    product.desc_ebay = descriptions.get("ebay", {}).get("description")
    product.desc_vinted = descriptions.get("vinted", {}).get("description")
    product.desc_facebook = descriptions.get("facebook", {}).get("description")
    product.desc_vestiaire = descriptions.get("vestiaire", {}).get("description")
    product.status = "ready" if product.status == "draft" else product.status

    await db.commit()
    await db.refresh(product)

    return {"descriptions": descriptions, "product": _serialize_product(product)}


@router.delete("/{product_id}")
async def delete_product(product_id: str, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)
    await db.delete(product)
    await db.commit()
    return {"deleted": product_id}


# --- Image Management ---

@router.delete("/{product_id}/images/{image_id}")
async def delete_image(product_id: str, image_id: str, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    img = await db.get(ProductImage, image_id)
    if not img or img.product_id != product_id:
        raise HTTPException(404, "Immagine non trovata")
    await db.delete(img)
    await db.commit()
    return {"deleted": image_id}


# --- Publications ---

class PublicationCreate(BaseModel):
    platform: str
    account_id: str | None = None
    status: str = "pending"
    link: str | None = None
    price_published: float | None = None
    notes: str | None = None
    is_manual: bool = True


class PublicationUpdate(BaseModel):
    account_id: str | None = None
    status: str | None = None
    link: str | None = None
    notes: str | None = None
    price_published: float | None = None
    views_count: int | None = None
    messages_count: int | None = None


@router.get("/{product_id}/publications/")
async def list_publications(product_id: str, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    result = await db.execute(select(Publication).where(Publication.product_id == product_id))
    pubs = result.scalars().all()
    return [_serialize_pub(p) for p in pubs]


@router.post("/{product_id}/publications/")
async def create_publication(product_id: str, data: PublicationCreate, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    pub = Publication(
        product_id=product_id,
        platform=data.platform,
        account_id=data.account_id,
        status=data.status,
        link=data.link,
        notes=data.notes,
        is_manual=data.is_manual,
        price_published=data.price_published,
        published_at=datetime.now(timezone.utc) if data.status == "published" else None,
    )
    db.add(pub)
    db.add(Event(event_type="publication_created", product_id=product_id, publication_id=pub.id,
                 source="user", title=f"Pubblicazione su {data.platform}",
                 description=f"Stato: {data.status}" + (f", Link: {data.link}" if data.link else "")))
    await db.commit()
    await db.refresh(pub)
    return _serialize_pub(pub)


@router.patch("/{product_id}/publications/{pub_id}")
async def update_publication(product_id: str, pub_id: str, data: PublicationUpdate, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    pub = await db.get(Publication, pub_id)
    if not pub or pub.product_id != product_id:
        raise HTTPException(404, "Pubblicazione non trovata")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pub, key, value)
    if data.status == "published" and not pub.published_at:
        pub.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(pub)
    return _serialize_pub(pub)


@router.patch("/{product_id}/publications/{pub_id}/check")
async def check_publication(product_id: str, pub_id: str, db: AsyncSession = Depends(get_db)):
    """Segna la pubblicazione come verificata ora."""
    await _get_or_404(db, product_id)
    pub = await db.get(Publication, pub_id)
    if not pub or pub.product_id != product_id:
        raise HTTPException(404, "Pubblicazione non trovata")
    pub.last_checked_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(pub)
    return _serialize_pub(pub)


def _serialize_pub(p: Publication) -> dict:
    return {
        "id": p.id,
        "product_id": p.product_id,
        "platform": p.platform,
        "account_id": p.account_id,
        "account_name": p.account.account_name if p.account else None,
        "status": p.status,
        "link": p.link,
        "notes": p.notes,
        "is_manual": p.is_manual,
        "price_published": p.price_published,
        "views_count": p.views_count,
        "messages_count": p.messages_count,
        "last_checked_at": p.last_checked_at.isoformat() if p.last_checked_at else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


async def _get_or_404(db: AsyncSession, product_id: str) -> Product:
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Prodotto non trovato")
    return product


def _serialize_product(p: Product) -> dict:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "owner_name": p.owner.name if p.owner else None,
        "title": p.title,
        "description_raw": p.description_raw,
        "desc_subito": p.desc_subito,
        "desc_ebay": p.desc_ebay,
        "desc_vinted": p.desc_vinted,
        "desc_facebook": p.desc_facebook,
        "desc_vestiaire": p.desc_vestiaire,
        "category": p.category,
        "condition": p.condition,
        "condition_score": p.condition_score,
        "defects": p.defects,
        "dimensions": p.dimensions,
        "measurements": p.measurements,
        "weight_kg": p.weight_kg,
        "price_initial": p.price_initial,
        "price_ai_suggested": p.price_ai_suggested,
        "price_listed": p.price_listed,
        "price_sold": p.price_sold,
        "status": p.status,
        "logistics_status": p.logistics_status,
        "platforms": p.platforms,
        "platform_links": p.platform_links,
        "pickup_location": p.pickup_location,
        "is_dismantled": p.is_dismantled,
        "shipping_available": p.shipping_available,
        "urgency": p.urgency,
        "ai_detected_object": p.ai_detected_object,
        "ai_confidence": p.ai_confidence,
        "notes": p.notes,
        "images": [
            {"id": img.id, "original": img.original_path, "processed": img.processed_path,
             "is_primary": img.is_primary, "is_ai_processed": img.is_ai_processed, "is_accepted": img.is_accepted}
            for img in (p.images or [])
        ],
        "publications": [
            {"id": pub.id, "platform": pub.platform, "status": pub.status, "link": pub.link,
             "account_id": pub.account_id, "account_name": pub.account.account_name if pub.account else None,
             "price_published": pub.price_published, "views_count": pub.views_count,
             "messages_count": pub.messages_count,
             "last_checked_at": pub.last_checked_at.isoformat() if pub.last_checked_at else None,
             "published_at": pub.published_at.isoformat() if pub.published_at else None}
            for pub in (p.publications or [])
        ],
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "sold_at": p.sold_at.isoformat() if p.sold_at else None,
    }
