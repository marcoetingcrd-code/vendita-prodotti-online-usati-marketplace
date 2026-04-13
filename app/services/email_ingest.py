"""
Email Hub — Ingestion Layer per il Sales Command Center.

Legge una casella IMAP dedicata, parserizza le notifiche delle piattaforme,
crea conversations/messages/events nel database.

Configurazione via .env:
    EMAIL_HUB_IMAP_HOST=imap.gmail.com
    EMAIL_HUB_IMAP_USER=marketplace@tuodominio.it
    EMAIL_HUB_IMAP_PASS=app-password
    EMAIL_HUB_POLL_SECONDS=60
"""

import asyncio
import email
import imaplib
import logging
import os
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

logger = logging.getLogger(__name__)

IMAP_HOST = os.getenv("EMAIL_HUB_IMAP_HOST", "")
IMAP_USER = os.getenv("EMAIL_HUB_IMAP_USER", "")
IMAP_PASS = os.getenv("EMAIL_HUB_IMAP_PASS", "")
POLL_SECONDS = int(os.getenv("EMAIL_HUB_POLL_SECONDS", "60"))

# Pattern per identificare la piattaforma dal mittente/subject
PLATFORM_PATTERNS = {
    "subito": [r"subito\.it", r"@subito\.it", r"Subito"],
    "ebay": [r"ebay\.(it|com)", r"@ebay\.", r"eBay"],
    "vinted": [r"vinted\.(it|com|fr)", r"@vinted\.", r"Vinted"],
    "facebook": [r"facebook\.com", r"marketplace", r"@facebookmail"],
}


def is_configured() -> bool:
    return bool(IMAP_HOST and IMAP_USER and IMAP_PASS)


def identify_platform(from_addr: str, subject: str) -> str:
    """Identifica la piattaforma dall'indirizzo mittente o dall'oggetto."""
    text = f"{from_addr} {subject}".lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return platform
    return "other"


def decode_mime_header(header_value: str) -> str:
    """Decodifica header MIME (es. subject con encoding)."""
    if not header_value:
        return ""
    parts = decode_header(header_value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def extract_body(msg: email.message.Message) -> str:
    """Estrae il body text da un messaggio email."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
            elif ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    # Strip HTML tags per ottenere testo leggibile
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    return text[:2000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def parse_email_message(raw_bytes: bytes) -> dict | None:
    """Parsa un'email grezza e restituisce un dizionario normalizzato."""
    try:
        msg = email.message_from_bytes(raw_bytes)

        from_header = msg.get("From", "")
        from_name, from_addr = parseaddr(from_header)
        from_name = decode_mime_header(from_name) or from_addr

        subject = decode_mime_header(msg.get("Subject", ""))
        message_id = msg.get("Message-ID", "")

        date_header = msg.get("Date")
        try:
            date = parsedate_to_datetime(date_header) if date_header else datetime.now(timezone.utc)
        except Exception:
            date = datetime.now(timezone.utc)

        body = extract_body(msg)
        platform = identify_platform(from_addr, subject)

        return {
            "from_name": from_name,
            "from_addr": from_addr,
            "subject": subject,
            "body": body[:5000],
            "message_id": message_id,
            "date": date,
            "platform": platform,
            "raw_from": from_header,
        }
    except Exception as e:
        logger.error(f"Errore parsing email: {e}")
        return None


async def fetch_new_emails() -> list[dict]:
    """Connette via IMAP, scarica le email non lette, le parsa."""
    if not is_configured():
        return []

    parsed = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            mail.logout()
            return []

        ids = data[0].split()
        logger.info(f"Email Hub: {len(ids)} email non lette trovate")

        for email_id in ids[-50:]:  # Max 50 per ciclo
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status == "OK" and msg_data[0]:
                raw = msg_data[0][1]
                result = parse_email_message(raw)
                if result:
                    parsed.append(result)

        mail.logout()
    except imaplib.IMAP4.error as e:
        logger.error(f"Email Hub IMAP error: {e}")
    except Exception as e:
        logger.error(f"Email Hub error: {e}")

    return parsed


async def process_emails(db_session):
    """Processa le nuove email: crea conversations, messages, events."""
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.event import Event
    from sqlalchemy import select

    emails = await fetch_new_emails()
    if not emails:
        return 0

    count = 0
    for em in emails:
        try:
            # Cerca conversazione esistente per contact_handle + platform
            result = await db_session.execute(
                select(Conversation).where(
                    Conversation.contact_handle == em["from_addr"],
                    Conversation.platform == em["platform"],
                )
            )
            conv = result.scalars().first()

            if not conv:
                conv = Conversation(
                    platform=em["platform"],
                    contact_name=em["from_name"],
                    contact_handle=em["from_addr"],
                    source="email",
                    status="open",
                )
                db_session.add(conv)
                await db_session.flush()

                db_session.add(Event(
                    event_type="conversation_created",
                    conversation_id=conv.id,
                    source="email_hub",
                    title=f"Nuova conversazione da {em['from_name']}",
                    description=f"Piattaforma: {em['platform']}",
                ))

            # Controlla duplicati per external_message_id
            if em["message_id"]:
                existing = await db_session.execute(
                    select(Message).where(Message.external_message_id == em["message_id"])
                )
                if existing.scalars().first():
                    continue

            msg = Message(
                conversation_id=conv.id,
                direction="incoming",
                source="email",
                sender_name=em["from_name"],
                sender_handle=em["from_addr"],
                subject=em["subject"],
                body=em["body"],
                external_message_id=em["message_id"],
                raw_payload={"from": em["raw_from"], "subject": em["subject"]},
            )
            db_session.add(msg)

            conv.last_message_at = datetime.now(timezone.utc)
            conv.unread_count += 1

            db_session.add(Event(
                event_type="message_received",
                conversation_id=conv.id,
                source="email_hub",
                title=f"Email da {em['from_name']} ({em['platform']})",
                description=em["subject"] or em["body"][:100],
            ))

            count += 1

        except Exception as e:
            logger.error(f"Errore processing email da {em.get('from_addr')}: {e}")
            db_session.add(Event(
                event_type="email_parse_error",
                source="email_hub",
                title=f"Errore parsing email",
                description=str(e)[:500],
            ))

    await db_session.commit()
    logger.info(f"Email Hub: {count} nuove email processate")
    return count


async def email_hub_loop():
    """Loop principale dell'Email Hub. Gira come background task."""
    if not is_configured():
        logger.info("Email Hub non configurato (variabili EMAIL_HUB_* mancanti). Disabilitato.")
        return

    logger.info(f"Email Hub avviato. Polling ogni {POLL_SECONDS}s verso {IMAP_HOST}")

    from app.database import async_session

    while True:
        try:
            async with async_session() as session:
                count = await process_emails(session)
                if count > 0:
                    logger.info(f"Email Hub: {count} messaggi ingeriti")
        except Exception as e:
            logger.error(f"Email Hub loop error: {e}")

        await asyncio.sleep(POLL_SECONDS)
