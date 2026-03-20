import httpx
from app.config import get_settings

settings = get_settings()

META_API_URL = (
    f"https://graph.facebook.com/v19.0/{settings.meta_phone_number_id}/messages"
)
HEADERS = {
    "Authorization": f"Bearer {settings.meta_whatsapp_token}",
    "Content-Type": "application/json",
}

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def build_confirmation_message(customer_name, order_id, items, total, currency="TND"):
    first_name = customer_name.split()[0] if customer_name else "client"
    items_text = "\n".join([f"  • {i.get('name','')} x{i.get('quantity',1)}" for i in items])
    return (
        f"Bonjour {first_name} !\n\n"
        f"Votre commande *#{order_id}* a été reçue.\n\n"
        f"Articles :\n{items_text}\n\n"
        f"Total : {total:.2f} {currency}\n\n"
        f"Confirmez votre commande :\n"
        f"OUI pour confirmer\n"
        f"NON pour annuler\n\n"
        f"Sans réponse dans 24h, la commande sera annulée.\n\n"
        f"Merci - HM Social Boost"
    )


async def ask_claude(customer_message, order_info, products_info, conversation_history):
    system = f"""Tu es l'assistant intelligent de HM Social Boost, une boutique en ligne tunisienne.
Tu communiques avec les clients via WhatsApp après une commande.

COMMANDE DU CLIENT :
{order_info}

PRODUITS DISPONIBLES :
{products_info}

INFOS LIVRAISON :
- Délai standard : 24-48h après confirmation
- Livraison partout en Tunisie
- Paiement à la livraison (cash on delivery)

RÈGLES :
- Réponds dans la même langue que le client (français, arabe, anglais)
- Messages courts et clairs (max 4 lignes) adaptés à WhatsApp
- Si le client confirme la commande → termine par INTENT:confirm
- Si le client annule la commande → termine par INTENT:cancel
- Si c'est une question → réponds et termine par INTENT:question
- Ne jamais inventer des infos produits
- Être chaleureux et professionnel"""

    messages = conversation_history + [{"role": "user", "content": customer_message}]

    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 300,
        "system": system,
        "messages": messages,
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        return data["content"][0]["text"]
    else:
        print(f"[Claude] Erreur: {response.status_code} — {response.text}")
        return None


def detect_intent_from_response(claude_response):
    if "INTENT:confirm" in claude_response:
        return "confirm"
    elif "INTENT:cancel" in claude_response:
        return "cancel"
    else:
        return "question"


def clean_response(claude_response):
    return claude_response.replace("INTENT:confirm", "").replace("INTENT:cancel", "").replace("INTENT:question", "").strip()


async def send_whatsapp_message(phone: str, text: str):
    phone_clean = phone.replace(" ", "").replace("-", "").replace("+", "")
    if phone_clean.startswith("00"):
        phone_clean = phone_clean[2:]
    if phone_clean.startswith("0"):
        phone_clean = "216" + phone_clean[1:]
    if not phone_clean.startswith("216"):
        phone_clean = "216" + phone_clean

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_clean,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(META_API_URL, headers=HEADERS, json=payload)

    print(f"[WhatsApp] Numero: {phone_clean}")
    print(f"[WhatsApp] Status: {response.status_code}")
    print(f"[WhatsApp] Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        return data.get("messages", [{}])[0].get("id")
    else:
        print(f"[WhatsApp] Erreur: {response.status_code} — {response.text}")
        return None


async def send_confirmation_order(phone, customer_name, order_id, items, total, currency="TND"):
    text = build_confirmation_message(customer_name, order_id, items, total, currency)
    return await send_whatsapp_message(phone, text)


async def send_status_update(phone, customer_name, status, order_id):
    first_name = customer_name.split()[0] if customer_name else "client"
    if status == "confirmed":
        text = (
            f"Parfait {first_name} ! Commande #{order_id} confirmée.\n\n"
            f"Livraison dans 24-48h. Merci - HM Social Boost"
        )
    else:
        text = (
            f"Commande #{order_id} annulée {first_name}.\n\n"
            f"N'hésitez pas à recommander. A bientôt - HM Social Boost"
        )
    await send_whatsapp_message(phone, text)
