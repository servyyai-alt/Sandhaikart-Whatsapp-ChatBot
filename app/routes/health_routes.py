from fastapi import APIRouter

router = APIRouter(tags=["health"])


def _health_response() -> dict:
    return {"status": "ok", "service": "whatsapp-service"}


@router.get("/")
async def root() -> dict:
    return _health_response()


@router.get("/health")
async def health() -> dict:
    return _health_response()

