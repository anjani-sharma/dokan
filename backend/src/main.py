from contextlib import asynccontextmanager

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.settings import settings
from src.products.router import router as products_router
from src.invoices.router import router as invoices_router
from src.sales.router import router as sales_router
from src.payments.router import router as payments_router
from src.stock.router import router as stock_router
from src.reports.router import router as reports_router

IST = pytz.timezone(settings.timezone)
scheduler = AsyncIOScheduler(timezone=IST)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.reports.service import send_daily_report, send_weekly_report

    scheduler.add_job(
        send_daily_report,
        CronTrigger(hour=20, minute=0, timezone=IST),
        id="daily_report",
        replace_existing=True,
    )
    scheduler.add_job(
        send_weekly_report,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=IST),
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Ananta Shop API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router, prefix="/products", tags=["products"])
app.include_router(invoices_router, prefix="/invoices", tags=["invoices"])
app.include_router(sales_router, prefix="/sales", tags=["sales"])
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(stock_router, prefix="/stock", tags=["stock"])
app.include_router(reports_router, prefix="/reports", tags=["reports"])


@app.get("/health")
async def health():
    return {"status": "ok"}
