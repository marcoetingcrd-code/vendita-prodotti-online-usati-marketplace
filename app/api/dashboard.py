from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.product import Product, ProductImage, Publication
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.event import Event

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

PLATFORMS = ["subito", "ebay", "vinted", "facebook", "vestiaire"]


def _aware(dt):
    """Ensure datetime is timezone-aware for safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    products = (await db.execute(select(Product))).scalars().all()
    conversations = (await db.execute(select(Conversation))).scalars().all()

    active = [p for p in products if p.status in ("listed", "negotiating", "ready")]
    sold = [p for p in products if p.status == "sold"]
    sold_month = [p for p in sold if p.sold_at and _aware(p.sold_at) >= now - timedelta(days=30)]

    unread = sum(c.unread_count for c in conversations)
    hot = [c for c in conversations if c.status == "hot"]
    stale = [c for c in conversations if c.status == "open" and c.last_message_at and _aware(c.last_message_at) < now - timedelta(hours=48)]

    revenue_month = sum(p.price_sold or 0 for p in sold_month)

    return {
        "active_products": len(active),
        "active_trend_7d": len([p for p in active if p.created_at and _aware(p.created_at) >= week_ago]),
        "unread_messages": unread,
        "unread_today": sum(1 for c in conversations if c.last_message_at and _aware(c.last_message_at).date() == now.date() and c.unread_count > 0),
        "open_negotiations": len([p for p in products if p.status == "negotiating"]),
        "hot_conversations": len(hot),
        "stale_conversations": len(stale),
        "sold_month": len(sold_month),
        "revenue_month": revenue_month,
        "total_products": len(products),
        "drafts": len([p for p in products if p.status == "draft"]),
    }


@router.get("/platform-stats")
async def get_platform_stats(db: AsyncSession = Depends(get_db)):
    pubs = (await db.execute(select(Publication))).scalars().all()
    conversations = (await db.execute(select(Conversation))).scalars().all()
    events = (await db.execute(
        select(Event).order_by(Event.created_at.desc()).limit(100)
    )).scalars().all()

    result = {}
    for platform in PLATFORMS:
        platform_pubs = [p for p in pubs if p.platform == platform]
        platform_convs = [c for c in conversations if c.platform == platform]
        platform_events = [e for e in events if platform in (e.title or "").lower() or platform in (e.description or "").lower()]

        published = len([p for p in platform_pubs if p.status == "published"])
        open_msgs = sum(c.unread_count for c in platform_convs)
        last_event = platform_events[0] if platform_events else None

        result[platform] = {
            "published": published,
            "total_pubs": len(platform_pubs),
            "open_messages": open_msgs,
            "conversations": len(platform_convs),
            "last_event": last_event.title if last_event else None,
            "last_event_at": last_event.created_at.isoformat() if last_event else None,
        }
    return result


@router.get("/alerts")
async def get_alerts(db: AsyncSession = Depends(get_db)):
    products = (await db.execute(select(Product))).scalars().all()
    conversations = (await db.execute(select(Conversation))).scalars().all()
    now = datetime.now(timezone.utc)

    alerts = []

    # Unread messages
    unread_convs = [c for c in conversations if c.unread_count > 0]
    if unread_convs:
        alerts.append({
            "type": "unread_messages",
            "severity": "high" if len(unread_convs) > 5 else "medium",
            "title": f"{sum(c.unread_count for c in unread_convs)} messaggi non letti",
            "detail": f"in {len(unread_convs)} conversazioni",
            "action_url": "/panel/inbox",
            "action_label": "Apri Inbox",
        })

    # Products without photos
    no_photos = [p for p in products if p.status != "archived" and (not p.images or len(p.images) == 0)]
    if no_photos:
        alerts.append({
            "type": "no_photos",
            "severity": "medium",
            "title": f"{len(no_photos)} prodotti senza foto",
            "detail": ", ".join(p.title or p.id[:8] for p in no_photos[:3]),
            "action_url": "/panel/prodotti",
            "action_label": "Vai ai Prodotti",
        })

    # Products without description
    no_desc = [p for p in products if p.status not in ("archived", "sold") and not p.desc_subito and not p.desc_ebay]
    if no_desc:
        alerts.append({
            "type": "no_description",
            "severity": "medium",
            "title": f"{len(no_desc)} prodotti senza descrizione",
            "detail": ", ".join(p.title or p.id[:8] for p in no_desc[:3]),
            "action_url": "/panel/prodotti",
            "action_label": "Genera Descrizioni",
        })

    # Products without platforms
    no_platform = [p for p in products if p.status in ("ready", "listed") and (not p.publications or len(p.publications) == 0)]
    if no_platform:
        alerts.append({
            "type": "no_platform",
            "severity": "low",
            "title": f"{len(no_platform)} prodotti senza piattaforma",
            "detail": ", ".join(p.title or p.id[:8] for p in no_platform[:3]),
            "action_url": "/panel/prodotti",
            "action_label": "Assegna Piattaforma",
        })

    # Stale negotiations
    stale = [c for c in conversations if c.status == "open" and c.last_message_at and _aware(c.last_message_at) < now - timedelta(hours=48)]
    if stale:
        alerts.append({
            "type": "stale_conversations",
            "severity": "high",
            "title": f"{len(stale)} trattative ferme da 48h+",
            "detail": ", ".join(c.contact_name or "Sconosciuto" for c in stale[:3]),
            "action_url": "/panel/inbox",
            "action_label": "Gestisci",
        })

    return alerts


@router.get("/timeline")
async def get_timeline(limit: int = 20, db: AsyncSession = Depends(get_db)):
    events = (await db.execute(
        select(Event).order_by(Event.created_at.desc()).limit(limit)
    )).scalars().all()

    return [
        {
            "id": e.id,
            "type": e.event_type,
            "source": e.source,
            "title": e.title,
            "description": e.description,
            "product_id": e.product_id,
            "conversation_id": e.conversation_id,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/poll")
async def poll(db: AsyncSession = Depends(get_db)):
    """Endpoint leggero per polling UI ogni 20 secondi."""
    conversations = (await db.execute(select(Conversation))).scalars().all()
    unread = sum(c.unread_count for c in conversations)

    latest_event = (await db.execute(
        select(Event).order_by(Event.created_at.desc()).limit(1)
    )).scalars().first()

    active_products = (await db.execute(
        select(func.count()).select_from(Product).where(Product.status.in_(["listed", "negotiating", "ready"]))
    )).scalar()

    return {
        "unread_messages": unread,
        "active_products": active_products or 0,
        "open_negotiations": (await db.execute(
            select(func.count()).select_from(Product).where(Product.status == "negotiating")
        )).scalar() or 0,
        "latest_event_at": latest_event.created_at.isoformat() if latest_event else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
