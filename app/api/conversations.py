from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.event import Event

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    product_id: str | None = None
    platform: str
    contact_name: str | None = None
    contact_handle: str | None = None
    status: str = "open"
    source: str = "manual"


class MessageCreate(BaseModel):
    direction: str = "outgoing"
    source: str = "manual"
    sender_name: str | None = None
    subject: str | None = None
    body: str | None = None


@router.get("/")
async def list_conversations(
    platform: str | None = None,
    status: str | None = None,
    unread_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(Conversation).order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
    if platform:
        query = query.where(Conversation.platform == platform)
    if status:
        query = query.where(Conversation.status == status)
    if unread_only:
        query = query.where(Conversation.unread_count > 0)

    result = await db.execute(query)
    convs = result.scalars().all()

    return [_serialize_conversation(c) for c in convs]


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversazione non trovata")

    data = _serialize_conversation(conv)
    data["messages"] = [
        {
            "id": m.id,
            "direction": m.direction,
            "source": m.source,
            "sender_name": m.sender_name,
            "subject": m.subject,
            "body": m.body,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat(),
        }
        for m in conv.messages
    ]
    return data


@router.post("/")
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = Conversation(**data.model_dump(exclude_none=True))
    db.add(conv)
    await db.flush()

    db.add(Event(
        event_type="conversation_created",
        conversation_id=conv.id,
        product_id=data.product_id,
        source="user",
        title=f"Nuova conversazione con {data.contact_name or 'Sconosciuto'}",
        description=f"Piattaforma: {data.platform}",
    ))

    await db.commit()
    await db.refresh(conv)
    return _serialize_conversation(conv)


@router.patch("/{conv_id}")
async def update_conversation(conv_id: str, status: str | None = None, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversazione non trovata")
    if status:
        conv.status = status
    await db.commit()
    await db.refresh(conv)
    return _serialize_conversation(conv)


@router.post("/{conv_id}/messages/")
async def add_message(conv_id: str, data: MessageCreate, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversazione non trovata")

    msg = Message(
        conversation_id=conv_id,
        direction=data.direction,
        source=data.source,
        sender_name=data.sender_name,
        subject=data.subject,
        body=data.body,
    )
    db.add(msg)

    conv.last_message_at = datetime.now(timezone.utc)
    if data.direction == "incoming":
        conv.unread_count += 1

    db.add(Event(
        event_type="message_received" if data.direction == "incoming" else "message_sent",
        conversation_id=conv_id,
        product_id=conv.product_id,
        source=data.source,
        title=f"Messaggio {'ricevuto' if data.direction == 'incoming' else 'inviato'}",
        description=data.body[:200] if data.body else None,
    ))

    await db.commit()
    await db.refresh(msg)

    return {
        "id": msg.id,
        "direction": msg.direction,
        "body": msg.body,
        "created_at": msg.created_at.isoformat(),
    }


@router.post("/{conv_id}/read")
async def mark_read(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await db.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(404, "Conversazione non trovata")
    conv.unread_count = 0

    for msg in conv.messages:
        if not msg.is_read:
            msg.is_read = True

    await db.commit()
    return {"ok": True}


def _serialize_conversation(c: Conversation) -> dict:
    last_msg = c.messages[-1] if c.messages else None
    return {
        "id": c.id,
        "product_id": c.product_id,
        "product_title": c.product.title if c.product else None,
        "platform": c.platform,
        "contact_name": c.contact_name,
        "contact_handle": c.contact_handle,
        "unread_count": c.unread_count,
        "status": c.status,
        "source": c.source,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        "last_message_preview": (last_msg.body or "")[:100] if last_msg else None,
        "last_message_direction": last_msg.direction if last_msg else None,
        "message_count": len(c.messages) if c.messages else 0,
        "created_at": c.created_at.isoformat(),
    }
