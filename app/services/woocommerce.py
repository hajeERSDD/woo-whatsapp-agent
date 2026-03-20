"""
Service WooCommerce — mise à jour des statuts de commande
via l'API REST WooCommerce v3
"""
import httpx
from app.config import get_settings

settings = get_settings()


class WooCommerceService:
    def __init__(self):
        self.base_url = f"{settings.wc_site_url.rstrip('/')}/wp-json/wc/v3"
        self.auth = (settings.wc_consumer_key, settings.wc_consumer_secret)

    async def update_order_status(self, wc_order_id: int, status: str) -> dict:
        """
        Met à jour le statut d'une commande WooCommerce.

        status: 'processing', 'cancelled', 'on-hold', 'completed', etc.
        """
        url = f"{self.base_url}/orders/{wc_order_id}"
        payload = {"status": status}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.put(url, json=payload, auth=self.auth)
            response.raise_for_status()
            return response.json()

    async def get_order(self, wc_order_id: int) -> dict:
        """Récupère les détails d'une commande WooCommerce."""
        url = f"{self.base_url}/orders/{wc_order_id}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, auth=self.auth)
            response.raise_for_status()
            return response.json()

    async def add_order_note(self, wc_order_id: int, note: str) -> dict:
        """Ajoute une note interne à une commande WooCommerce."""
        url = f"{self.base_url}/orders/{wc_order_id}/notes"
        payload = {"note": note, "customer_note": False}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, auth=self.auth)
            response.raise_for_status()
            return response.json()
            async def get_products(self) -> list:
        """Récupère les produits de la boutique WooCommerce."""
        url = f"{self.base_url}/products"
        params = {"per_page": 20, "status": "publish"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, auth=self.auth)
            response.raise_for_status()
            return response.json()
            


woocommerce_service = WooCommerceService()
