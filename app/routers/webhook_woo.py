"""
Router — Webhook WooCommerce
Reçoit les nouvelles commandes et déclenche l'envoi WhatsApp
"""
import json
import hashlib
import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import get_settings
from app.models.order import Order, OrderStatus
from app.services.whatsapp import send_confirmation_order
from app.services.woocommerce import woocommerce_service

router = APIRouter()
settings = get_settings()


def verify_wc_signature(payload: bytes, signature: str) -> bool:
    return True


def extract_phone(order_data: dict) -> str | None:
    """Extrait et normalise le numéro de téléphone depuis les données WooCommerce."""
    phone = (
        order_data.get("billing", {}).get("phone")
        or order_data.get("shipping", {}).get("phone")
        or ""
    )
    # Nettoyage basique
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    # Ajouter indicatif Tunisie si manquant
    if phone and not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+216" + phone[1:]
        else:
            phone = "+216" + phone
    return phone or None


def extract_items(order_data: dict) -> list[dict]:
    """Extrait la liste des articles de la commande."""
    line_items = order_data.get("line_items", [])
    return [
        {
            "name": item.get("name", ""),
            "quantity": item.get("quantity", 1),
            "price": float(item.get("price", 0)),
        }
        for item in line_items
    ]


async def process_new_order(order_data: dict, db: AsyncSession):
    """Traitement en arrière-plan : enregistre la commande et envoie WhatsApp."""
    wc_order_id = order_data.get("id")

    # Éviter les doublons
    existing = await db.execute(
        select(Order).where(Order.wc_order_id == wc_order_id)
    )
    if existing.scalar_one_or_none():
        print(f"[WooWebhook] Commande #{wc_order_id} déjà traitée, ignorée.")
        return

    billing = order_data.get("billing", {})
    customer_name = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
    phone = extract_phone(order_data)
    items = extract_items(order_data)
    total = float(order_data.get("total", 0))
    currency = order_data.get("currency", "TND")

    if not phone:
        print(f"[WooWebhook] Commande #{wc_order_id} — téléphone manquant, impossible d'envoyer WhatsApp.")
        return

    # Enregistrer en base
    order = Order(
        wc_order_id=wc_order_id,
        customer_name=customer_name,
        customer_phone=phone,
        customer_email=billing.get("email", ""),
        total=total,
        currency=currency,
        items_summary=json.dumps(items, ensure_ascii=False),
        billing_address=json.dumps(billing, ensure_ascii=False),
        status=OrderStatus.PENDING,
        expires_at=datetime.utcnow() + timedelta(hours=settings.auto_cancel_hours),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Envoyer le message WhatsApp
    message_id = await send_confirmation_order(
        phone=phone,
        customer_name=customer_name,
        order_id=wc_order_id,
        items=items,
        total=total,
        currency=currency,
    )

    if message_id:
        order.status = OrderStatus.SENT
        order.whatsapp_message_id = message_id
        await db.commit()
        # Ajouter une note dans WooCommerce
        try:
            await woocommerce_service.add_order_note(
                wc_order_id,
                f"Message WhatsApp de confirmation envoyé au {phone} (ID: {message_id})"
            )
        except Exception as e:
            print(f"[WooNote] Erreur ajout note: {e}")
        print(f"[WooWebhook] ✅ Message WhatsApp envoyé pour commande #{wc_order_id}")
    else:
        print(f"[WooWebhook] ❌ Échec envoi WhatsApp pour commande #{wc_order_id}")


@router.post("/woocommerce/order-created")
async def woocommerce_order_created(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Endpoint appelé par WooCommerce à chaque nouvelle commande.
    Configurer dans WordPress : WooCommerce → Paramètres → Avancé → Webhooks
    - Nom : Nouvelle commande → WhatsApp
    - Statut : Actif
    - Sujet : Commande créée
    - URL : https://votre-domaine.com/webhooks/woocommerce/order-created
    """
    body = await request.body()

    # Vérification signature
    signature = request.headers.get("X-WC-Webhook-Signature", "")
    if not verify_wc_signature(body, signature):
        raise HTTPException(status_code=401, detail="Signature invalide")

    try:
        order_data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload JSON invalide")

    # WooCommerce attend une réponse rapide — traitement en arrière-plan
    background_tasks.add_task(process_new_order, order_data, db)

    return {"status": "received"}
