from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.event import Event

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/")
async def list_events(
    event_type: str | None = None,
    product_id: str | None = None,
    conversation_id: str | None = None,
    source: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Event).order_by(Event.created_at.desc()).limit(limit)
    if event_type:
        query = query.where(Event.event_type == event_type)
    if product_id:
        query = query.where(Event.product_id == product_id)
    if conversation_id:
        query = query.where(Event.conversation_id == conversation_id)
    if source:
        query = query.where(Event.source == source)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "product_id": e.product_id,
            "conversation_id": e.conversation_id,
            "publication_id": e.publication_id,
            "source": e.source,
            "title": e.title,
            "description": e.description,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
