from fastapi import APIRouter
from sqlalchemy import text
from ..schemas import HealthOut
from ..db import SessionLocal, redis_client

router = APIRouter(tags=["misc"])


@router.get("/health", response_model=HealthOut)
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        pg = "ok"
    except Exception as e:
        pg = f"error: {e}"

    try:
        redis_client.ping()
        rd = "ok"
    except Exception as e:
        rd = f"error: {e}"

    return HealthOut(postgres=pg, redis=rd)
