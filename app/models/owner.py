import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Owner(Base):
    __tablename__ = "owners"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    name: Mapped[str] = mapped_column(String, nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    products = relationship("Product", back_populates="owner", lazy="selectin")

    def __repr__(self):
        return f"<Owner {self.name} ({self.telegram_chat_id})>"
