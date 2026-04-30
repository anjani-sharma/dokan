# Ananta — Free Tier Setup Guide
**Stack: Supabase (DB) + Render (backend) + Cloudflare R2 (images) + Vercel (dashboard)**
Total cost: **₹0/month**

---

## What you need before starting

- GitHub account (code must be pushed)
- Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Your Telegram chat ID (send a message to [@userinfobot](https://t.me/userinfobot))
- Anthropic API key (console.anthropic.com)
- OpenAI API key (platform.openai.com)

---

## Step 1 — Push your code to GitHub

```bash
cd /path/to/Ananta
git init                        # if not already a repo
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/ananta.git
git push -u origin master
```

---

## Step 2 — Supabase (Free PostgreSQL)

1. Go to [supabase.com](https://supabase.com) → **New project**
2. Pick a name (`ananta`), region closest to India (Singapore), set a database password
3. Wait ~2 minutes for it to provision
4. Go to **Settings → Database → Connection string → URI**
5. Copy the URI — it looks like:
   ```
   postgresql://postgres.xxxxx:PASSWORD@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
6. **Change `postgresql://` to `postgresql+asyncpg://`** (needed for SQLAlchemy async)
7. Save this — you'll paste it into Render as `DATABASE_URL`

---

## Step 3 — Cloudflare R2 (Free image storage)

> Skip this step if you're just testing. Images will save to /tmp (deleted on restart).

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → **R2 Object Storage**
2. Click **Create bucket**, name it `ananta-images`
3. **Enable public access**: bucket → Settings → Public Access → Allow Access → copy the URL
   - Looks like: `https://pub-xxxxxxxxxxxxxxxx.r2.dev`
4. Create API token: R2 → **Manage R2 API tokens** → Create token
   - Permissions: **Object Read & Write**
   - Apply to: your bucket only
   - Copy **Access Key ID** and **Secret Access Key**
5. Your **Account ID** is shown on the top-right of the Cloudflare dashboard

---

## Step 4 — Render (Free Backend + Bot)

1. Go to [render.com](https://render.com) → New → **Blueprint**
2. Connect your GitHub repo
3. Render will detect `render.yaml` and create the `ananta-backend` service automatically
4. Before clicking Deploy, go to the service → **Environment** → add all secret variables:

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | postgresql+asyncpg://... from Supabase |
   | `ANTHROPIC_API_KEY` | sk-ant-... |
   | `OPENAI_API_KEY` | sk-proj-... |
   | `TELEGRAM_BOT_TOKEN` | 7123...:AAF... |
   | `SHOP_CHAT_ID` | your numeric Telegram ID |
   | `APP_BASE_URL` | **leave blank for now** (fill after first deploy) |
   | `R2_ACCOUNT_ID` | from Cloudflare (or leave blank) |
   | `R2_ACCESS_KEY_ID` | from Cloudflare (or leave blank) |
   | `R2_SECRET_ACCESS_KEY` | from Cloudflare (or leave blank) |
   | `R2_BUCKET_NAME` | `ananta-images` (or leave blank) |
   | `R2_PUBLIC_URL` | https://pub-xxx.r2.dev (or leave blank) |

5. Click **Deploy** — first deploy runs Alembic migrations automatically (via `start.sh`)
6. Wait for deploy to finish (2–4 min). You'll see a URL like:
   `https://ananta-backend.onrender.com`

### Register the Telegram webhook

After the first deploy succeeds:

1. In Render → Environment, set `APP_BASE_URL` = `https://ananta-backend.onrender.com`
2. Click **Save** — Render will redeploy (~1 min)
3. The webhook registers automatically on startup. Verify:
   ```
   curl https://ananta-backend.onrender.com/health
   ```
   Should return `{"status": "ok"}`

4. Test the bot: open Telegram, send `/start` to your bot — it should reply.

---

## Step 5 — Vercel (Free Dashboard)

1. Go to [vercel.com](https://vercel.com) → **New Project** → Import from GitHub
2. Select your repo, set **Root Directory** to `dashboard`
3. Framework: **Vite** (auto-detected)
4. No environment variables needed — API calls go through the proxy in `vercel.json`
5. Click **Deploy** — you'll get a URL like `https://ananta-dashboard.vercel.app`
6. Open it — the dashboard should load and fetch data from your Render backend

---

## Step 6 — Keep Render awake (free tier sleeps after 15 min)

Render free services sleep when idle. The Telegram webhook wakes them up automatically when a message arrives (~30 sec cold start). If you want zero cold starts:

**Option A — UptimeRobot (free)**
1. Go to [uptimerobot.com](https://uptimerobot.com) → Add Monitor
2. Type: HTTP(S), URL: `https://ananta-backend.onrender.com/health`
3. Interval: 5 minutes
4. That's it — free tier allows 50 monitors

**Option B — Accept the cold start**
The first Telegram message after idle gets a 30-sec delay. After that it's fast. For a shop use-case this is usually fine.

---

## Step 7 — Seed demo data (for client presentation)

```bash
# Install deps locally
pip install httpx asyncpg sqlalchemy alembic pydantic-settings

# Run seeder against live Render database
cd backend
DATABASE_URL="postgresql+asyncpg://..." python seed_demo.py

# To wipe and re-seed (before client handover)
python seed_demo.py --clear
```

---

## Step 8 — Swap client details (handover)

When the client is ready, update 3 Render environment variables:

| Variable | Demo value | Client value |
|----------|-----------|--------------|
| `TELEGRAM_BOT_TOKEN` | your demo bot | client's bot from @BotFather |
| `SHOP_CHAT_ID` | your Telegram ID | client's Telegram ID |
| `SHOP_NAME` | Sharma Electricals | client's actual shop name |

Then run `python seed_demo.py --clear` to wipe demo data.

---

## Troubleshooting

**Bot not responding after deploy**
- Check Render logs for errors
- Make sure `APP_BASE_URL` is set correctly (no trailing slash)
- Verify webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

**Database connection errors**
- Supabase free tier pauses after 1 week of inactivity — go to Supabase dashboard and click Resume
- Make sure you used `postgresql+asyncpg://` not `postgresql://`

**Photos not saving permanently**
- Without R2, images save to `/tmp` which is wiped on Render restart
- Set up Cloudflare R2 (Step 3) to make image URLs permanent

**Dashboard showing no data**
- Check browser console for API errors
- Verify Render is awake (visit the health URL)
- Check `vercel.json` has the correct Render URL

---

## Free tier limits summary

| Service | Free limit | When you'll hit it |
|---------|-----------|-------------------|
| Supabase DB | 500 MB storage, 2 GB bandwidth | ~1 year of normal use |
| Render web | 750 hrs/month, sleeps after 15 min | Never (only 1 service) |
| Cloudflare R2 | 10 GB storage, 1M requests/month | ~10,000 invoice photos |
| Vercel | 100 GB bandwidth, unlimited deploys | Never for a shop dashboard |

All limits are very generous for a single-shop use case.
