from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.owner import Owner

router = APIRouter(prefix="/api/owners", tags=["owners"])


class OwnerCreate(BaseModel):
    name: str
    telegram_chat_id: str


class OwnerUpdate(BaseModel):
    name: str | None = None


@router.get("/")
async def list_owners(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Owner).order_by(Owner.name))
    owners = result.scalars().all()
    return [{"id": o.id, "name": o.name, "telegram_chat_id": o.telegram_chat_id} for o in owners]


@router.post("/")
async def create_owner(data: OwnerCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Owner).where(Owner.telegram_chat_id == data.telegram_chat_id))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Owner con questo chat_id esiste già")

    owner = Owner(name=data.name, telegram_chat_id=data.telegram_chat_id)
    db.add(owner)
    await db.commit()
    await db.refresh(owner)
    return {"id": owner.id, "name": owner.name, "telegram_chat_id": owner.telegram_chat_id}


@router.patch("/{owner_id}")
async def update_owner(owner_id: str, data: OwnerUpdate, db: AsyncSession = Depends(get_db)):
    owner = await db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(404, "Owner non trovato")

    if data.name is not None:
        owner.name = data.name

    await db.commit()
    await db.refresh(owner)
    return {"id": owner.id, "name": owner.name, "telegram_chat_id": owner.telegram_chat_id}


@router.delete("/{owner_id}")
async def delete_owner(owner_id: str, db: AsyncSession = Depends(get_db)):
    owner = await db.get(Owner, owner_id)
    if not owner:
        raise HTTPException(404, "Owner non trovato")
    await db.delete(owner)
    await db.commit()
    return {"deleted": owner_id}
