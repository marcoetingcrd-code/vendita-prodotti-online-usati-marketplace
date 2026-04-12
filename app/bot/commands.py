"""Telegram Bot command handlers — interfaccia primaria del Marketplace Hub."""

from telegram import Update, InputFile
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import async_session
from app.models.product import Product, ProductImage, PriceHistory
from app.models.owner import Owner
from app.services import gemini, image_processor
from app.services.notifications import send_telegram_message, send_telegram_photo
from app.templates.listings import format_subito, format_ebay, format_vinted, format_telegram_summary
from app.bot.keyboards import main_menu, product_actions, condition_keyboard, owner_selection, confirm_sold

# Temporary state for multi-step conversations
_user_state: dict[int, dict] = {}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏪 <b>Marketplace Hub</b>\n\n"
        "Benvenuto! Ecco cosa posso fare:\n\n"
        "/nuovo — Aggiungi un prodotto (invia foto!)\n"
        "/lista — Vedi tutti i prodotti\n"
        "/venduto [id] [prezzo] — Segna come venduto\n"
        "/prezzo [id] [nuovo_prezzo] — Aggiorna prezzo\n"
        "/stats — Statistiche vendite\n"
        "/help — Mostra questo messaggio\n",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_nuovo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Avvia il flow di creazione prodotto. Chiede di selezionare il proprietario."""
    chat_id = update.effective_chat.id

    async with async_session() as db:
        result = await db.execute(select(Owner))
        owners = result.scalars().all()

    if not owners:
        await update.message.reply_text(
            "⚠️ Nessun proprietario registrato.\n"
            "Registrati prima con: POST /api/owners\n"
            "oppure chiedi all'admin di aggiungerti.",
            parse_mode="HTML",
        )
        return

    owner_list = [{"id": o.id, "name": o.name} for o in owners]

    _user_state[chat_id] = {"step": "select_owner", "owners": owner_list}

    await update.message.reply_text(
        "📦 <b>Nuovo Prodotto</b>\n\nDi chi è questo prodotto?",
        parse_mode="HTML",
        reply_markup=owner_selection(owner_list),
    )


async def cmd_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra tutti i prodotti attivi."""
    async with async_session() as db:
        result = await db.execute(
            select(Product).where(Product.status.notin_(["sold", "archived"])).order_by(Product.created_at.desc())
        )
        products = result.scalars().all()

    if not products:
        await update.message.reply_text("📭 Nessun prodotto attivo.")
        return

    lines = ["📋 <b>Prodotti Attivi</b>\n"]
    for p in products:
        owner_name = p.owner.name if p.owner else "?"
        lines.append(format_telegram_summary({
            "id": p.id, "title": p.title, "status": p.status,
            "price_listed": p.price_listed, "price_initial": p.price_initial,
            "price_ai_suggested": p.price_ai_suggested, "owner_name": owner_name,
        }))

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_venduto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Segna un prodotto come venduto: /venduto [id] [prezzo]"""
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Uso: /venduto <id_prodotto> <prezzo>")
        return

    product_id = args[0]
    try:
        price = float(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Il prezzo deve essere un numero. Es: /venduto abc123 150")
        return

    async with async_session() as db:
        product = await db.get(Product, product_id)
        if not product:
            await update.message.reply_text(f"❌ Prodotto {product_id} non trovato.")
            return

        from datetime import datetime, timezone
        product.status = "sold"
        product.price_sold = price
        product.sold_at = datetime.now(timezone.utc)

        db.add(PriceHistory(product_id=product_id, price=price, reason="sale"))

        owner = await db.get(Owner, product.owner_id)
        await db.commit()

    await update.message.reply_text(
        f"🎉 <b>VENDUTO!</b>\n\n"
        f"<b>{product.title}</b>\n"
        f"💰 Prezzo: €{price:.0f}\n"
        f"👤 {owner.name if owner else '?'}",
        parse_mode="HTML",
    )


async def cmd_prezzo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Aggiorna il prezzo: /prezzo [id] [nuovo_prezzo]"""
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text("Uso: /prezzo <id_prodotto> <nuovo_prezzo>")
        return

    product_id = args[0]
    try:
        new_price = float(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Il prezzo deve essere un numero.")
        return

    async with async_session() as db:
        product = await db.get(Product, product_id)
        if not product:
            await update.message.reply_text(f"❌ Prodotto {product_id} non trovato.")
            return

        old_price = product.price_listed or product.price_initial or 0
        product.price_listed = new_price
        db.add(PriceHistory(product_id=product_id, price=new_price, reason="manual_update"))
        await db.commit()

    await update.message.reply_text(
        f"💰 Prezzo aggiornato!\n\n"
        f"<b>{product.title}</b>\n"
        f"€{old_price:.0f} → €{new_price:.0f}",
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra statistiche vendite."""
    async with async_session() as db:
        result = await db.execute(select(Product))
        products = result.scalars().all()

    total = len(products)
    sold = [p for p in products if p.status == "sold"]
    listed = [p for p in products if p.status in ("listed", "ready")]
    revenue = sum(p.price_sold for p in sold if p.price_sold)

    await update.message.reply_text(
        f"📊 <b>Statistiche</b>\n\n"
        f"📦 Totale prodotti: {total}\n"
        f"🟢 In vendita: {len(listed)}\n"
        f"💰 Venduti: {len(sold)}\n"
        f"💵 Ricavo totale: €{revenue:.0f}\n",
        parse_mode="HTML",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce foto inviate — crea prodotto se nel flow /nuovo, altrimenti chiede."""
    chat_id = update.effective_chat.id
    state = _user_state.get(chat_id, {})

    if state.get("step") != "waiting_photo":
        await update.message.reply_text(
            "📸 Foto ricevuta! Vuoi creare un nuovo prodotto?\nUsa /nuovo per iniziare il processo.",
        )
        return

    await update.message.reply_text("⏳ Analizzo la foto con AI...")

    photo = update.message.photo[-1]  # Highest resolution
    file = await context.bot.get_file(photo.file_id)
    photo_bytes = await file.download_as_bytearray()

    original_path = image_processor.save_original(bytes(photo_bytes), ".jpg")
    processed_path = image_processor.process_image(original_path)

    try:
        analysis = await gemini.analyze_product_image(original_path)
    except Exception as e:
        analysis = {"object": "Oggetto non identificato", "confidence": 0}
        await update.message.reply_text(f"⚠️ Errore AI: {e}\nContinuo con dati manuali.")

    owner_id = state.get("owner_id")

    async with async_session() as db:
        product = Product(
            owner_id=owner_id,
            title=analysis.get("object"),
            category=analysis.get("category"),
            condition=analysis.get("condition"),
            condition_score=analysis.get("condition_score"),
            defects=analysis.get("defects"),
            dimensions=analysis.get("dimensions_estimate"),
            price_ai_suggested=analysis.get("suggested_price_eur"),
            ai_detected_object=analysis.get("object"),
            ai_confidence=analysis.get("confidence"),
            status="draft",
        )
        db.add(product)
        await db.flush()

        img = ProductImage(
            product_id=product.id,
            original_path=original_path,
            processed_path=processed_path,
            is_primary=True,
        )
        db.add(img)
        await db.commit()
        await db.refresh(product)

        product_id = product.id

    price_str = f"€{analysis.get('suggested_price_eur', 0):.0f}" if analysis.get("suggested_price_eur") else "N/D"

    await update.message.reply_text(
        f"✅ <b>Prodotto creato!</b>\n\n"
        f"🆔 ID: <code>{product_id}</code>\n"
        f"📦 {analysis.get('object', '?')}\n"
        f"📂 {analysis.get('category', '?')}\n"
        f"📊 Condizione: {analysis.get('condition', '?')}\n"
        f"💰 Prezzo suggerito: {price_str}\n"
        f"🎯 Confidenza AI: {analysis.get('confidence', 0):.0%}\n",
        parse_mode="HTML",
        reply_markup=product_actions(product_id),
    )

    # Send processed image
    try:
        with open(processed_path, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption="📸 Foto processata (sfondo rimosso)",
            )
    except Exception:
        pass

    _user_state.pop(chat_id, None)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i bottoni inline."""
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = update.effective_chat.id

    if data == "menu":
        await query.edit_message_text(
            "🏪 <b>Marketplace Hub</b>\nScegli un'azione:",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    if data == "new_product":
        async with async_session() as db:
            result = await db.execute(select(Owner))
            owners = result.scalars().all()
        if not owners:
            await query.edit_message_text("⚠️ Nessun proprietario registrato.")
            return
        owner_list = [{"id": o.id, "name": o.name} for o in owners]
        _user_state[chat_id] = {"step": "select_owner", "owners": owner_list}
        await query.edit_message_text(
            "📦 <b>Nuovo Prodotto</b>\n\nDi chi è?",
            parse_mode="HTML",
            reply_markup=owner_selection(owner_list),
        )
        return

    if data == "list_products":
        async with async_session() as db:
            result = await db.execute(
                select(Product).where(Product.status.notin_(["sold", "archived"])).order_by(Product.created_at.desc())
            )
            products = result.scalars().all()
        if not products:
            await query.edit_message_text("📭 Nessun prodotto attivo.")
            return
        lines = ["📋 <b>Prodotti Attivi</b>\n"]
        for p in products:
            owner_name = p.owner.name if p.owner else "?"
            lines.append(format_telegram_summary({
                "id": p.id, "title": p.title, "status": p.status,
                "price_listed": p.price_listed, "price_initial": p.price_initial,
                "price_ai_suggested": p.price_ai_suggested, "owner_name": owner_name,
            }))
        await query.edit_message_text("\n".join(lines), parse_mode="HTML")
        return

    if data == "stats":
        async with async_session() as db:
            result = await db.execute(select(Product))
            products = result.scalars().all()
        sold = [p for p in products if p.status == "sold"]
        revenue = sum(p.price_sold for p in sold if p.price_sold)
        listed = [p for p in products if p.status in ("listed", "ready")]
        await query.edit_message_text(
            f"📊 <b>Statistiche</b>\n\n"
            f"📦 Totale: {len(products)}\n🟢 In vendita: {len(listed)}\n"
            f"💰 Venduti: {len(sold)}\n💵 Ricavo: €{revenue:.0f}",
            parse_mode="HTML",
        )
        return

    if data.startswith("owner_"):
        owner_id = data.replace("owner_", "")
        _user_state[chat_id] = {"step": "waiting_photo", "owner_id": owner_id}
        await query.edit_message_text(
            "📸 Ora inviami la foto del prodotto!\n\n"
            "Scatta una foto chiara dell'oggetto e inviala qui.",
            parse_mode="HTML",
        )
        return

    if data.startswith("analyze_"):
        product_id = data.replace("analyze_", "")
        await query.edit_message_text("⏳ Analizzo con AI...")
        async with async_session() as db:
            product = await db.get(Product, product_id)
            if product and product.images:
                img_path = product.images[0].original_path
                try:
                    analysis = await gemini.analyze_product_image(img_path)
                    await query.edit_message_text(
                        f"🔍 <b>Analisi AI</b>\n\n"
                        f"📦 {analysis.get('object', '?')}\n"
                        f"📂 {analysis.get('category', '?')}\n"
                        f"📊 {analysis.get('condition', '?')}\n"
                        f"💰 Prezzo suggerito: €{analysis.get('suggested_price_eur', 0):.0f}\n"
                        f"🎯 Confidenza: {analysis.get('confidence', 0):.0%}",
                        parse_mode="HTML",
                        reply_markup=product_actions(product_id),
                    )
                except Exception as e:
                    await query.edit_message_text(f"❌ Errore: {e}")
        return

    if data.startswith("describe_"):
        product_id = data.replace("describe_", "")
        await query.edit_message_text("⏳ Genero descrizioni...")
        async with async_session() as db:
            product = await db.get(Product, product_id)
            if product:
                try:
                    descs = await gemini.generate_listing_descriptions(
                        object_name=product.title or product.ai_detected_object or "Oggetto",
                        category=product.category or "Altro",
                        condition=product.condition or "usato",
                        defects=product.defects,
                        dimensions=product.dimensions,
                        materials=None, features=None,
                        price=product.price_listed or product.price_initial or product.price_ai_suggested,
                        location=product.pickup_location,
                    )
                    product.desc_subito = descs.get("subito", {}).get("description")
                    product.desc_ebay = descs.get("ebay", {}).get("description")
                    product.desc_vinted = descs.get("vinted", {}).get("description")
                    if product.status == "draft":
                        product.status = "ready"
                    await db.commit()

                    await query.edit_message_text(
                        f"✅ <b>Descrizioni generate!</b>\n\n"
                        f"Usa i bottoni per copiare l'annuncio per ogni piattaforma.",
                        parse_mode="HTML",
                        reply_markup=product_actions(product_id),
                    )
                except Exception as e:
                    await query.edit_message_text(f"❌ Errore: {e}")
        return

    for platform in ("subito", "ebay", "vinted"):
        if data == f"copy_{platform}_{data.split('_', 2)[-1] if data.count('_') >= 2 else ''}":
            break
    else:
        platform = None

    if data.startswith("copy_subito_") or data.startswith("copy_ebay_") or data.startswith("copy_vinted_"):
        parts = data.split("_", 2)
        platform = parts[1]
        product_id = parts[2]

        async with async_session() as db:
            product = await db.get(Product, product_id)
            if not product:
                await query.edit_message_text("❌ Prodotto non trovato")
                return

            desc_map = {"subito": product.desc_subito, "ebay": product.desc_ebay, "vinted": product.desc_vinted}
            desc = desc_map.get(platform)
            price = product.price_listed or product.price_initial or product.price_ai_suggested

            if not desc:
                await query.edit_message_text(
                    "⚠️ Descrizione non ancora generata. Premi prima '📝 Genera Annunci'.",
                    reply_markup=product_actions(product_id),
                )
                return

            formatter = {"subito": format_subito, "ebay": format_ebay, "vinted": format_vinted}
            text = formatter[platform](product.title or "Prodotto", desc, price, product.pickup_location)
            await query.edit_message_text(text, reply_markup=product_actions(product_id))
        return

    if data.startswith("sold_"):
        product_id = data.replace("sold_", "")
        _user_state[chat_id] = {"step": "waiting_sold_price", "product_id": product_id}
        await query.edit_message_text(
            "💰 A quanto l'hai venduto? Scrivi il prezzo (es: 150)",
            parse_mode="HTML",
        )
        return


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce messaggi di testo liberi (usati nel flow conversazionale)."""
    chat_id = update.effective_chat.id
    state = _user_state.get(chat_id, {})
    text = update.message.text.strip()

    if state.get("step") == "waiting_sold_price":
        product_id = state.get("product_id")
        try:
            price = float(text.replace("€", "").replace(",", ".").strip())
        except ValueError:
            await update.message.reply_text("⚠️ Scrivi solo il numero. Es: 150")
            return

        from datetime import datetime, timezone
        async with async_session() as db:
            product = await db.get(Product, product_id)
            if not product:
                await update.message.reply_text("❌ Prodotto non trovato")
                _user_state.pop(chat_id, None)
                return

            product.status = "sold"
            product.price_sold = price
            product.sold_at = datetime.now(timezone.utc)
            db.add(PriceHistory(product_id=product_id, price=price, reason="sale"))

            owner = await db.get(Owner, product.owner_id)
            await db.commit()

        await update.message.reply_text(
            f"🎉 <b>VENDUTO!</b>\n\n"
            f"<b>{product.title}</b>\n"
            f"💰 €{price:.0f}\n"
            f"👤 {owner.name if owner else '?'}",
            parse_mode="HTML",
        )
        _user_state.pop(chat_id, None)
        return

    await update.message.reply_text("Usa /help per vedere i comandi disponibili.")
