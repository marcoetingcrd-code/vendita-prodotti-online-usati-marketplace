from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.product import Product
from app.models.owner import Owner

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/")
async def get_stats(owner_id: str | None = None, db: AsyncSession = Depends(get_db)):
    base_query = select(Product)
    if owner_id:
        base_query = base_query.where(Product.owner_id == owner_id)

    result = await db.execute(base_query)
    products = result.scalars().all()

    total = len(products)
    sold = [p for p in products if p.status == "sold"]
    listed = [p for p in products if p.status == "listed"]
    draft = [p for p in products if p.status == "draft"]

    total_revenue = sum(p.price_sold for p in sold if p.price_sold)
    avg_sale_price = total_revenue / len(sold) if sold else 0

    days_to_sell = []
    for p in sold:
        if p.sold_at and p.created_at:
            delta = (p.sold_at - p.created_at).days
            days_to_sell.append(delta)
    avg_days = sum(days_to_sell) / len(days_to_sell) if days_to_sell else 0

    return {
        "total_products": total,
        "sold": len(sold),
        "listed": len(listed),
        "draft": len(draft),
        "total_revenue": round(total_revenue, 2),
        "avg_sale_price": round(avg_sale_price, 2),
        "avg_days_to_sell": round(avg_days, 1),
    }


@router.get("/by-owner")
async def stats_by_owner(db: AsyncSession = Depends(get_db)):
    owners_result = await db.execute(select(Owner))
    owners = owners_result.scalars().all()

    stats = []
    for owner in owners:
        products_result = await db.execute(select(Product).where(Product.owner_id == owner.id))
        products = products_result.scalars().all()

        sold = [p for p in products if p.status == "sold"]
        revenue = sum(p.price_sold for p in sold if p.price_sold)

        stats.append({
            "owner_id": owner.id,
            "owner_name": owner.name,
            "total_products": len(products),
            "sold": len(sold),
            "revenue": round(revenue, 2),
        })

    return stats
