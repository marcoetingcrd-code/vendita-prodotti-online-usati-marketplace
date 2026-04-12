import httpx
from app.config import TELEGRAM_BOT_TOKEN, OWNER_CHAT_IDS

API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_telegram_message(chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
    """Invia un messaggio Telegram a un singolo chat_id."""
    if not TELEGRAM_BOT_TOKEN:
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })
        return resp.status_code == 200


async def send_telegram_photo(chat_id: str, photo_path: str, caption: str = "") -> bool:
    """Invia una foto via Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        return False

    async with httpx.AsyncClient() as client:
        with open(photo_path, "rb") as f:
            resp = await client.post(
                f"{API_URL}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                files={"photo": f},
            )
        return resp.status_code == 200


async def notify_all_owners(text: str) -> None:
    """Invia notifica a tutti gli owner registrati."""
    for chat_id in OWNER_CHAT_IDS:
        await send_telegram_message(chat_id, text)


async def notify_product_created(product_title: str, owner_name: str, price: float | None) -> None:
    price_str = f"€{price:.0f}" if price else "da definire"
    text = (
        f"📦 <b>Nuovo prodotto aggiunto</b>\n\n"
        f"<b>{product_title}</b>\n"
        f"👤 Proprietario: {owner_name}\n"
        f"💰 Prezzo: {price_str}\n"
    )
    await notify_all_owners(text)


async def notify_product_sold(product_title: str, owner_name: str, price_sold: float) -> None:
    text = (
        f"🎉 <b>VENDUTO!</b>\n\n"
        f"<b>{product_title}</b>\n"
        f"👤 Proprietario: {owner_name}\n"
        f"💰 Venduto a: €{price_sold:.0f}\n"
    )
    await notify_all_owners(text)


async def notify_price_reminder(product_title: str, days_online: int, current_price: float) -> None:
    text = (
        f"⏰ <b>Promemoria prezzo</b>\n\n"
        f"<b>{product_title}</b> è online da <b>{days_online} giorni</b>.\n"
        f"💰 Prezzo attuale: €{current_price:.0f}\n\n"
        f"Vuoi abbassare il prezzo? Usa /prezzo [id] [nuovo_prezzo]"
    )
    await notify_all_owners(text)
