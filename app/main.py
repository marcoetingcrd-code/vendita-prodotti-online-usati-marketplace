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
from app.web.routes import router as web_router
from app.bot.handler import create_bot_app, get_bot_app

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

    yield

    if TELEGRAM_BOT_TOKEN:
        bot_app = get_bot_app()
        if bot_app:
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            logger.info("Telegram Bot fermato.")


app = FastAPI(
    title="Unified Marketplace Hub",
    description="CRM operativo per vendita usato multi-utente",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# API Routes
app.include_router(products_router)
app.include_router(owners_router)
app.include_router(stats_router)

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
