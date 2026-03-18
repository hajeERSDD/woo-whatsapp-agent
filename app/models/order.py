from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"         # Commande reçue, message pas encore envoyé
    SENT = "sent"               # Message WhatsApp envoyé, en attente réponse
    CONFIRMED = "confirmed"     # Client a confirmé → WooCommerce mis à jour
    CANCELLED = "cancelled"     # Client a annulé → WooCommerce mis à jour
    EXPIRED = "expired"         # Pas de réponse dans le délai


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    wc_order_id = Column(Integer, unique=True, index=True, nullable=False)
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(30), nullable=False)  # Format E.164: +21655xxxxxx
    customer_email = Column(String(200))
    total = Column(Float, nullable=False)
    currency = Column(String(10), default="TND")
    items_summary = Column(Text)           # JSON string des articles
    billing_address = Column(Text)
    status = Column(String(30), default=OrderStatus.PENDING)
    whatsapp_message_id = Column(String(200))   # ID du message Meta retourné
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Order wc_id={self.wc_order_id} status={self.status}>"
