from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Nuovo Prodotto", callback_data="new_product")],
        [InlineKeyboardButton("📋 Lista Prodotti", callback_data="list_products")],
        [InlineKeyboardButton("📊 Statistiche", callback_data="stats")],
    ])


def product_actions(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Analizza AI", callback_data=f"analyze_{product_id}"),
            InlineKeyboardButton("📝 Genera Annunci", callback_data=f"describe_{product_id}"),
        ],
        [
            InlineKeyboardButton("📋 Copia Subito", callback_data=f"copy_subito_{product_id}"),
            InlineKeyboardButton("📋 Copia eBay", callback_data=f"copy_ebay_{product_id}"),
        ],
        [
            InlineKeyboardButton("📋 Copia Vinted", callback_data=f"copy_vinted_{product_id}"),
            InlineKeyboardButton("💰 Segna Venduto", callback_data=f"sold_{product_id}"),
        ],
        [InlineKeyboardButton("🔙 Menu", callback_data="menu")],
    ])


def confirm_sold(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Conferma", callback_data=f"confirm_sold_{product_id}"),
            InlineKeyboardButton("❌ Annulla", callback_data=f"cancel_sold_{product_id}"),
        ],
    ])


def condition_keyboard(product_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🆕 Nuovo", callback_data=f"cond_{product_id}_nuovo"),
            InlineKeyboardButton("✨ Come Nuovo", callback_data=f"cond_{product_id}_come_nuovo"),
        ],
        [
            InlineKeyboardButton("👍 Buono", callback_data=f"cond_{product_id}_buono"),
            InlineKeyboardButton("👌 Usato", callback_data=f"cond_{product_id}_usato"),
        ],
        [InlineKeyboardButton("⚠️ Difettoso", callback_data=f"cond_{product_id}_difettoso")],
    ])


def owner_selection(owners: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for owner in owners:
        buttons.append([InlineKeyboardButton(
            f"👤 {owner['name']}",
            callback_data=f"owner_{owner['id']}",
        )])
    return InlineKeyboardMarkup(buttons)
