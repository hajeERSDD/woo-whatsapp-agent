"""
Tâche de fond — Auto-annulation des commandes expirées
À lancer via un cron job ou APScheduler
"""
import asyncio
from datetime import datetime
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.order import Order, OrderStatus
from app.services.woocommerce import woocommerce_service
from app.services.whatsapp import send_whatsapp_message
from app.config import get_settings

settings = get_settings()


async def cancel_expired_orders():
    """
    Annule automatiquement les commandes sans réponse après le délai configuré.
    À appeler toutes les heures via cron ou scheduler.
    """
    async with AsyncSessionLocal() as db:
        # Chercher les commandes envoyées et expirées
        result = await db.execute(
            select(Order)
            .where(Order.status == OrderStatus.SENT)
            .where(Order.expires_at < datetime.utcnow())
        )
        expired_orders = result.scalars().all()

        print(f"[AutoCancel] {len(expired_orders)} commande(s) expirée(s) trouvée(s)")

        for order in expired_orders:
            try:
                # Mettre à jour WooCommerce
                await woocommerce_service.update_order_status(
                    order.wc_order_id, settings.wc_status_cancelled
                )
                await woocommerce_service.add_order_note(
                    order.wc_order_id,
                    "⏰ Commande annulée automatiquement — pas de réponse WhatsApp dans le délai imparti."
                )

                # Notifier le client
                await send_whatsapp_message(
                    order.customer_phone,
                    f"⏰ Bonjour {order.customer_name.split()[0]} !\n\n"
                    f"Votre commande *#{order.wc_order_id}* a été annulée automatiquement "
                    f"car nous n'avons pas reçu de confirmation dans les {settings.auto_cancel_hours}h.\n\n"
                    f"Si c'est une erreur, contactez-nous directement.\n\n"
                    f"— HM Social Boost"
                )

                # Mise à jour en base
                order.status = OrderStatus.EXPIRED
                await db.commit()
                print(f"[AutoCancel] ✅ Commande #{order.wc_order_id} expirée et annulée")

            except Exception as e:
                print(f"[AutoCancel] ❌ Erreur commande #{order.wc_order_id}: {e}")


if __name__ == "__main__":
    asyncio.run(cancel_expired_orders())
