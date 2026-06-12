import json
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.services.cart_link_service import build_whatsapp_cart_link
from app.services.whatsapp_client import send_checkout_cta_message, send_text_message
from app.utils.logger import get_logger

router = APIRouter(tags=["whatsapp"])
logger = get_logger(__name__)


@router.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
) -> PlainTextResponse:
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        logger.info("WhatsApp webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)

    logger.warning("WhatsApp webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        logger.warning("Webhook received invalid JSON payload")
        return Response(content='{"status":"ignored","reason":"invalid_json"}', media_type="application/json")

    logger.info("Incoming WhatsApp webhook payload snapshot: %s", _safe_json_snapshot(payload))

    handled_messages = 0
    for context in _iter_incoming_messages(payload):
        message = context["message"]
        customer_number = context["customer_number"]

        if not customer_number:
            continue

        items = _extract_catalog_items(message)
        if items:
            try:
                cart_link = build_whatsapp_cart_link(items)
            except ValueError as exc:
                logger.warning("Unable to build cart link from items %s: %s", items, exc)
                continue

            order_reply = _build_checkout_cta_body(items, message)
            await _safe_send_checkout_cta(customer_number, order_reply, cart_link)
            handled_messages += 1
            continue

        if message.get("type") == "text":
            text_body = ((message.get("text") or {}).get("body") or "").strip()
            lowered = text_body.lower()
            if lowered in {"hi", "hello", "hey", "start"}:
                greeting = (
                    f"Hi 👋 Welcome to {settings.brand_name}. "
                    "Please browse our WhatsApp catalog and send your cart."
                )
                await _safe_send_message(customer_number, greeting)
            else:
                normal_reply = (
                    "Please browse our WhatsApp catalog, select your items, and send your cart. "
                    "I will share a secure website checkout link."
                )
                await _safe_send_message(customer_number, normal_reply)
            handled_messages += 1
            continue

        logger.info("Ignoring non-text/non-order message type: %s", message.get("type"))

    return Response(
        content=json.dumps({"status": "processed", "handled_messages": handled_messages}),
        media_type="application/json",
    )


def _safe_json_snapshot(payload: Any, max_chars: int = 4000) -> str:
    try:
        compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        compact = str(payload)
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars]}...<truncated>"


def _iter_incoming_messages(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    if not isinstance(payload, dict):
        return contexts

    entries = payload.get("entry")
    if not isinstance(entries, list):
        return contexts

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes")
        if not isinstance(changes, list):
            continue
        for change in changes:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            messages = value.get("messages") or []
            contacts = value.get("contacts") or []
            if not isinstance(messages, list):
                continue
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                customer_number = str(msg.get("from") or "").strip()
                customer_name = _resolve_contact_name(contacts, customer_number)
                contexts.append(
                    {
                        "message": msg,
                        "customer_number": customer_number,
                        "customer_name": customer_name,
                    }
                )
    return contexts


def _resolve_contact_name(contacts: Any, customer_number: str) -> str:
    if not isinstance(contacts, list):
        return ""
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        wa_id = str(contact.get("wa_id") or "").strip()
        if wa_id != customer_number:
            continue
        profile = contact.get("profile") or {}
        if isinstance(profile, dict):
            return str(profile.get("name") or "").strip()
    return ""


def _extract_catalog_items(message: Dict[str, Any]) -> List[Dict[str, int]]:
    raw_items: List[Tuple[str, int]] = []
    msg_type = str(message.get("type") or "").strip().lower()

    if msg_type == "order":
        order_block = message.get("order") or {}
        product_items = order_block.get("product_items") or []
        if isinstance(product_items, list):
            for item in product_items:
                if not isinstance(item, dict):
                    continue
                product_id = _extract_any_product_id(item)
                quantity = _to_positive_int(item.get("quantity"), default=1)
                if product_id:
                    raw_items.append((product_id, quantity))

    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        if isinstance(interactive, dict):
            product_block = interactive.get("product") or {}
            if isinstance(product_block, dict):
                product_id = _extract_any_product_id(product_block)
                if product_id:
                    raw_items.append((product_id, 1))

            product_list = interactive.get("product_list") or {}
            if isinstance(product_list, dict):
                for section in product_list.get("sections") or []:
                    if not isinstance(section, dict):
                        continue
                    for product_item in section.get("product_items") or []:
                        if not isinstance(product_item, dict):
                            continue
                        product_id = _extract_any_product_id(product_item)
                        quantity = _to_positive_int(product_item.get("quantity"), default=1)
                        if product_id:
                            raw_items.append((product_id, quantity))

            action = interactive.get("action") or {}
            if isinstance(action, dict):
                action_product_id = _extract_any_product_id(action)
                if action_product_id:
                    raw_items.append((action_product_id, 1))
                parameters = action.get("parameters") or []
                if isinstance(parameters, list):
                    for param in parameters:
                        if not isinstance(param, dict):
                            continue
                        param_product_id = _extract_any_product_id(param)
                        quantity = _to_positive_int(param.get("quantity"), default=1)
                        if param_product_id:
                            raw_items.append((param_product_id, quantity))

    if not raw_items:
        return []

    aggregated: Dict[str, int] = {}
    for product_id, qty in raw_items:
        aggregated[product_id] = aggregated.get(product_id, 0) + qty
    return [{"product_id": pid, "quantity": qty} for pid, qty in aggregated.items()]


def _extract_any_product_id(payload: Dict[str, Any]) -> str:
    for key in ("product_retailer_id", "product_id", "retailer_id", "id", "_id", "sku"):
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _build_checkout_cta_body(items: List[Dict[str, int]], message: Dict[str, Any]) -> str:
    item_count = sum(_to_positive_int(item.get("quantity"), default=1) for item in items)
    estimated_total = _extract_estimated_total(message)

    lines = [
        "Your cart is ready ✅",
        "",
        f"Selected items: {item_count}",
    ]

    if estimated_total is not None:
        lines.append(f"Estimated total: ₹{_format_inr_amount(estimated_total)}")

    lines.extend(
        [
            "",
            "Tap the button below to continue checkout securely.",
        ]
    )
    return "\n".join(lines)


def _extract_estimated_total(message: Dict[str, Any]) -> float | None:
    if str(message.get("type") or "").strip().lower() != "order":
        return None

    order_block = message.get("order") or {}
    product_items = order_block.get("product_items") or []
    if not isinstance(product_items, list):
        return None

    total = 0.0
    found_price = False
    for item in product_items:
        if not isinstance(item, dict):
            continue

        price = _to_positive_float(
            item.get("item_price")
            or item.get("price")
            or item.get("sale_price")
            or item.get("salePrice")
            or item.get("amount")
        )
        if price is None:
            continue

        quantity = _to_positive_int(item.get("quantity"), default=1)
        total += price * quantity
        found_price = True

    return total if found_price else None


def _to_positive_float(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _format_inr_amount(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def _to_positive_int(value: Any, default: int = 1) -> int:
    try:
        number = int(value)
        return number if number > 0 else default
    except (TypeError, ValueError):
        return default


async def _safe_send_message(to: str, message: str) -> None:
    try:
        await send_text_message(to=to, message=message)
    except Exception as exc:
        logger.exception("Failed to send WhatsApp message to %s: %s", to, exc)


async def _safe_send_checkout_cta(to: str, message: str, checkout_url: str) -> None:
    try:
        await send_checkout_cta_message(to=to, body_text=message, checkout_url=checkout_url)
    except Exception as exc:
        logger.exception("Failed to send WhatsApp checkout CTA to %s: %s", to, exc)
