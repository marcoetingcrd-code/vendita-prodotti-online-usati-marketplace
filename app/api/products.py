from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.product import Product, ProductImage, PriceHistory, ActivityLog, Publication
from app.models.owner import Owner
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
    platforms: list[str] | None = None
    platform_links: dict | None = None


class SoldRequest(BaseModel):
    price_sold: float


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

    product = Product(**data.model_dump())
    db.add(product)

    if data.price_initial:
        db.add(PriceHistory(product_id=product.id, price=data.price_initial, reason="initial"))

    db.add(ActivityLog(product_id=product.id, owner_id=data.owner_id, action="created"))

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
    status: str = "pending"
    link: str | None = None
    notes: str | None = None
    is_manual: bool = True


class PublicationUpdate(BaseModel):
    status: str | None = None
    link: str | None = None
    notes: str | None = None


@router.get("/{product_id}/publications/")
async def list_publications(product_id: str, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    result = await db.execute(select(Publication).where(Publication.product_id == product_id))
    pubs = result.scalars().all()
    return [
        {"id": p.id, "platform": p.platform, "status": p.status, "link": p.link,
         "notes": p.notes, "is_manual": p.is_manual,
         "published_at": p.published_at.isoformat() if p.published_at else None}
        for p in pubs
    ]


@router.post("/{product_id}/publications/")
async def create_publication(product_id: str, data: PublicationCreate, db: AsyncSession = Depends(get_db)):
    await _get_or_404(db, product_id)
    pub = Publication(
        product_id=product_id,
        platform=data.platform,
        status=data.status,
        link=data.link,
        notes=data.notes,
        is_manual=data.is_manual,
        published_at=datetime.now(timezone.utc) if data.status == "published" else None,
    )
    db.add(pub)
    await db.commit()
    await db.refresh(pub)
    return {"id": pub.id, "platform": pub.platform, "status": pub.status, "link": pub.link}


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
    return {"id": pub.id, "platform": pub.platform, "status": pub.status, "link": pub.link}


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
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "sold_at": p.sold_at.isoformat() if p.sold_at else None,
    }
