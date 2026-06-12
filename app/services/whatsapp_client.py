from typing import Any, Dict

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def send_text_message(to: str, message: str) -> Dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    }
    return await _send_whatsapp_message(payload)


async def send_template_message(
    to: str,
    template_name: str,
    body_values: list[str],
    language_code: str | None = None,
) -> Dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code or settings.whatsapp_template_language,
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(value or "-")}
                        for value in body_values
                    ],
                }
            ],
        },
    }
    return await _send_whatsapp_message(payload)


async def send_checkout_cta_message(to: str, body_text: str, checkout_url: str) -> Dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "cta_url",
            "body": {
                "text": body_text,
            },
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": "Continue Checkout",
                    "url": checkout_url,
                },
            },
        },
    }
    return await _send_whatsapp_message(payload)


async def send_order_confirmation_message(
    to: str,
    order_number: str,
    total_amount: float,
    payment_status: str,
    customer_name: str = "Customer",
) -> Dict[str, Any]:
    amount = _format_inr_amount(total_amount)
    if settings.whatsapp_order_confirmed_template:
        return await send_template_message(
            to=to,
            template_name=settings.whatsapp_order_confirmed_template,
            body_values=[
                customer_name or "Customer",
                order_number,
                amount,
                payment_status,
            ],
        )

    logger.warning(
        "WHATSAPP_ORDER_CONFIRMED_TEMPLATE is not configured; falling back to text order confirmation"
    )
    message = (
        "Your order is confirmed ✅\n\n"
        f"Order ID: {order_number}\n"
        f"Amount: ₹{amount}\n"
        f"Payment status: {payment_status}\n\n"
        "We will notify you once your order is shipped."
    )
    return await send_text_message(to=to, message=message)


async def send_tracking_update_message(
    to: str,
    order_number: str,
    tracking_number: str,
    courier_name: str,
    order_url: str,
    customer_name: str = "Customer",
) -> Dict[str, Any]:
    if settings.whatsapp_order_shipped_template:
        return await send_template_message(
            to=to,
            template_name=settings.whatsapp_order_shipped_template,
            body_values=[
                customer_name or "Customer",
                order_number,
                courier_name,
                tracking_number,
                order_url,
            ],
        )

    logger.warning(
        "WHATSAPP_ORDER_SHIPPED_TEMPLATE is not configured; falling back to text tracking update"
    )
    message = (
        "Your order has been shipped 🚚\n\n"
        f"Order ID: {order_number}\n"
        f"Courier: {courier_name or 'Not available'}\n"
        f"AWB: {tracking_number}\n\n"
        "Track your order:\n"
        f"{order_url}"
    )
    return await send_text_message(to=to, message=message)


async def _send_whatsapp_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.whatsapp_temp_token:
        raise RuntimeError("WHATSAPP_TEMP_TOKEN is missing in environment variables")
    if not settings.whatsapp_phone_number_id:
        raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID is missing in environment variables")

    url = (
        f"https://graph.facebook.com/"
        f"{settings.graph_api_version}/{settings.whatsapp_phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.whatsapp_temp_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        logger.error(
            "WhatsApp API send failure | status=%s | body=%s",
            response.status_code,
            response.text,
        )
        raise RuntimeError(f"WhatsApp API request failed with status {response.status_code}")

    try:
        return response.json()
    except ValueError:
        return {"ok": True, "raw_response": response.text}


def _format_inr_amount(value: float) -> str:
    number = float(value or 0)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"
