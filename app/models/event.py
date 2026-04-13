from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
import uuid

_new_id = lambda: uuid.uuid4().hex[:16]
_now = lambda: datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Types: product_created, product_updated, product_sold, product_archived,
    #        image_uploaded, ai_analyzed, description_generated,
    #        publication_created, publication_updated,
    #        message_received, message_sent,
    #        email_ingested, email_parse_error,
    #        telegram_alert_sent, system_error
    product_id: Mapped[str | None] = mapped_column(String, ForeignKey("products.id", ondelete="SET NULL"))
    conversation_id: Mapped[str | None] = mapped_column(String, ForeignKey("conversations.id", ondelete="SET NULL"))
    publication_id: Mapped[str | None] = mapped_column(String, ForeignKey("publications.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String, default="system")  # system, user, email_hub, telegram, ai
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self):
        return f"<Event {self.event_type} {self.title}>"
