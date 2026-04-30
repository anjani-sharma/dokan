# Ananta — Electrical Shop Bookkeeping App
## Implementation Plan

**App Purpose:** Help an electrical-materials shopkeeper track purchase invoices (handwritten photos), daily sales (via Telegram voice), stock levels, and payments (bank deposit / GPay). Delivers daily and weekly reports via Telegram. Includes a web dashboard.

---

## Phase 0: Documentation Discovery (COMPLETED — findings below)

**Verified APIs & Libraries**

| Component | Library / API | Version |
|---|---|---|
| Telegram bot | `python-telegram-bot` | 22.7 |
| Voice transcription | OpenAI Whisper API — `whisper-1` | REST `POST /v1/audio/transcriptions` |
| Invoice OCR | Anthropic Claude Vision — `claude-sonnet-4-6` | `POST /v1/messages` |
| NLP parsing | Anthropic Claude API — `claude-sonnet-4-6` | same |
| Backend | FastAPI | 0.136.1 |
| ORM | SQLAlchemy async (`asyncpg`) | 2.x |
| Migrations | Alembic (`-t async`) | 1.x |
| Scheduler | APScheduler `AsyncIOScheduler` | 3.11.2 |
| Frontend | React + Recharts | Recharts 3.8.1 |
| Database | PostgreSQL | 15+ |

**Allowed API Patterns (from research)**

- Telegram voice: `update.message.voice.file_id` → `bot.get_file(file_id)` → `tg_file.download_to_drive("voice.ogg")`
- Telegram photo: `update.message.photo[-1].file_id` (always last element = highest res)
- Whisper: `client.audio.transcriptions.create(model="whisper-1", file=f, language="hi", response_format="text")`
  - Accepts `.ogg` natively (Telegram voice format)
- Claude Vision: content block `{"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":"<raw_b64>"}}`
  - Image block BEFORE text block
  - Do NOT include `data:image/...;base64,` prefix in `data` field
- APScheduler: `AsyncIOScheduler`, start/stop in FastAPI `lifespan`, not `BackgroundScheduler`
- SQLAlchemy async session: `async_sessionmaker(..., expire_on_commit=False)` — mandatory

**Anti-patterns to avoid**
- Never use `message.photo[0]` — always `[-1]`
- Never use `BackgroundScheduler` in async FastAPI
- Never use `FLOAT` for money columns — always `NUMERIC(12,2)`
- Never include `data:` URI prefix in Claude base64 image data
- Never use APScheduler 4.x alpha in production

---

## Phase 1: Project Foundation & Database

**Goal:** Working repo, Docker Compose (PostgreSQL), full database schema, Alembic migrations applied.

### 1.1 Project structure

```
ananta/
├── backend/
│   ├── src/
│   │   ├── main.py          # FastAPI app + lifespan
│   │   ├── db.py            # engine, AsyncSessionLocal, Base
│   │   ├── settings.py      # pydantic-settings env config
│   │   ├── dependencies.py  # get_db Depends
│   │   ├── products/        # models, schemas, router, service
│   │   ├── invoices/        # purchase invoices
│   │   ├── sales/           # daily sales
│   │   ├── payments/        # payments
│   │   ├── stock/           # stock movements
│   │   └── reports/         # daily/weekly report generators
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── requirements.txt
│   └── Dockerfile
├── bot/
│   ├── main.py              # Telegram bot entry point
│   ├── handlers/
│   │   ├── voice.py         # voice message handler
│   │   ├── photo.py         # photo/invoice upload handler
│   │   └── text.py          # text command handler
│   ├── services/
│   │   ├── ocr.py           # Claude Vision invoice OCR
│   │   ├── transcriber.py   # Whisper voice-to-text
│   │   └── nlp.py           # Claude NLP sales extraction
│   └── requirements.txt
├── dashboard/               # React app (create-react-app or Vite)
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   ├── Invoices.tsx
│       │   ├── Stock.tsx
│       │   └── Payments.tsx
│       └── components/charts/
└── docker-compose.yml
```

### 1.2 Database schema (implement as SQLAlchemy models + Alembic migration)

