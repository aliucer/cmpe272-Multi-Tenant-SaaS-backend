import time
from fastapi import HTTPException
from ..db import redis_client


def rate_limit(key: str, limit=300, window=60):
    bucket = f"rl:{key}:{int(time.time()//window)}"
    n = redis_client.incr(bucket)
    if n == 1:
        redis_client.expire(bucket, window)
    if n > limit:
        raise HTTPException(status_code=429, detail="Too many requests")
