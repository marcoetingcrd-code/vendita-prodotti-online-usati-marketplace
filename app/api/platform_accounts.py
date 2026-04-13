from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.database import get_db
from app.models.platform_account import PlatformAccount

router = APIRouter(prefix="/api/platform-accounts", tags=["platform-accounts"])


class AccountCreate(BaseModel):
    platform: str
    account_name: str
    account_label: str | None = None
    login_url: str | None = None
    profile_url: str | None = None
    notes: str | None = None


class AccountUpdate(BaseModel):
    account_name: str | None = None
    account_label: str | None = None
    login_url: str | None = None
    profile_url: str | None = None
    notes: str | None = None
    is_active: bool | None = None


def _serialize(a: PlatformAccount) -> dict:
    return {
        "id": a.id,
        "platform": a.platform,
        "account_name": a.account_name,
        "account_label": a.account_label,
        "login_url": a.login_url,
        "profile_url": a.profile_url,
        "notes": a.notes,
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/")
async def list_accounts(platform: str | None = None, db: AsyncSession = Depends(get_db)):
    query = select(PlatformAccount).order_by(PlatformAccount.platform, PlatformAccount.account_name)
    if platform:
        query = query.where(PlatformAccount.platform == platform)
    result = await db.execute(query)
    return [_serialize(a) for a in result.scalars().all()]


@router.post("/")
async def create_account(data: AccountCreate, db: AsyncSession = Depends(get_db)):
    account = PlatformAccount(
        platform=data.platform,
        account_name=data.account_name,
        account_label=data.account_label,
        login_url=data.login_url,
        profile_url=data.profile_url,
        notes=data.notes,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return _serialize(account)


@router.patch("/{account_id}")
async def update_account(account_id: str, data: AccountUpdate, db: AsyncSession = Depends(get_db)):
    account = await db.get(PlatformAccount, account_id)
    if not account:
        raise HTTPException(404, "Account non trovato")
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(account, field, val)
    await db.commit()
    await db.refresh(account)
    return _serialize(account)


@router.delete("/{account_id}")
async def delete_account(account_id: str, db: AsyncSession = Depends(get_db)):
    account = await db.get(PlatformAccount, account_id)
    if not account:
        raise HTTPException(404, "Account non trovato")
    await db.delete(account)
    await db.commit()
    return {"ok": True}
