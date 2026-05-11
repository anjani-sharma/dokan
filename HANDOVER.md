# Ananta — Setup & Client Handover Guide

---

## Architecture

```
DigitalOcean Droplet $12/month (Ubuntu 22.04, 2GB RAM)
│
├── nginx          → handles all web traffic, SSL
├── dashboard      → React app (your browser dashboard)
├── backend        → FastAPI (the brain)
├── bot            → Telegram bot (always listening)
├── db             → PostgreSQL (all transaction data)
│
├── pgdata volume  → database files (NEVER deleted on redeploy)
└── uploads volume → all invoice photos + payment slips (NEVER deleted)
```

Everything runs in Docker. `deploy.sh` updates the app without losing any data.

---

## Step 1 — What you need to collect first

Get these 4 things before touching the server:

### A. Telegram Bot Token (2 min, free)
1. Open Telegram → search **@BotFather** → send `/newbot`
2. Give it a name: e.g. `Sharma Electricals Bot`
3. Give it a username: e.g. `SharmaElecBot`
4. Copy the token: `7123456789:AAF...`

### B. Your Telegram Chat ID
1. Message your new bot: `/start`
2. Visit in browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id": 123456789}` — that number is your Chat ID

### C. Anthropic API Key (Claude — for OCR and NLP)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Settings → API Keys → Create Key
3. Copy: `sk-ant-api03-...`
4. Add a payment method (pay-as-you-go, ~₹400–800/month for this app)

### D. OpenAI API Key (Whisper — for voice transcription)
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create new secret key
3. Copy: `sk-proj-...`
4. Add a payment method (~₹200–400/month)

---

## Step 2 — Create the DigitalOcean server

1. Go to [digitalocean.com](https://digitalocean.com) → sign up
2. **Create Droplet:**
   - Image: **Ubuntu 22.04 LTS**
   - Size: **Basic → Regular → $12/mo** (2GB RAM / 1 CPU / 50GB disk)
   - Region: **Bangalore** (closest to India)
   - Authentication: SSH Key (recommended) or Password
3. Note the droplet's **IP address** (e.g. `165.22.45.123`)

---

## Step 3 — Set up the server (one command)

SSH into your new server:
```bash
ssh root@YOUR_DROPLET_IP
```

Run the setup script:
```bash
curl -sO https://raw.githubusercontent.com/anjani-sharma/dokan/main/setup_server.sh
bash setup_server.sh
```

This installs Docker, sets up the firewall, clones the app, and configures auto-start. Takes ~3 minutes.

---

## Step 4 — Add your credentials

```bash
nano /opt/ananta/.env
```

Fill in these values (everything else can stay as-is):

```bash
POSTGRES_PASSWORD=choose_a_strong_password_here

ANTHROPIC_API_KEY=sk-ant-api03-...
OPENAI_API_KEY=sk-proj-...

TELEGRAM_BOT_TOKEN=7123456789:AAF...
SHOP_CHAT_ID=123456789

SHOP_NAME=Sharma Electricals

# DOKANE dashboard PIN gate. Mutations (POST/PUT/DELETE) require this PIN.
# Leave blank in dev to disable. Rotate DASHBOARD_SECRET to invalidate sessions.
DASHBOARD_PIN=1234
DASHBOARD_SECRET=long-random-string-keep-secret
```

Save: `Ctrl+X` → `Y` → `Enter`

---

## Step 5 — Deploy

```bash
bash /opt/ananta/deploy.sh
```

This builds all containers, runs database migrations, and starts everything. Takes ~4 minutes first time.

---

## Step 6 — Load demo data (for client presentation)

```bash
cd /opt/ananta
docker compose exec backend python seed_demo.py
```

Populates 14 days of realistic sales, invoices, payments, and products.

---

## Step 7 — Test everything

Open Telegram, message your bot:

| Test | What to send | Expected result |
|---|---|---|
| Bot online | `/start` | Menu message appears |
| Voice sales | Say "Sold 10 MCB at ₹85" | ✅ Sale recorded confirmation |
| Invoice photo | Send any invoice photo | 🧾 OCR result + Save/Edit/Cancel buttons |
| Payment slip | Send GPay screenshot | 💸 Payment detected + Save buttons |
| Daily report | `/report` | Today's sales summary |
| Weekly report | `/weekly` | This week's statement |
| Outstanding | `/outstanding` | Unpaid invoices list |

Open the dashboard: `http://YOUR_DROPLET_IP`

---

## Client Handover — Swapping Details (5 minutes)

### 1. Create the client's Telegram bot
Follow Step 1A above with the client's actual shop name.

### 2. Update 4 values on the server

```bash
ssh root@YOUR_DROPLET_IP
nano /opt/ananta/.env
```

Change:
```bash
TELEGRAM_BOT_TOKEN=  ← client's bot token
SHOP_CHAT_ID=        ← client's chat ID
SHOP_NAME=           ← client's actual shop name (e.g. "Ravi Electricals")
```

### 3. Clear demo data and restart

```bash
cd /opt/ananta
docker compose exec backend python seed_demo.py --clear
bash deploy.sh
```

### 4. Done ✅

Client opens Telegram, messages their bot, and starts using it. Their invoice photos and data are stored permanently on the server.

---

## Updates — pushing new features to the live server

Whenever you update the code on your laptop:
```bash
# On your laptop
git push origin main

# On the server
ssh root@YOUR_DROPLET_IP
bash /opt/ananta/deploy.sh
```

Zero downtime. Data is never touched.

---

## Backups (strongly recommended for real client)

Enable DigitalOcean automated backups: **$2.40/month extra**
- Go to your Droplet → Backups → Enable
- Weekly snapshots kept for 4 weeks
- One click to restore if anything goes wrong

Also backup the database manually anytime:
```bash
docker compose exec db pg_dump -U ananta shopdb > backup_$(date +%Y%m%d).sql
```

---

## Monitoring — is everything running?

```bash
ssh root@YOUR_DROPLET_IP
docker compose -f /opt/ananta/docker-compose.yml ps
```

All 5 services should show `running`.

View bot logs (most useful for debugging):
```bash
docker compose -f /opt/ananta/docker-compose.yml logs -f bot
```

---

## Monthly costs

| Service | Cost |
|---|---|
| DigitalOcean droplet | ₹1,000/mo ($12) |
| DigitalOcean backups | ₹200/mo ($2.40) |
| Anthropic (Claude OCR + NLP) | ₹400–800/mo |
| OpenAI (Whisper voice) | ₹200–400/mo |
| **Total** | **₹1,800–2,400/mo** |

---

## What the client needs to do

Absolutely nothing technical. Just:
1. Save the bot on their phone (Telegram contact)
2. Send invoice photos to the bot when they receive invoices
3. Send a voice note at end of day: *"Sold X MCB, Y wire coils"*
4. Check the dashboard on any browser: `http://YOUR_IP`

Everything else is automatic — daily report at 8 PM, weekly report Monday 9 AM.
