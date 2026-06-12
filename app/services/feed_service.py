import re
from typing import Any, Dict, Optional

from app.config import settings
from app.services.dashboard_client import get_all_products
from app.utils.csv_utils import rows_to_csv
from app.utils.logger import get_logger

logger = get_logger(__name__)

FEED_COLUMNS = [
    "id",
    "title",
    "description",
    "availability",
    "condition",
    "price",
    "link",
    "image_link",
    "brand",
]


async def generate_meta_product_feed_csv() -> str:
    if not settings.website_base_url:
        logger.warning("WEBSITE_BASE_URL is not configured; feed links may be invalid")

    products = await get_all_products()
    rows = []
    skipped = 0

    for product in products:
        row = _map_product_to_feed_row(product)
        if row:
            rows.append(row)
        else:
            skipped += 1

    logger.info(
        "Meta feed generation done | total=%s | exported=%s | skipped=%s",
        len(products),
        len(rows),
        skipped,
    )
    return rows_to_csv(FEED_COLUMNS, rows)


def _map_product_to_feed_row(product: Dict[str, Any]) -> Optional[Dict[str, str]]:
    product_id = _product_id(product)
    product_page_id = _product_page_id(product)
    title = _string_value(product.get("name") or product.get("title"))
    price_value = _extract_price(product)
    image_link = _extract_image_link(product)

    if not settings.website_base_url:
        return None

    if not product_id or not product_page_id or not title or price_value is None or not image_link:
        logger.warning(
            "Skipping product due to missing required feed fields | id=%s | page_id=%s | title=%s | price=%s | image=%s",
            product_id,
            product_page_id,
            title,
            price_value,
            image_link,
        )
        return None

    description = _string_value(product.get("description")) or title
    stock = _extract_stock(product)
    availability = "in stock" if stock > 0 else "out of stock"
    brand = _extract_brand(product) or settings.brand_name
    product_link = f"{settings.website_base_url}/products/{product_page_id}"
    currency = settings.default_currency or "INR"

    return {
        "id": product_id,
        "title": title,
        "description": description,
        "availability": availability,
        "condition": "new",
        "price": f"{price_value:.2f} {currency}",
        "link": product_link,
        "image_link": image_link,
        "brand": brand,
    }


def _product_id(product: Dict[str, Any]) -> str:
    for key in ("_id", "id", "sku"):
        value = product.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _product_page_id(product: Dict[str, Any]) -> str:
    for key in ("_id", "id", "sku"):
        value = product.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _extract_price(product: Dict[str, Any]) -> Optional[float]:
    for key in ("price", "sale_price", "salePrice", "selling_price", "sellingPrice", "mrp"):
        value = product.get(key)
        converted = _to_float(value)
        if converted is not None:
            return converted

    pricing = product.get("pricing")
    if isinstance(pricing, dict):
        for key in ("price", "sale_price", "salePrice"):
            converted = _to_float(pricing.get(key))
            if converted is not None:
                return converted

    return None


def _extract_stock(product: Dict[str, Any]) -> int:
    for key in ("stock", "quantity", "countInStock", "inventory"):
        value = product.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def _extract_brand(product: Dict[str, Any]) -> str:
    brand = product.get("brand")
    if isinstance(brand, dict):
        return _string_value(brand.get("name"))
    return _string_value(brand)


def _extract_image_link(product: Dict[str, Any]) -> str:
    images = product.get("images")
    if isinstance(images, list):
        for item in images:
            image = _image_from_item(item)
            if image:
                return image

    for key in ("image", "image_url", "imageUrl", "thumbnail"):
        image = _image_from_item(product.get(key))
        if image:
            return image

    return ""


def _image_from_item(item: Any) -> str:
    if isinstance(item, str):
        candidate = item.strip()
        if candidate:
            return candidate
    if isinstance(item, dict):
        for key in ("url", "src", "image", "image_url", "imageUrl", "link"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]+", "", value.replace(",", ""))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
