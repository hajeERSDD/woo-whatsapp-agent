import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import get_settings
from app.models.order import Order, OrderStatus
from app.services.woocommerce import woocommerce_service
from app.services.whatsapp import (
    ask_claude, detect_intent_from_response,
    clean_response, send_whatsapp_message, send_status_update
)

router = APIRouter()
settings = get_settings()

conversation_histories = {}

@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Token invalide")


@router.post("/whatsapp")
async def whatsapp_incoming(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "statuses" in value and "messages" not in value:
            return {"status": "ok"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}

        message = messages[0]
        sender_phone = message["from"]
        msg_type = message.get("type", "")
        msg_text = ""

        if msg_type == "text":
            msg_text = message["text"]["body"]
        else:
            return {"status": "ok"}

    except (KeyError, IndexError) as e:
        print(f"[WhatsApp] Payload inattendu: {e}")
        return {"status": "ok"}

    phone_normalized = "+" + sender_phone if not sender_phone.startswith("+") else sender_phone

    result = await db.execute(
        select(Order)
        .where(Order.customer_phone == phone_normalized)
        .where(Order.status == OrderStatus.SENT)
        .order_by(Order.created_at.desc())
    )
    order = result.scalar_one_or_none()
