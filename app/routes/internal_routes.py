import re
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.whatsapp_client import (
    send_order_confirmation_message,
    send_tracking_update_message,
)
from app.utils.logger import get_logger

router = APIRouter(prefix="/internal", tags=["internal"])
logger = get_logger(__name__)


class OrderNotificationPayload(BaseModel):
    orderId: str
    orderNumber: Optional[str] = ""
    customerName: Optional[str] = ""
    customerPhone: str
    totalAmount: float = 0
    paymentStatus: Optional[str] = "Pending"
    trackingNumber: Optional[str] = ""
    courierName: Optional[str] = ""
    orderUrl: Optional[str] = ""


@router.post("/order-confirmation")
async def order_confirmation(
    payload: OrderNotificationPayload,
    authorization: Optional[str] = Header(default=None),
):
    _require_internal_auth(authorization)
    phone = _normalize_indian_phone(payload.customerPhone)
    order_number = _resolve_order_number(payload)

    if not phone:
        raise HTTPException(status_code=400, detail="Valid customerPhone is required")
    if not order_number:
        raise HTTPException(status_code=400, detail="orderId or orderNumber is required")

    try:
        response = await send_order_confirmation_message(
            to=phone,
            order_number=order_number,
            total_amount=payload.totalAmount,
            payment_status=payload.paymentStatus or "Pending",
            customer_name=payload.customerName or "Customer",
        )
        logger.info("WhatsApp order confirmation sent | order=%s | phone=%s", order_number, phone)
        return {"success": True, "response": response}
    except Exception as exc:
        logger.exception("WhatsApp order confirmation send failed | order=%s | phone=%s: %s", order_number, phone, exc)
        raise HTTPException(status_code=502, detail="WhatsApp order confirmation send failed")


@router.post("/tracking-update")
async def tracking_update(
    payload: OrderNotificationPayload,
    authorization: Optional[str] = Header(default=None),
):
    _require_internal_auth(authorization)
    phone = _normalize_indian_phone(payload.customerPhone)
    order_number = _resolve_order_number(payload)
    tracking_number = str(payload.trackingNumber or "").strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Valid customerPhone is required")
    if not order_number:
        raise HTTPException(status_code=400, detail="orderId or orderNumber is required")
    if not tracking_number:
        raise HTTPException(status_code=400, detail="trackingNumber is required")

    try:
        response = await send_tracking_update_message(
            to=phone,
            order_number=order_number,
            tracking_number=tracking_number,
            courier_name=str(payload.courierName or "").strip(),
            order_url=str(payload.orderUrl or "").strip(),
            customer_name=payload.customerName or "Customer",
        )
        logger.info("WhatsApp tracking update sent | order=%s | phone=%s | tracking=%s", order_number, phone, tracking_number)
        return {"success": True, "response": response}
    except Exception as exc:
        logger.exception("WhatsApp tracking update send failed | order=%s | phone=%s: %s", order_number, phone, exc)
        raise HTTPException(status_code=502, detail="WhatsApp tracking update send failed")


def _require_internal_auth(authorization: Optional[str]) -> None:
    expected_key = settings.dashboard_internal_api_key
    if not expected_key:
        logger.warning("DASHBOARD_INTERNAL_API_KEY is not configured")
        raise HTTPException(status_code=401, detail="Internal API key is not configured")

    expected = f"Bearer {expected_key}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _normalize_indian_phone(phone: str) -> str:
    digits = re.sub(r"\D+", "", str(phone or ""))
    if re.fullmatch(r"\d{10}", digits):
        return f"91{digits}"
    if re.fullmatch(r"91\d{10}", digits):
        return digits
    return ""


def _resolve_order_number(payload: OrderNotificationPayload) -> str:
    order_number = str(payload.orderNumber or "").strip()
    if order_number:
        return order_number

    order_id = str(payload.orderId or "").strip()
    return order_id[-8:].upper() if order_id else ""