```sql
CREATE TABLE suppliers (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    phone      VARCHAR(20),
    address    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id            SERIAL PRIMARY KEY,
    sku           VARCHAR(100) UNIQUE NOT NULL,
    name          VARCHAR(255) NOT NULL,
    unit          VARCHAR(50),               -- 'piece','coil','kg','box'
    cost_price    NUMERIC(12,2) NOT NULL DEFAULT 0,
    selling_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    stock_qty     NUMERIC(12,3) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(12,3) DEFAULT 0,
    supplier_id   INT REFERENCES suppliers(id),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE purchase_invoices (
    id             SERIAL PRIMARY KEY,
    invoice_number VARCHAR(100) UNIQUE NOT NULL,
    supplier_id    INT NOT NULL REFERENCES suppliers(id),
    invoice_date   DATE NOT NULL,
    total_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
    paid_amount    NUMERIC(14,2) DEFAULT 0,
    status         VARCHAR(20) DEFAULT 'unpaid'
                       CHECK (status IN ('unpaid','partial','paid')),
    image_path     TEXT,                  -- local path to invoice photo
    raw_ocr_text   TEXT,                  -- Claude OCR output
    notes          TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE purchase_invoice_items (
    id                  SERIAL PRIMARY KEY,
    purchase_invoice_id INT NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
    product_id          INT REFERENCES products(id),
    product_name_raw    VARCHAR(255),     -- fallback if product not in catalog
    qty                 NUMERIC(12,3) NOT NULL,
    unit_cost           NUMERIC(12,2) NOT NULL,
    line_total          NUMERIC(14,2) GENERATED ALWAYS AS (qty * unit_cost) STORED
);

CREATE TABLE daily_sales (
    id            SERIAL PRIMARY KEY,
    sale_date     DATE NOT NULL,
    product_id    INT REFERENCES products(id),
    product_name_raw VARCHAR(255),        -- fallback from voice parse
    qty_sold      NUMERIC(12,3) NOT NULL,
    selling_price NUMERIC(12,2) NOT NULL,
    line_total    NUMERIC(14,2) GENERATED ALWAYS AS (qty_sold * selling_price) STORED,
    source        VARCHAR(20) DEFAULT 'voice'
                      CHECK (source IN ('voice','manual','text')),
    raw_input     TEXT,                  -- original voice transcript or text
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX ux_daily_sales_date_product ON daily_sales(sale_date, product_id)
    WHERE product_id IS NOT NULL;

CREATE TABLE stock_movements (
    id             SERIAL PRIMARY KEY,
    product_id     INT NOT NULL REFERENCES products(id),
    movement_type  VARCHAR(30) NOT NULL
                       CHECK (movement_type IN ('purchase','sale','return','adjustment')),
    qty_change     NUMERIC(12,3) NOT NULL,   -- positive=in, negative=out
    reference_id   INT,
    reference_type VARCHAR(30),
    note           TEXT,
    moved_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE payments (
    id              SERIAL PRIMARY KEY,
    payment_date    DATE NOT NULL,
    amount          NUMERIC(14,2) NOT NULL,
    payment_mode    VARCHAR(20) NOT NULL
                        CHECK (payment_mode IN ('cash','bank_deposit','gpay','upi','other')),
    direction       VARCHAR(10) NOT NULL
                        CHECK (direction IN ('inflow','outflow')),
    purchase_invoice_id INT REFERENCES purchase_invoices(id),
    transaction_ref VARCHAR(100),          -- GPay UTR / bank ref
    image_path      TEXT,                  -- payment slip photo
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.3 Setup commands

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install fastapi==0.136.1 sqlalchemy[asyncio] asyncpg alembic \
            apscheduler==3.11.2 anthropic openai python-telegram-bot==22.7 \
            pydantic-settings uvicorn python-multipart pillow pytz

# Init alembic (MUST use -t async)
alembic init -t async alembic

# After editing alembic/env.py to import all models:
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

### 1.4 Verification checklist

- [ ] `docker-compose up` starts PostgreSQL without errors
- [ ] `alembic upgrade head` applies all 8 tables with zero errors
- [ ] `uvicorn src.main:app --reload` starts FastAPI, `/docs` loads
- [ ] `GET /products` returns `[]` (empty but 200 OK)

---

## Phase 2: Telegram Bot Core

**Goal:** Bot receives voice messages and photos, downloads files locally, acknowledges receipt.

### 2.1 Bot main (bot/main.py)

```python
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers.voice import handle_voice
from handlers.photo import handle_photo
from handlers.text import handle_text

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
```

### 2.2 Voice handler (bot/handlers/voice.py)

```python
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)
    local_path = f"/tmp/voice_{voice.file_unique_id}.ogg"
    await tg_file.download_to_drive(local_path)
    await update.message.reply_text("Voice received, processing...")
    # → call transcriber.py → nlp.py → POST /sales/daily
