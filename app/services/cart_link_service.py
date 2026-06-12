from typing import Any, Dict, List
from urllib.parse import quote

from app.config import settings


def build_whatsapp_cart_link(items: List[Dict[str, Any]]) -> str:
    if not items:
        raise ValueError("At least one item is required to build cart link")
    if not settings.website_base_url:
        raise ValueError("WEBSITE_BASE_URL is not configured")

    formatted_items = []
    for item in items:
        product_id = str(item.get("product_id") or "").strip()
        if not product_id:
            continue
        quantity = _to_positive_int(item.get("quantity"), default=1)
        formatted_items.append(f"{product_id}:{quantity}")

    if not formatted_items:
        raise ValueError("No valid product items found for cart link")

    serialized = ",".join(formatted_items)
    encoded = quote(serialized, safe=":,")
    return f"{settings.website_base_url}/whatsapp-cart?items={encoded}"


def _to_positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default
