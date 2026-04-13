import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def _new_id():
    return uuid.uuid4().hex[:16]


def _now():
    return datetime.now(timezone.utc)


class PlatformAccount(Base):
    __tablename__ = "platform_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # subito, ebay, vinted, facebook, vestiaire
    account_name: Mapped[str] = mapped_column(String, nullable=False)  # "Marco Personale", "Account Business"
    account_label: Mapped[str | None] = mapped_column(String)  # short label for UI badges
    login_url: Mapped[str | None] = mapped_column(String)  # link to seller dashboard on the platform
    profile_url: Mapped[str | None] = mapped_column(String)  # link to public profile
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
