import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    whatsapp_temp_token: str
    whatsapp_phone_number_id: str
    whatsapp_business_account_id: str
    whatsapp_verify_token: str
    graph_api_version: str
    dashboard_api_base: str
    website_base_url: str
    dashboard_internal_api_key: str
    brand_name: str
    default_currency: str
    whatsapp_template_language: str
    whatsapp_order_confirmed_template: str
    whatsapp_order_shipped_template: str
    whatsapp_return_update_template: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        whatsapp_temp_token=os.getenv("WHATSAPP_TEMP_TOKEN", "").strip(),
        whatsapp_phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
        whatsapp_business_account_id=os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip(),
        whatsapp_verify_token=os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip(),
        graph_api_version=os.getenv("GRAPH_API_VERSION", "v19.0").strip(),
        dashboard_api_base=os.getenv("DASHBOARD_API_BASE", "").strip().rstrip("/"),
        website_base_url=os.getenv("WEBSITE_BASE_URL", "").strip().rstrip("/"),
        dashboard_internal_api_key=os.getenv("DASHBOARD_INTERNAL_API_KEY", "").strip(),
        brand_name=os.getenv("BRAND_NAME", "Sandhaikart").strip(),
        default_currency=os.getenv("DEFAULT_CURRENCY", "INR").strip().upper(),
        whatsapp_template_language=os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "en").strip() or "en",
        whatsapp_order_confirmed_template=os.getenv("WHATSAPP_ORDER_CONFIRMED_TEMPLATE", "").strip(),
        whatsapp_order_shipped_template=os.getenv("WHATSAPP_ORDER_SHIPPED_TEMPLATE", "").strip(),
        whatsapp_return_update_template=os.getenv("WHATSAPP_RETURN_UPDATE_TEMPLATE", "").strip(),
    )


settings = get_settings()
