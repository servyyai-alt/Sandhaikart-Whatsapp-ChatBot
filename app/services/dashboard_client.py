from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

PRODUCT_PAGE_SIZE = 50
MAX_PRODUCT_FEED_PAGES = 1000


async def get_products(page: int = 1, limit: int = PRODUCT_PAGE_SIZE) -> List[Dict[str, Any]]:
    page_result = await _get_product_page(page=page, limit=limit)
    if not page_result:
        return []
    return page_result["products"]


async def _get_product_page(
    page: int = 1,
    limit: int = PRODUCT_PAGE_SIZE,
    require_pagination: bool = False,
) -> Optional[Dict[str, Any]]:
    if not settings.dashboard_api_base:
        logger.warning("DASHBOARD_API_BASE is not configured")
        return None

    endpoints = ["/api/products", "/products"]
    headers = _build_headers()
    params = {"page": page, "limit": limit}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            url = f"{settings.dashboard_api_base}{endpoint}"
            try:
                response = await client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("Dashboard request error at %s: %s", url, exc)
                continue

            if response.status_code >= 400:
                logger.warning(
                    "Dashboard endpoint returned %s for %s",
                    response.status_code,
                    url,
                )
                continue

            payload = _safe_json(response)
            products = _extract_products(payload)
            if products is not None:
                pagination = _extract_pagination_metadata(payload)
                if require_pagination and (
                    pagination["current_page"] is None or pagination["total_pages"] is None
                ):
                    logger.warning(
                        "Product response from %s is missing pagination metadata (page=%s, limit=%s)",
                        url,
                        page,
                        limit,
                    )
                    continue

                logger.info(
                    "Fetched %s product records from %s (page=%s, limit=%s)",
                    len(products),
                    endpoint,
                    page,
                    limit,
                )
                return {
                    "products": products,
                    "current_page": pagination["current_page"],
                    "total_pages": pagination["total_pages"],
                    "total_products": pagination["total_products"],
                }

            logger.warning("Unrecognized product response schema from %s", url)

    return None


async def get_all_products(limit: int = PRODUCT_PAGE_SIZE) -> List[Dict[str, Any]]:
    all_products: List[Dict[str, Any]] = []
    seen_ids = set()
    page_signatures = set()
    page = 1

    while page <= MAX_PRODUCT_FEED_PAGES:
        page_result = await _get_product_page(
            page=page,
            limit=limit,
            require_pagination=True,
        )
        if not page_result:
            logger.warning("Stopping product pagination because page %s returned no valid response", page)
            break

        page_products = page_result["products"]
        if not page_products:
            logger.info("Stopping product pagination because page %s returned no products", page)
            break

        current_page = page_result["current_page"]
        total_pages = page_result["total_pages"]
        total_products = page_result["total_products"]

        signature_parts = []
        for product in page_products[:20]:
            product_id = _extract_product_identity(product)
            if product_id:
                signature_parts.append(f"id:{product_id}")
            else:
                signature_parts.append(f"raw:{str(sorted(product.items()))[:120]}")
        signature = tuple(signature_parts)
        if signature in page_signatures:
            logger.warning("Detected repeated product page signature at page %s, stopping pagination", page)
            break
        page_signatures.add(signature)

        newly_added = 0
        for product in page_products:
            product_id = _extract_product_identity(product)
            if product_id:
                if product_id in seen_ids:
                    continue
                seen_ids.add(product_id)
            all_products.append(product)
            newly_added += 1

        if newly_added == 0:
            logger.warning("No new products added from page %s, stopping pagination", page)
            break

        logger.info(
            "Collected product page %s of %s | page_records=%s | total_products=%s | collected=%s",
            current_page,
            total_pages,
            len(page_products),
            total_products,
            len(all_products),
        )

        if current_page >= total_pages:
            break

        next_page = current_page + 1
        if next_page <= page:
            logger.warning(
                "Backend pagination did not advance from page %s to %s, stopping pagination",
                page,
                next_page,
            )
            break
        page = next_page
    else:
        logger.warning(
            "Reached safe max product feed page count of %s, stopping pagination",
            MAX_PRODUCT_FEED_PAGES,
        )

    logger.info("Collected total products: %s", len(all_products))
    return all_products


def _build_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if settings.dashboard_internal_api_key:
        headers["x-internal-api-key"] = settings.dashboard_internal_api_key
        headers["X-API-Key"] = settings.dashboard_internal_api_key
        headers["Authorization"] = f"Bearer {settings.dashboard_internal_api_key}"
    return headers


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        logger.warning("Dashboard response is not valid JSON")
        return None


def _extract_products(payload: Any) -> Optional[List[Dict[str, Any]]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if not isinstance(payload, dict):
        return None

    for key in ("products", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    data_block = payload.get("data")
    if isinstance(data_block, list):
        return [row for row in data_block if isinstance(row, dict)]

    if isinstance(data_block, dict):
        for key in ("products", "items", "results", "data"):
            nested = data_block.get(key)
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]

    # Recognize a product-like dict payload as a single item list.
    if any(key in payload for key in ("name", "price", "_id", "id", "sku")):
        return [payload]

    return None


def _extract_pagination_metadata(payload: Any) -> Dict[str, Optional[int]]:
    sources = []
    if isinstance(payload, dict):
        sources.append(payload)
        data_block = payload.get("data")
        if isinstance(data_block, dict):
            sources.append(data_block)

    return {
        "current_page": _extract_int_field(sources, ("currentPage", "page"), minimum=1),
        "total_pages": _extract_int_field(sources, ("totalPages", "pages"), minimum=0),
        "total_products": _extract_int_field(
            sources,
            ("totalProducts", "total", "count"),
            minimum=0,
        ),
    }


def _extract_int_field(
    sources: List[Dict[str, Any]],
    keys: tuple[str, ...],
    minimum: int,
) -> Optional[int]:
    for source in sources:
        for key in keys:
            if key not in source:
                continue
            value = _to_int(source.get(key))
            if value is not None and value >= minimum:
                return value
    return None


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_product_identity(product: Dict[str, Any]) -> str:
    for key in ("_id", "id", "sku"):
        value = product.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
