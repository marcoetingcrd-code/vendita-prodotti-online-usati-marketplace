from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import uuid

_new_id = lambda: uuid.uuid4().hex[:16]
_now = lambda: datetime.now(timezone.utc)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)  # incoming, outgoing, system
    source: Mapped[str] = mapped_column(String, default="email")  # email, api, telegram_forward, manual
    sender_name: Mapped[str | None] = mapped_column(String)
    sender_handle: Mapped[str | None] = mapped_column(String)
    subject: Mapped[str | None] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    external_message_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message {self.direction} from={self.sender_name}>"