```

### 2.3 Photo handler (bot/handlers/photo.py)

```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]   # highest resolution
    tg_file = await context.bot.get_file(photo.file_id)
    local_path = f"/tmp/invoice_{photo.file_unique_id}.jpg"
    await tg_file.download_to_drive(local_path)
    caption = update.message.caption or ""
    # Determine: invoice photo or payment slip based on caption keyword
    # "invoice"/"bill" → call ocr.py → POST /invoices
    # "payment"/"deposit"/"gpay" → extract amount → POST /payments
    await update.message.reply_text("Photo received, processing...")
```

### 2.4 Verification checklist

- [ ] `/start` command returns greeting message
- [ ] Send a voice message → bot replies "Voice received, processing..."
- [ ] Send a photo → bot replies "Photo received, processing..."
- [ ] Files downloaded to `/tmp/` with correct names

---

## Phase 3: AI Processing Pipeline

**Goal:** Voice transcription → sales extraction. Photo → structured invoice data.

### 3.1 Voice transcription (bot/services/transcriber.py)

```python
from openai import OpenAI
client = OpenAI()  # reads OPENAI_API_KEY

def transcribe(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="hi",           # Hindi or "en" — set per shopkeeper preference
            response_format="text",
        )
    return result  # plain string
```

### 3.2 NLP sales extraction (bot/services/nlp.py)

```python
import anthropic, json
client = anthropic.Anthropic()

SALES_EXTRACTION_PROMPT = """
You are a bookkeeping assistant for an electrical materials shop.
Extract the items sold from the following voice transcript.
Return a JSON array of objects with keys: product_name, qty, unit, selling_price (if mentioned).
If selling_price is unknown, omit it. Be tolerant of Hindi/Hinglish text.

Transcript:
{transcript}
"""

def extract_sales(transcript: str) -> list[dict]:
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role":"user","content": SALES_EXTRACTION_PROMPT.format(transcript=transcript)}]
    )
    return json.loads(msg.content[0].text)
```

### 3.3 Invoice OCR (bot/services/ocr.py)

```python
import anthropic, base64, json
client = anthropic.Anthropic()

INVOICE_OCR_PROMPT = """
This is a handwritten purchase invoice from an electrical materials supplier.
Extract all fields: supplier name, invoice number, date, line items (product name, qty, unit, unit price, line total), and grand total.
Return structured JSON with keys: supplier_name, invoice_number, invoice_date (YYYY-MM-DD), items (array), total_amount.
"""

def ocr_invoice(image_path: str) -> dict:
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":image_data}},
                {"type":"text","text":INVOICE_OCR_PROMPT},
            ]
        }]
    )
    return json.loads(msg.content[0].text)
```

### 3.4 Verification checklist

- [ ] Send a voice message "Sold 10 pieces of MCB and 2 coils of wire" → transcript returns readable English/Hindi text
- [ ] NLP extract returns `[{"product_name":"MCB","qty":10,"unit":"pieces"},{"product_name":"wire","qty":2,"unit":"coils"}]`
- [ ] Upload a test handwritten invoice photo → OCR returns JSON with supplier, items, total
- [ ] Edge case: blurry photo → Claude returns partial data without crashing

---

## Phase 4: Business Logic APIs

**Goal:** FastAPI routes for products, invoices, sales, stock, payments. Bot calls these after AI processing.

### 4.1 Core API routes

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/products` | List / create products |
| `PUT` | `/products/{id}` | Update price or stock |
| `GET/POST` | `/invoices` | List / create purchase invoices |
| `PUT` | `/invoices/{id}` | Update (mark paid, edit items) |
| `GET/POST` | `/sales/daily` | List / record daily sales |
| `PUT` | `/sales/daily/{id}` | Edit a sale entry |
| `DELETE` | `/sales/daily/{id}` | Remove a sale entry |
| `GET/POST` | `/payments` | List / record payments |
| `GET` | `/stock/movements` | Audit trail |
| `GET` | `/reports/daily` | Today's summary |
| `GET` | `/reports/weekly` | This week's summary |

### 4.2 Stock update rule

When a `daily_sales` record is created → also insert a `stock_movements` row with:
- `movement_type = 'sale'`
- `qty_change = -qty_sold`
- `reference_id = daily_sales.id`, `reference_type = 'daily_sale'`

