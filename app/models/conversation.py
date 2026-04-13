from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import uuid

_new_id = lambda: uuid.uuid4().hex[:16]
_now = lambda: datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    product_id: Mapped[str | None] = mapped_column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # subito, ebay, vinted, facebook, telegram, other
    external_thread_id: Mapped[str | None] = mapped_column(String)
    contact_name: Mapped[str | None] = mapped_column(String)
    contact_handle: Mapped[str | None] = mapped_column(String)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="open")  # open, hot, waiting, closed
    source: Mapped[str] = mapped_column(String, default="email")  # email, api, manual, telegram_forward
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product = relationship("Product", backref="conversations", lazy="selectin")
    messages = relationship("Message", back_populates="conversation", lazy="selectin", cascade="all, delete-orphan",
                            order_by="Message.created_at.asc()")

    def __repr__(self):
        return f"<Conversation {self.platform} {self.contact_name}>"
