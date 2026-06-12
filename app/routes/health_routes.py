from fastapi import APIRouter, Response

router = APIRouter(tags=["health"])


def _health_response() -> dict:
    return {"status": "ok", "service": "whatsapp-service"}


@router.get("/")
async def root() -> dict:
    return _health_response()


@router.head("/")
async def root_head() -> Response:
    return Response(status_code=200)


@router.get("/health")
async def health() -> dict:
    return _health_response()


@router.head("/health")
async def health_head() -> Response:
    return Response(status_code=200)
