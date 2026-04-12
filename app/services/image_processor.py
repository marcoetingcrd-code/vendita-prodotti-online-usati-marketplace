import io
import uuid
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps
from rembg import remove
from app.config import BASE_DIR, ORIGINALS_DIR, PROCESSED_DIR


PLATFORM_SIZES = {
    "subito": (1080, 1080),
    "ebay": (800, 800),
    "vinted": (1200, 1200),
    "default": (1200, 1200),
}

BG_COLOR = (245, 245, 245)  # Grigio chiaro, stile studio


def save_original(image_bytes: bytes, extension: str = ".jpg") -> str:
    """Salva l'immagine originale e restituisce il path."""
    filename = f"{uuid.uuid4().hex}{extension}"
    path = (ORIGINALS_DIR / filename).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    return str(path.relative_to(BASE_DIR.resolve()))


def process_image(original_path: str) -> str:
    """Pipeline completa: rimozione sfondo → crop → luci → resize.
    Restituisce il path dell'immagine processata."""

    p = Path(original_path)
    full_path = p if p.is_absolute() else (BASE_DIR / p).resolve()
    img_bytes = full_path.read_bytes()

    # 1. Rimozione sfondo con rembg
    result_bytes = remove(img_bytes)
    img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

    # 2. Crea sfondo neutro e componi
    bg = Image.new("RGBA", img.size, (*BG_COLOR, 255))
    composite = Image.alpha_composite(bg, img).convert("RGB")

    # 3. Auto-crop (rimuovi spazio vuoto attorno all'oggetto)
    composite = _auto_crop(composite, BG_COLOR)

    # 4. Padding uniforme (10% di margine)
    composite = _add_padding(composite, BG_COLOR, margin_pct=0.10)

    # 5. Correzione luci leggera
    enhancer = ImageEnhance.Brightness(composite)
    composite = enhancer.enhance(1.05)
    enhancer = ImageEnhance.Contrast(composite)
    composite = enhancer.enhance(1.08)

    # 6. Resize per piattaforma default
    size = PLATFORM_SIZES["default"]
    composite = ImageOps.fit(composite, size, method=Image.LANCZOS)

    # 7. Salva
    filename = f"{uuid.uuid4().hex}_clean.jpg"
    output_path = (PROCESSED_DIR / filename).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composite.save(str(output_path), "JPEG", quality=92)

    return str(output_path.relative_to(BASE_DIR.resolve()))


def resize_for_platform(processed_path: str, platform: str) -> str:
    """Resize un'immagine già processata per una piattaforma specifica."""
    size = PLATFORM_SIZES.get(platform, PLATFORM_SIZES["default"])
    p = Path(processed_path)
    full_path = p if p.is_absolute() else (BASE_DIR / p).resolve()
    img = Image.open(str(full_path))
    img = ImageOps.fit(img, size, method=Image.LANCZOS)

    filename = f"{uuid.uuid4().hex}_{platform}.jpg"
    output_path = (PROCESSED_DIR / filename).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=90)
    return str(output_path.relative_to(BASE_DIR.resolve()))


def _auto_crop(img: Image.Image, bg_color: tuple, threshold: int = 30) -> Image.Image:
    """Ritaglia automaticamente lo spazio vuoto attorno all'oggetto."""
    from PIL import ImageChops

    bg = Image.new(img.mode, img.size, bg_color)
    diff = ImageChops.difference(img, bg)
    diff = diff.convert("L")
    bbox = diff.getbbox()

    if bbox:
        return img.crop(bbox)
    return img


def _add_padding(img: Image.Image, bg_color: tuple, margin_pct: float = 0.10) -> Image.Image:
    """Aggiunge padding uniforme attorno all'immagine."""
    w, h = img.size
    pad_w = int(w * margin_pct)
    pad_h = int(h * margin_pct)

    new_w = w + 2 * pad_w
    new_h = h + 2 * pad_h

    padded = Image.new("RGB", (new_w, new_h), bg_color)
    padded.paste(img, (pad_w, pad_h))
    return padded
