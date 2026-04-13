import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from app.config import HOST, PORT, BASE_URL, UPLOAD_DIR, TELEGRAM_BOT_TOKEN
from app.database import init_db
from app.api.products import router as products_router
from app.api.owners import router as owners_router
from app.api.stats import router as stats_router
from app.api.dashboard import router as dashboard_router
from app.api.conversations import router as conversations_router
from app.api.events import router as events_router
from app.api.search import router as search_router
from app.web.routes import router as web_router
from app.bot.handler import create_bot_app, get_bot_app
from app.services.email_ingest import email_hub_loop, is_configured as email_hub_configured

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inizializzazione database...")
    await init_db()

    if TELEGRAM_BOT_TOKEN:
        logger.info("Avvio Telegram Bot in polling mode...")
        bot_app = create_bot_app()
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram Bot avviato!")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN non configurato — bot disabilitato")

    # Email Hub background task
    email_task = None
    if email_hub_configured():
        logger.info("Avvio Email Hub...")
        email_task = asyncio.create_task(email_hub_loop())
    else:
        logger.info("Email Hub non configurato — disabilitato")

    yield

    if email_task:
        email_task.cancel()

    if TELEGRAM_BOT_TOKEN:
        bot_app = get_bot_app()
        if bot_app:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            logger.info("Telegram Bot fermato.")


app = FastAPI(
    title="Sales Command Center",
    description="Centro di comando vendite multi-piattaforma",
    version="2.0.0",
    lifespan=lifespan,
)

# Static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# API Routes
app.include_router(products_router)
app.include_router(owners_router)
app.include_router(stats_router)
app.include_router(dashboard_router)
app.include_router(conversations_router)
app.include_router(events_router)
app.include_router(search_router)

# Web Panel
app.include_router(web_router)


@app.get("/")
async def root():
    return RedirectResponse(url="/panel")


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=int(PORT), reload=True)
