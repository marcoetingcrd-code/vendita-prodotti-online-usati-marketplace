import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, Boolean, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _new_id():
    return uuid.uuid4().hex[:16]


def _now():
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("owners.id"), nullable=False)

    title: Mapped[str | None] = mapped_column(String)
    description_raw: Mapped[str | None] = mapped_column(Text)
    desc_subito: Mapped[str | None] = mapped_column(Text)
    desc_ebay: Mapped[str | None] = mapped_column(Text)
    desc_vinted: Mapped[str | None] = mapped_column(Text)

    category: Mapped[str | None] = mapped_column(String)
    condition: Mapped[str | None] = mapped_column(String)  # nuovo, come_nuovo, buono, usato, difettoso
    condition_score: Mapped[int | None] = mapped_column(Integer)  # 1-5
    defects: Mapped[str | None] = mapped_column(Text)
    dimensions: Mapped[str | None] = mapped_column(String)
    weight_kg: Mapped[float | None] = mapped_column(Float)

    price_initial: Mapped[float | None] = mapped_column(Float)
    price_ai_suggested: Mapped[float | None] = mapped_column(Float)
    price_listed: Mapped[float | None] = mapped_column(Float)
    price_sold: Mapped[float | None] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String, default="draft")  # draft, ready, listed, negotiating, sold, archived

    platforms: Mapped[dict | None] = mapped_column(JSON)  # ["subito","ebay","vinted"]
    platform_links: Mapped[dict | None] = mapped_column(JSON)  # {"subito":"url","ebay":"url"}

    pickup_location: Mapped[str | None] = mapped_column(String)
    logistics_status: Mapped[str | None] = mapped_column(String)  # da_ritirare, ritirato, in_magazzino, spedito
    is_dismantled: Mapped[bool] = mapped_column(Boolean, default=False)
    shipping_available: Mapped[bool] = mapped_column(Boolean, default=False)
    urgency: Mapped[str] = mapped_column(String, default="low")  # low, medium, high
    measurements: Mapped[str | None] = mapped_column(Text)
    desc_facebook: Mapped[str | None] = mapped_column(Text)
    desc_vestiaire: Mapped[str | None] = mapped_column(Text)

    ai_detected_object: Mapped[str | None] = mapped_column(String)
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner = relationship("Owner", back_populates="products", lazy="selectin")
    images = relationship("ProductImage", back_populates="product", lazy="selectin", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="product", lazy="selectin", cascade="all, delete-orphan")
    publications = relationship("Publication", back_populates="product", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product {self.title} ({self.status})>"


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    original_path: Mapped[str] = mapped_column(String, nullable=False)
    processed_path: Mapped[str | None] = mapped_column(String)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    product = relationship("Product", back_populates="images")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)  # initial, ai_suggestion, manual_update, sale
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    product = relationship("Product", back_populates="price_history")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    product_id: Mapped[str] = mapped_column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # subito, ebay, vinted, facebook
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, published, paused, removed
    link: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    product = relationship("Product", back_populates="publications")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str | None] = mapped_column(String, ForeignKey("products.id"))
    owner_id: Mapped[str | None] = mapped_column(String, ForeignKey("owners.id"))
    action: Mapped[str] = mapped_column(String, nullable=False)  # created, listed, price_changed, sold, archived
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
