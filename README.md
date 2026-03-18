# 🛍️ Agent WooCommerce × WhatsApp
**HM Social Boost** — Confirmation automatique des commandes via WhatsApp

---

## 🔄 Fonctionnement

```
Nouvelle commande WooCommerce
         ↓
  Webhook → Agent FastAPI
         ↓
  Message WhatsApp envoyé au client
  (via Meta Cloud API)
         ↓
  Client répond OUI ou NON
         ↓
  Statut WooCommerce mis à jour automatiquement
  + Note interne ajoutée à la commande
```

---

## 🚀 Installation

### 1. Cloner et configurer l'environnement

```bash
git clone <repo>
cd woo-whatsapp-agent

python -m venv venv
source venv/bin/activate      # Linux/Mac
# ou: venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Configurer les variables d'environnement

```bash
cp .env.example .env
# Éditer .env avec vos vraies valeurs
```

### 3. Lancer l'agent

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

L'API sera accessible sur `http://localhost:8000`
Documentation Swagger : `http://localhost:8000/docs`

---

## ⚙️ Configuration WooCommerce

### Créer les clés API WooCommerce

1. WordPress Admin → **WooCommerce → Paramètres → Avancé → REST API**
2. Cliquer **Ajouter une clé**
3. Description : `Agent WhatsApp`
4. Permissions : **Lecture/Écriture**
5. Copier `Consumer Key` et `Consumer Secret` dans `.env`

### Configurer le Webhook

1. WordPress Admin → **WooCommerce → Paramètres → Avancé → Webhooks**
2. Cliquer **Ajouter un webhook**
3. Remplir :
   - **Nom** : `Nouvelle commande → WhatsApp`
   - **Statut** : Actif
   - **Sujet** : `Commande créée`
   - **URL de livraison** : `https://votre-domaine.com/webhooks/woocommerce/order-created`
   - **Version API** : WP REST API Integration v3
4. Copier le **Secret** dans `.env` → `WC_WEBHOOK_SECRET`

---

## 📱 Configuration Meta WhatsApp Cloud API

### Prérequis
- Compte Meta Business (business.facebook.com)
- Application Meta Developer avec produit WhatsApp

### Étapes

1. **Meta Developer Portal** → Votre app → WhatsApp → Configuration
2. Récupérer :
   - `Phone Number ID` → `META_PHONE_NUMBER_ID` dans `.env`
   - `Access Token` → `META_WHATSAPP_TOKEN` dans `.env`

3. **Configurer le webhook entrant** :
   - URL du callback : `https://votre-domaine.com/webhooks/whatsapp`
   - Token de vérification : même valeur que `META_VERIFY_TOKEN` dans `.env`
   - Champs à souscrire : `messages`

4. **Numéro de test** : En sandbox, ajouter les numéros clients dans
   Meta Developer → WhatsApp → API Setup → To

> ⚠️ **En production** : utiliser des Templates de message approuvés par Meta
> pour les messages initiaux (hors 24h de fenêtre de conversation).

---

## ⏰ Auto-annulation des commandes expirées

Ajouter une tâche cron pour annuler automatiquement les commandes sans réponse :

```bash
# Crontab - toutes les heures
0 * * * * cd /chemin/vers/agent && venv/bin/python -m app.tasks
```

Ou avec systemd timer, ou via un service comme Railway/Render Cron Jobs.

---

## 🌐 Déploiement en production

### Option recommandée : Railway

```bash
# railway.toml déjà inclus
railway up
```

### Option alternative : VPS avec nginx

```nginx
server {
    server_name votre-domaine.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Lancer avec gunicorn en production
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 📊 API de gestion

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/orders/` | Liste toutes les commandes |
| GET | `/orders/?status=sent` | Filtre par statut |
| GET | `/orders/stats/summary` | Statistiques globales |
| GET | `/orders/{id}` | Détail d'une commande |
| POST | `/orders/{id}/resend-whatsapp` | Renvoyer le message manuellement |

---

## 📝 Mots-clés reconnus

| Intention | Mots acceptés |
|-----------|---------------|
| ✅ Confirmer | OUI, YES, OK, CONFIRMER, CONFIRME, 1 |
| ❌ Annuler | NON, NO, ANNULER, ANNULE, CANCEL, 2 |

---

## 🏗️ Structure du projet

```
woo-whatsapp-agent/
├── main.py                      # Point d'entrée FastAPI
├── requirements.txt
├── .env.example                 # Template de configuration
├── app/
│   ├── config.py                # Variables d'environnement
│   ├── database.py              # SQLite async
│   ├── tasks.py                 # Auto-annulation cron
│   ├── models/
│   │   └── order.py             # Modèle SQLAlchemy
│   ├── services/
│   │   ├── whatsapp.py          # Meta Cloud API
│   │   └── woocommerce.py       # WooCommerce REST API
│   └── routers/
│       ├── webhook_woo.py       # Webhook WooCommerce entrant
│       ├── webhook_whatsapp.py  # Webhook WhatsApp entrant
│       └── orders.py            # API de gestion
```

---

Développé pour **HM Social Boost** 🚀