Then `UPDATE products SET stock_qty = stock_qty - qty_sold WHERE id = product_id`.

When a `purchase_invoice_items` row is created → insert `stock_movements` with `movement_type = 'purchase'`, `qty_change = +qty`.

### 4.3 Bot integration flow (after AI processing)

**Voice → sales:**
```
voice message → transcriber.transcribe() → nlp.extract_sales()
→ for each item: fuzzy-match product_name to products table
→ POST /sales/daily for each matched item
→ reply with formatted confirmation message
```

**Photo (invoice) → purchase invoice:**
```
photo → ocr.ocr_invoice()
→ POST /suppliers (upsert by name)
→ POST /invoices with line items
→ POST /payments if a payment slip was included
→ reply with summary: "Invoice #XX from Supplier Y: ₹ZZ recorded"
```

### 4.4 Verification checklist

- [ ] `POST /sales/daily` with `{sale_date,product_id,qty_sold,selling_price,source:"voice"}` → 201 created
- [ ] `GET /products/{id}` shows updated `stock_qty` after sale
- [ ] `GET /stock/movements` shows both `purchase` and `sale` entries
- [ ] `PUT /sales/daily/{id}` updates the record and adjusts stock accordingly
- [ ] `DELETE /sales/daily/{id}` removes record and reverses stock adjustment

---

## Phase 5: Scheduled Reports

**Goal:** Bot sends a daily summary at 8 PM and a weekly statement every Monday 9 AM (IST).

### 5.1 Scheduler setup in FastAPI lifespan (src/main.py)

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")
scheduler = AsyncIOScheduler(timezone=IST)

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(send_daily_report, CronTrigger(hour=20, minute=0, timezone=IST))
    scheduler.add_job(send_weekly_report, CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=IST))
    scheduler.start()
    yield
    scheduler.shutdown()
```

### 5.2 Daily report format (sent via Telegram)

```
📊 *Daily Report — 30 Apr 2026*

Items Sold Today:
• MCB 32A × 15 pcs — ₹3,750
• Wire 2.5mm × 3 coils — ₹1,800
• Switch Board × 8 pcs — ₹640

Total Sales: ₹6,190
Payments Received: ₹4,500 (GPay)
Payments Made: ₹12,000 (Bank Deposit to XYZ Electricals)

Stock Alerts (below reorder level):
⚠️ MCB 16A — only 5 pcs left
```

### 5.3 Weekly report format

```
📅 *Weekly Statement — Week ending 4 May 2026*

Total Sales: ₹38,400
Total Purchases: ₹52,000
Payments Out: ₹45,000
Payments In: ₹41,000

Outstanding Payables: ₹7,000 (to Ravi Electricals)

Top 5 Items Sold This Week:
1. MCB 32A — 68 pcs
2. Wire 2.5mm — 14 coils
3. Switch Board — 42 pcs
...
```

### 5.4 Telegram send helper

```python
# Use HTML parse_mode to avoid MarkdownV2 escaping issues
await bot.send_message(
    chat_id=SHOP_CHAT_ID,
    text=report_html,
    parse_mode="HTML"
)
```

### 5.5 Verification checklist

- [ ] Scheduler starts without error in FastAPI lifespan
- [ ] Manual trigger `GET /reports/daily` returns correct JSON
- [ ] Bot sends formatted daily report (test with manual API call)
- [ ] Weekly report correctly aggregates all 7 days

---

## Phase 6: Web Dashboard

**Goal:** React SPA with four pages: Overview, Invoices, Stock, Payments.

### 6.1 Tech

```bash
npm create vite@latest dashboard -- --template react-ts
cd dashboard && npm install recharts@3.8.1 axios react-router-dom
```

### 6.2 Dashboard page components

**Overview (Dashboard.tsx)**
- KPI cards: Total Sales This Week, Outstanding Payables, Low-Stock Items count
- `BarChart` (Recharts 3.8.1): Daily sales vs purchases for last 7 days
- `LineChart`: Cumulative sales for current month

```jsx
// Sales bar chart pattern (verified from Recharts 3.8.1 docs)
<ResponsiveContainer width="100%" height={300}>
  <BarChart data={weeklyData} margin={{top:10,right:20,left:0,bottom:0}}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="day" />
    <YAxis tickFormatter={v => `₹${v}`} />
    <Tooltip formatter={v => `₹${v}`} />
    <Legend />
    <Bar dataKey="sales" fill="#4f46e5" name="Sales" />
    <Bar dataKey="purchases" fill="#f59e0b" name="Purchases" />
  </BarChart>
