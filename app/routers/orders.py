"""
Router — Gestion des commandes
API pour consulter et gérer les commandes depuis le dashboard
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.order import Order, OrderStatus

router = APIRouter()


class OrderOut(BaseModel):
    id: int
    wc_order_id: int
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    total: float
    currency: str
    items_summary: Optional[str]
    status: str
    created_at: Optional[datetime]
    confirmed_at: Optional[datetime]
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/", response_model=list[OrderOut])
async def list_orders(
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Retourne la liste des commandes, optionnellement filtrée par statut."""
    query = select(Order).order_by(desc(Order.created_at)).offset(skip).limit(limit)
    if status:
        query = query.where(Order.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Retourne une commande par son ID local."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")
    return order


@router.post("/{order_id}/resend-whatsapp")
async def resend_whatsapp(order_id: int, db: AsyncSession = Depends(get_db)):
    """Renvoie manuellement le message WhatsApp pour une commande."""
    import json
    from app.services.whatsapp import send_confirmation_order

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Commande non trouvée")

    if order.status not in [OrderStatus.PENDING, OrderStatus.SENT]:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de renvoyer: statut actuel = {order.status}"
        )

    items = json.loads(order.items_summary or "[]")
    message_id = await send_confirmation_order(
        phone=order.customer_phone,
        customer_name=order.customer_name,
        order_id=order.wc_order_id,
        items=items,
        total=order.total,
        currency=order.currency,
    )

    if message_id:
        order.status = OrderStatus.SENT
        order.whatsapp_message_id = message_id
        await db.commit()
        return {"status": "sent", "message_id": message_id}
    else:
        raise HTTPException(status_code=500, detail="Échec de l'envoi WhatsApp")


@router.get("/stats/summary")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Retourne les statistiques des commandes."""
    from sqlalchemy import func

    result = await db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    stats = {row[0]: row[1] for row in result.all()}
    total = sum(stats.values())

    return {
        "total": total,
        "pending": stats.get(OrderStatus.PENDING, 0),
        "sent": stats.get(OrderStatus.SENT, 0),
        "confirmed": stats.get(OrderStatus.CONFIRMED, 0),
        "cancelled": stats.get(OrderStatus.CANCELLED, 0),
        "expired": stats.get(OrderStatus.EXPIRED, 0),
        "confirmation_rate": round(
            stats.get(OrderStatus.CONFIRMED, 0) / max(total, 1) * 100, 1
        ),
    }
