from fastapi import APIRouter, Depends
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.product import Product
from app.models.conversation import Conversation

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/")
async def global_search(q: str, db: AsyncSession = Depends(get_db)):
    if not q or len(q) < 2:
        return {"products": [], "conversations": []}

    pattern = f"%{q}%"

    # Search products
    products = (await db.execute(
        select(Product).where(
            or_(
                Product.title.ilike(pattern),
                Product.category.ilike(pattern),
                Product.id.ilike(pattern),
                Product.notes.ilike(pattern),
            )
        ).limit(10)
    )).scalars().all()

    # Search conversations
    conversations = (await db.execute(
        select(Conversation).where(
            or_(
                Conversation.contact_name.ilike(pattern),
                Conversation.contact_handle.ilike(pattern),
                Conversation.platform.ilike(pattern),
                Conversation.id.ilike(pattern),
            )
        ).limit(10)
    )).scalars().all()

    return {
        "products": [
            {
                "id": p.id,
                "title": p.title or "Senza titolo",
                "category": p.category,
                "status": p.status,
                "owner_name": p.owner.name if p.owner else None,
            }
            for p in products
        ],
        "conversations": [
            {
                "id": c.id,
                "contact_name": c.contact_name,
                "platform": c.platform,
                "status": c.status,
                "unread_count": c.unread_count,
            }
            for c in conversations
        ],
    }
