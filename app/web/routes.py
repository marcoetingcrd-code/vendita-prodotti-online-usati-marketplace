import json
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from app.database import get_db
from app.models.product import Product, PriceHistory, Publication
from app.models.owner import Owner

router = APIRouter(tags=["web"])

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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


async def _get_owners(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Owner).order_by(Owner.name))
    return [{"id": o.id, "name": o.name, "telegram_chat_id": o.telegram_chat_id} for o in result.scalars().all()]


@router.get("/panel")
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
    })


@router.get("/panel/prodotti")
async def products_list(request: Request, db: AsyncSession = Depends(get_db)):
    owners = await _get_owners(db)
    return templates.TemplateResponse("products.html", {
        "request": request,
        "active_page": "products",
        "owners": owners,
    })


@router.get("/panel/prodotti/nuovo")
async def product_new(request: Request, db: AsyncSession = Depends(get_db)):
    owners = await _get_owners(db)
    return templates.TemplateResponse("product_new.html", {
        "request": request,
        "active_page": "products",
        "owners": owners,
    })


@router.get("/panel/prodotti/{product_id}")
async def product_detail(product_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "active_page": "dashboard",
            "owners": await _get_owners(db),
            "flash_message": "Prodotto non trovato",
            "flash_type": "error",
        })

    product_data = _serialize_product(product)

    price_history = [
        {"id": ph.id, "price": ph.price, "reason": ph.reason, "created_at": ph.created_at.isoformat()}
        for ph in (product.price_history or [])
    ]

    publications = [
        {"id": pub.id, "platform": pub.platform, "status": pub.status, "link": pub.link,
         "notes": pub.notes, "is_manual": pub.is_manual,
         "published_at": pub.published_at.isoformat() if pub.published_at else None}
        for pub in (product.publications or [])
    ]

    return templates.TemplateResponse("product_detail.html", {
        "request": request,
        "active_page": "products",
        "product": product_data,
        "product_json": json.dumps(product_data),
        "price_history_json": json.dumps(price_history),
        "publications_json": json.dumps(publications),
    })


@router.get("/panel/inbox")
async def inbox(request: Request):
    return templates.TemplateResponse("inbox.html", {
        "request": request,
        "active_page": "inbox",
    })


@router.get("/panel/eventi")
async def events_page(request: Request):
    return templates.TemplateResponse("events.html", {
        "request": request,
        "active_page": "events",
    })


@router.get("/panel/proprietari")
async def owners_page(request: Request, db: AsyncSession = Depends(get_db)):
    owners = await _get_owners(db)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "owners",
        "flash_message": "Pagina proprietari in costruzione. Usa API /api/owners/",
        "flash_type": "info",
    })
