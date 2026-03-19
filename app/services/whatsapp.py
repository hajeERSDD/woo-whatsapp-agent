"""
Service Meta WhatsApp Cloud API
Envoi de messages de confirmation de commande
"""
import httpx
import json
from app.config import get_settings

settings = get_settings()

META_API_URL = (
    f"https://graph.facebook.com/v19.0/{settings.meta_phone_number_id}/messages"
)
HEADERS = {
    "Authorization": f"Bearer {settings.meta_whatsapp_token}",
    "Content-Type": "application/json",
}


def build_confirmation_message(
    customer_name: str,
    order_id: int,
    items: list[dict],
    total: float,
    currency: str = "TND",
) -> str:
    """
    Construit le message WhatsApp de confirmation de commande.
    Utilise le format texte simple (pas de template) pour les tests.
    En production, utiliser un Template approuvé Meta.
    """
    first_name = customer_name.split()[0] if customer_name else "client"
    items_text = "\n".join(
        [f"  • {item.get('name', '')} x{item.get('quantity', 1)}" for item in items]
    )

    message = (
        f"🛍️ Bonjour {first_name} !\n\n"
        f"Votre commande *#{order_id}* a été reçue sur notre boutique.\n\n"
        f"📦 *Articles commandés :*\n{items_text}\n\n"
        f"💰 *Total : {total:.2f} {currency}*\n\n"
        f"Merci de confirmer votre commande en répondant :\n\n"
        f"✅ Répondez *OUI* pour confirmer\n"
        f"❌ Répondez *NON* pour annuler\n\n"
        f"_Vous avez 24h pour répondre. Sans réponse, la commande sera annulée automatiquement._\n\n"
        f"Merci de votre confiance — HM Social Boost 🙏"
    )
    return message


async def send_whatsapp_message(phone: str, text: str) -> str | None:
    """
    Envoie un message WhatsApp texte.
    Retourne le message_id Meta en cas de succès, None sinon.

    phone: numéro au format E.164 sans espaces ex: +21655123456
    """
    phone_clean = phone.replace(" ", "").replace("-", "")

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_clean,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(META_API_URL, headers=HEADERS, json=payload)

    print(f"[WhatsApp] Status: {response.status_code}")
print(f"[WhatsApp] Response: {response.text}")
if response.status_code == 200:
    data = response.json()
    message_id = data.get("messages", [{}])[0].get("id")
    return message_id
else:
    print(f"[WhatsApp] Erreur envoi: {response.status_code} — {response.text}")
    return None

async def send_confirmation_order(
    phone: str,
    customer_name: str,
    order_id: int,
    items: list[dict],
    total: float,
    currency: str = "TND",
) -> str | None:
    """Construit et envoie le message de confirmation de commande."""
    text = build_confirmation_message(customer_name, order_id, items, total, currency)
    return await send_whatsapp_message(phone, text)


async def send_status_update(phone: str, customer_name: str, status: str, order_id: int):
    """Envoie une notification après confirmation ou annulation."""
    first_name = customer_name.split()[0] if customer_name else "client"

    if status == "confirmed":
        text = (
            f"✅ Parfait {first_name} ! Votre commande *#{order_id}* est confirmée.\n\n"
            f"Nous préparons votre colis et vous tiendrons informé(e) de l'expédition.\n\n"
            f"Merci — HM Social Boost 🙏"
        )
    else:
        text = (
            f"❌ Votre commande *#{order_id}* a bien été annulée {first_name}.\n\n"
            f"Si c'est une erreur ou si vous souhaitez repasser une commande, "
            f"n'hésitez pas à nous contacter.\n\n"
            f"À bientôt — HM Social Boost"
        )

    await send_whatsapp_message(phone, text)
