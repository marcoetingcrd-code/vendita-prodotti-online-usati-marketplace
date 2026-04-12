"""Template di formattazione annunci per copia-incolla rapido."""


def format_subito(title: str, description: str, price: float | None, location: str | None) -> str:
    price_str = f"€{price:.0f}" if price else "[Prezzo da inserire]"
    loc_str = location or "[Zona da inserire]"
    return (
        f"📋 ANNUNCIO PER SUBITO.IT\n"
        f"{'='*40}\n\n"
        f"Titolo: {title}\n\n"
        f"Descrizione:\n{description}\n\n"
        f"Prezzo: {price_str} (Trattabile)\n"
        f"Ritiro: {loc_str}\n"
    )


def format_ebay(title: str, description: str, price: float | None) -> str:
    price_str = f"€{price:.0f}" if price else "[Prezzo da inserire]"
    return (
        f"📋 ANNUNCIO PER EBAY\n"
        f"{'='*40}\n\n"
        f"Titolo: {title}\n\n"
        f"Descrizione:\n{description}\n\n"
        f"Prezzo: {price_str}\n"
        f"Spedizione: [Da specificare]\n"
    )


def format_vinted(title: str, description: str, price: float | None) -> str:
    price_str = f"€{price:.0f}" if price else "[Prezzo da inserire]"
    return (
        f"📋 ANNUNCIO PER VINTED\n"
        f"{'='*40}\n\n"
        f"Titolo: {title}\n\n"
        f"Descrizione:\n{description}\n\n"
        f"Prezzo: {price_str}\n"
    )


def format_telegram_summary(product: dict) -> str:
    """Formatta un riepilogo prodotto per Telegram."""
    status_emoji = {
        "draft": "📝", "ready": "✅", "listed": "📢",
        "negotiating": "🤝", "sold": "💰", "archived": "📦",
    }
    emoji = status_emoji.get(product.get("status", ""), "❓")
    price = product.get("price_listed") or product.get("price_initial") or product.get("price_ai_suggested")
    price_str = f"€{price:.0f}" if price else "N/D"

    return (
        f"{emoji} <b>{product.get('title', 'Senza titolo')}</b>\n"
        f"   ID: <code>{product.get('id', '?')}</code>\n"
        f"   💰 {price_str} | 📊 {product.get('status', '?')}\n"
        f"   👤 {product.get('owner_name', '?')}\n"
    )
