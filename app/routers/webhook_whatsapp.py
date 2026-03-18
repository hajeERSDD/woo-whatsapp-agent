"""
Router — Webhook Meta WhatsApp
Reçoit les réponses des clients (OUI / NON)
et met à jour le statut WooCommerce en conséquence
"""
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.config import get_settings
from app.models.order import Order, OrderStatus
from app.services.woocommerce import woocommerce_service
from app.services.whatsapp import send_status_update

router = APIRouter()
settings = get_settings()

# Mots-clés de confirmation et annulation (insensible à la casse)
CONFIRM_KEYWORDS = {"oui", "yes", "confirmer", "confirme", "ok", "1", "✅"}
CANCEL_KEYWORDS = {"non", "no", "annuler", "annule", "cancel", "2", "❌"}


def normalize_reply(text: str) -> str:
    """Normalise le texte de réponse du client."""
    return text.strip().lower()


def detect_intent(text: str) -> str | None:
    """
    Détecte l'intention du client depuis son message.
    Retourne 'confirm', 'cancel', ou None si non reconnu.
    """
    normalized = normalize_reply(text)
    # Vérifier correspondance exacte d'abord
    if normalized in CONFIRM_KEYWORDS:
        return "confirm"
    if normalized in CANCEL_KEYWORDS:
        return "cancel"
    # Vérifier si le message contient un mot-clé
    for kw in CONFIRM_KEYWORDS:
        if kw in normalized:
            return "confirm"
    for kw in CANCEL_KEYWORDS:
        if kw in normalized:
            return "cancel"
    return None


@router.get("/whatsapp")
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Vérification du webhook par Meta.
    Meta envoie une requête GET lors de la configuration dans le Meta Developer Portal.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_verify_token:
        print("[WhatsApp Webhook] ✅ Verification réussie.")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification token invalide")


@router.post("/whatsapp")
async def whatsapp_incoming(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Reçoit les messages WhatsApp entrants (réponses des clients).
    Meta envoie un POST ici pour chaque message reçu.
    """
    data = await request.json()

    # Naviguer dans la structure du payload Meta
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Ignorer les statuts de livraison (sent, delivered, read)
        if "statuses" in value and "messages" not in value:
            return {"status": "ok"}

        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok"}

        message = messages[0]
        sender_phone = message["from"]          # Format: 21655xxxxxx (sans +)
        msg_type = message.get("type", "")
        msg_text = ""

        if msg_type == "text":
            msg_text = message["text"]["body"]
        elif msg_type == "interactive":
            # Boutons interactifs (si template avec boutons)
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                msg_text = interactive["button_reply"]["id"]  # "confirm" ou "cancel"
        else:
            # Type de message non géré (image, audio, etc.)
            return {"status": "ok"}

    except (KeyError, IndexError) as e:
        print(f"[WhatsApp Webhook] Payload inattendu: {e}")
        return {"status": "ok"}

    # Normaliser le numéro (Meta envoie sans +)
    if not sender_phone.startswith("+"):
        sender_phone_normalized = "+" + sender_phone
    else:
        sender_phone_normalized = sender_phone

    # Trouver la commande en attente pour ce numéro
    result = await db.execute(
        select(Order)
        .where(Order.customer_phone == sender_phone_normalized)
        .where(Order.status == OrderStatus.SENT)
        .order_by(Order.created_at.desc())
    )
    order = result.scalar_one_or_none()

    if not order:
        print(f"[WhatsApp] Aucune commande en attente pour {sender_phone_normalized}")
        return {"status": "ok"}

    # Détecter l'intention du client
    intent = detect_intent(msg_text)

    if intent == "confirm":
        await handle_confirmation(order, db)
    elif intent == "cancel":
        await handle_cancellation(order, db)
    else:
        # Message non reconnu — envoyer un rappel
        from app.services.whatsapp import send_whatsapp_message
        await send_whatsapp_message(
            sender_phone_normalized,
            f"Désolé, je n'ai pas compris votre réponse 😅\n\n"
            f"Pour la commande *#{order.wc_order_id}*, répondez :\n"
            f"✅ *OUI* pour confirmer\n"
            f"❌ *NON* pour annuler"
        )

    return {"status": "ok"}


async def handle_confirmation(order: Order, db: AsyncSession):
    """Traite la confirmation du client."""
    try:
        # 1. Mettre à jour WooCommerce
        await woocommerce_service.update_order_status(
            order.wc_order_id, settings.wc_status_confirmed
        )
        await woocommerce_service.add_order_note(
            order.wc_order_id,
            f"✅ Commande confirmée par le client via WhatsApp ({order.customer_phone})"
        )

        # 2. Mettre à jour la base locale
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = datetime.utcnow()
        await db.commit()

        # 3. Envoyer confirmation au client
        await send_status_update(
            order.customer_phone, order.customer_name, "confirmed", order.wc_order_id
        )
        print(f"[WhatsApp] ✅ Commande #{order.wc_order_id} confirmée → WooCommerce mis à jour")

    except Exception as e:
        print(f"[WhatsApp] Erreur lors de la confirmation: {e}")


async def handle_cancellation(order: Order, db: AsyncSession):
    """Traite l'annulation par le client."""
    try:
        # 1. Mettre à jour WooCommerce
        await woocommerce_service.update_order_status(
            order.wc_order_id, settings.wc_status_cancelled
        )
        await woocommerce_service.add_order_note(
            order.wc_order_id,
            f"❌ Commande annulée par le client via WhatsApp ({order.customer_phone})"
        )

        # 2. Mettre à jour la base locale
        order.status = OrderStatus.CANCELLED
        await db.commit()

        # 3. Envoyer confirmation d'annulation
        await send_status_update(
            order.customer_phone, order.customer_name, "cancelled", order.wc_order_id
        )
        print(f"[WhatsApp] ❌ Commande #{order.wc_order_id} annulée → WooCommerce mis à jour")

    except Exception as e:
        print(f"[WhatsApp] Erreur lors de l'annulation: {e}")
