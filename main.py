"""
WooCommerce × WhatsApp Confirmation Agent
HM Social Boost — Hajer Manai
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import webhook_woo, webhook_whatsapp, orders
from app.database import init_db

app = FastAPI(
    title="WooCommerce WhatsApp Agent",
    description="Agent de confirmation automatique des commandes via WhatsApp",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_db()

# Routers
app.include_router(webhook_woo.router, prefix="/webhooks", tags=["WooCommerce"])
app.include_router(webhook_whatsapp.router, prefix="/webhooks", tags=["WhatsApp"])
app.include_router(orders.router, prefix="/orders", tags=["Orders"])

@app.get("/")
async def root():
    return {"status": "Agent actif", "service": "HM Social Boost WooCommerce Agent"}
