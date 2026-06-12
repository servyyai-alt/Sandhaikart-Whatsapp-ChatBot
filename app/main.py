from fastapi import FastAPI

from app.routes.health_routes import router as health_router
from app.routes.internal_routes import router as internal_router
from app.routes.meta_feed_routes import router as meta_feed_router
from app.routes.whatsapp_routes import router as whatsapp_router
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(title="whatsapp-service", version="1.0.0")

app.include_router(health_router)
app.include_router(internal_router)
app.include_router(whatsapp_router)
app.include_router(meta_feed_router)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("whatsapp-service started successfully")
