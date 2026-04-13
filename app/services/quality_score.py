def compute_quality(product) -> dict:
    """Calcola quality score per un prodotto. Ritorna score (0-100) e livello."""
    checks = {
        "has_title": bool(product.title and len(product.title) > 3),
        "has_images": bool(product.images and len(product.images) > 0),
        "has_description": bool(product.desc_subito or product.desc_ebay or product.desc_vinted),
        "has_measurements": bool(product.dimensions or product.measurements),
        "has_platform": bool(product.publications and len(product.publications) > 0),
    }

    score = sum(20 for v in checks.values() if v)
    level = "red" if score <= 40 else ("yellow" if score <= 70 else "green")

    return {
        "score": score,
        "level": level,
        "checks": checks,
    }
