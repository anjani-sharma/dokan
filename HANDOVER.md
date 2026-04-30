# Ananta — Setup & Client Handover Guide

## Overview

All client-specific details are environment variables. The code never changes.
Demo → Production = swapping values in Railway's dashboard. Takes 5 minutes.

---

## Step 1 — Get the API Keys (one-time)

### Telegram Bot Token
1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g. `Sharma Electricals Bot`
4. Choose a username: e.g. `SharmaElecBot`
5. Copy the token: `7123456789:AAF...`

### Find the Telegram Chat ID
1. Start the bot (send it `/start`)
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Look for `"chat":{"id":XXXXXXXXX}` — that number is the `SHOP_CHAT_ID`

### Anthropic API Key (Claude)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Settings → API Keys → Create Key
3. Copy: `sk-ant-api03-...`

### OpenAI API Key (Whisper)
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create new secret key
3. Copy: `sk-proj-...`

---

## Step 2 — Deploy to Railway

### First-time setup
1. Go to [railway.app](https://railway.app) and sign up (free)
2. Click **New Project → Deploy from GitHub repo**
3. Connect your GitHub and select the `Ananta` repository
4. Railway auto-detects the Procfile and deploys

### Add PostgreSQL
1. In your Railway project, click **+ New → Database → PostgreSQL**
2. Railway automatically sets `DATABASE_URL` in your environment

### Set environment variables (backend service)
In Railway → your backend service → **Variables**, add:

```
DATABASE_URL          = (auto-set by Railway PostgreSQL)
ANTHROPIC_API_KEY     = sk-ant-api03-...
OPENAI_API_KEY        = sk-proj-...
TELEGRAM_BOT_TOKEN    = 7123456789:AAF...
SHOP_CHAT_ID          = 123456789
TIMEZONE              = Asia/Kolkata
IMAGES_DIR            = /tmp/ananta_images
SHOP_NAME             = Sharma Electricals        ← display name only
```

### Set environment variables (bot service)
Same values for the bot service:
```
BACKEND_URL           = https://your-backend.railway.app
TELEGRAM_BOT_TOKEN    = 7123456789:AAF...
SHOP_CHAT_ID          = 123456789
ANTHROPIC_API_KEY     = sk-ant-api03-...
OPENAI_API_KEY        = sk-proj-...
VOICE_LANGUAGE        = hi
IMAGES_DIR            = /tmp/ananta_images
```

---

## Step 3 — Run the Demo Seed (for demo only)

SSH into Railway or run locally with the production DATABASE_URL:

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://..." python seed_demo.py
```

This creates:
- 3 suppliers, 18 products
- 4 purchase invoices (2 paid, 2 unpaid — ₹25,460 outstanding)
- 14 days of realistic daily sales
- Payments history

The demo shop name is **"Sharma Electricals"** — clearly fictional.

---

## Step 4 — Show the Demo

| What to show | How |
|---|---|
| Dashboard | Open `https://your-dashboard.railway.app` |
| Bot receiving a photo | Send any invoice photo to the bot |
| Bot receiving voice | Say "Sold 10 MCB at ₹85 and 3 wire coils" |
| Daily report | Type `/report` in Telegram |
| Weekly report | Type `/weekly` in Telegram |
| Outstanding payables | Type `/outstanding` in Telegram |
| Low stock alerts | Dashboard → Stock page (conduit pipes shown in orange) |

---

## Step 5 — Client Handover (swapping details)

### 5a — Create the client's Telegram bot
Follow Step 1 above with the client's business name.
Takes 2 minutes.

### 5b — Swap these variables in Railway dashboard

| Variable | Demo value | Replace with |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | your demo token | client's bot token |
| `SHOP_CHAT_ID` | your chat ID | client's chat ID |
| `SHOP_NAME` | Sharma Electricals | client's actual shop name |

That's it. Railway redeploys automatically (takes ~30 seconds).

### 5c — Clear demo data and start fresh

```bash
cd backend
DATABASE_URL="postgresql+asyncpg://..." python seed_demo.py --clear
```

This wipes all demo data. The client starts with an empty database.

### 5d — Optionally seed the client's existing product list

If the client gives you a list of their products (Excel/paper), run:

```bash
# Edit seed_client.py with their actual products, then:
python seed_client.py
```

---

## Cost summary for client

| Service | Monthly cost |
|---|---|
| Railway (backend + bot + DB) | ~₹500 |
| Anthropic API (Claude OCR + NLP) | ~₹400–800 |
| OpenAI API (Whisper voice) | ~₹200–400 |
| **Total** | **~₹1,100–1,700/month** |

---

## What the client needs to do themselves

Nothing technical. Just:
1. Save the Telegram bot contact on their phone
2. Send photos of invoices and payment slips to the bot
3. Send voice messages each day saying what was sold
4. Check the dashboard link on their browser/phone

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Bot not responding | Check `TELEGRAM_BOT_TOKEN` is correct in Railway variables |
| OCR reads wrong | Retake photo in better light, send again |
| Voice not understood | Speak clearly, bot will show transcript so you can correct it |
| Dashboard blank | Check `BACKEND_URL` in bot service points to correct Railway URL |
| Migration failed on deploy | Check `DATABASE_URL` is set; Railway PostgreSQL must be provisioned first |
