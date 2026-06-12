from fastapi import APIRouter, HTTPException, Response

from app.services.feed_service import generate_meta_product_feed_csv
from app.utils.logger import get_logger

router = APIRouter(tags=["meta-feed"])
logger = get_logger(__name__)


@router.get("/meta/product-feed.csv")
async def get_meta_product_feed() -> Response:
    try:
        csv_content = await generate_meta_product_feed_csv()
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="product-feed.csv"'},
        )
    except Exception as exc:
        logger.exception("Failed to generate Meta product feed CSV: %s", exc)
        raise HTTPException(status_code=500, detail="Unable to generate product feed")

