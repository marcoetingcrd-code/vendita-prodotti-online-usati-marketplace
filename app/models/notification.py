from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import uuid

_new_id = lambda: uuid.uuid4().hex[:16]
_now = lambda: datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    target_type: Mapped[str] = mapped_column(String, nullable=False)  # conversation, product, publication, event
    target_id: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String, default="telegram")  # telegram, email, web
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, sent, failed
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self):
        return f"<Notification {self.channel} {self.status}>"