</ResponsiveContainer>
```

**Invoices page**
- Table: Invoice #, Supplier, Date, Amount, Paid, Status (unpaid/partial/paid)
- Filter by status, date range
- Click row → expand to show line items
- Upload invoice button (calls `/invoices` API)

**Stock page**
- Table: Product, SKU, Unit, Current Stock, Reorder Level, Status
- Highlight rows where `stock_qty <= reorder_level` in orange
- Stock movement log (paginated)

**Payments page**
- Table: Date, Mode, Direction, Amount, Reference, Invoice
- Filter by mode (GPay / Bank Deposit / Cash)
- Running balance view

### 6.3 API integration

```typescript
// src/api/client.ts
import axios from 'axios';
const api = axios.create({ baseURL: 'http://localhost:8000' });
export default api;

// Usage
const { data } = await api.get('/reports/daily');
```

### 6.4 Verification checklist

- [ ] `npm run dev` starts without errors
- [ ] Overview page loads KPI cards with real data from API
- [ ] Bar chart renders correctly with `ResponsiveContainer` (parent div must have explicit height)
- [ ] Invoices table shows uploaded invoice after bot processing
- [ ] Stock page highlights low-stock products
- [ ] Payments page shows GPay and bank deposit entries separately

---

## Phase 7: End-to-End Integration & Hardening

**Goal:** All components talk to each other correctly. Edge cases handled. Production-ready config.

### 7.1 Edge cases to handle

| Scenario | Handling |
|---|---|
| Voice message in Hindi | Whisper `language="hi"` — falls back gracefully |
| Unrecognized product name in voice | Create `daily_sales` with `product_name_raw`, flag for manual mapping |
| Blurry/incomplete invoice photo | Claude returns partial JSON → store raw OCR text, alert user |
| Duplicate invoice number | `UNIQUE` constraint on `invoice_number` → bot replies "Invoice already recorded" |
| Multiple products in one voice message | NLP returns array → create multiple `daily_sales` rows in one transaction |
| User says "kal wala order cancel karo" | Text handler with Claude NLP → identify and delete/edit record |
| Stock goes negative | Warn user in Telegram reply; allow override |

### 7.2 Edit flow via text/voice

User can send:
- "Remove 5 MCB from today's sales" → bot identifies record, calls `PUT /sales/daily/{id}`
- "Change yesterday's wire sale to 4 coils" → bot calls `PUT /sales/daily/{id}`
- Voice message with corrections → same flow through Whisper + NLP

NLP prompt should include an `intent` field: `"record_sale"`, `"edit_sale"`, `"delete_sale"`, `"query"`.

### 7.3 .env file structure

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://ananta:ananta@localhost:5432/shopdb
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
SHOP_CHAT_ID=...          # Telegram chat ID of the shopkeeper
```

### 7.4 Docker Compose

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ananta
      POSTGRES_PASSWORD: ananta
      POSTGRES_DB: shopdb
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  backend:
    build: ./backend
    env_file: ./backend/.env
    ports: ["8000:8000"]
    depends_on: [db]
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000

  bot:
    build: ./bot
    env_file: ./bot/.env
    depends_on: [backend]

volumes:
  pgdata:
```

### 7.5 Final verification checklist

- [ ] Full flow: send voice "Sold 10 MCB" → daily sales recorded → stock decremented → daily report includes it
- [ ] Full flow: upload handwritten invoice photo → OCR extracts data → invoice created → stock incremented
- [ ] Full flow: upload payment slip with caption "gpay" → payment recorded against invoice → invoice status updated
- [ ] Edit flow: "Change today's MCB sale to 8 pieces" → bot updates record
- [ ] Weekly report sent on Monday with correct 7-day aggregation
- [ ] Dashboard shows correct numbers matching database

---

## Execution Order

1. **Phase 1** → Working database + FastAPI skeleton
2. **Phase 2** → Telegram bot receives messages
3. **Phase 3** → AI pipeline processes voice + photos
4. **Phase 4** → Business logic APIs (bot calls these after Phase 3)
5. **Phase 5** → Scheduled reports (needs Phase 4 data)
6. **Phase 6** → Dashboard (reads from Phase 4 APIs)
7. **Phase 7** → Integration, edge cases, production config

Each phase is self-contained and can be implemented in a fresh chat context using this plan as the sole reference.
