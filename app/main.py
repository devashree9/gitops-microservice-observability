import os
import time
import json
import logging
import sys

from fastapi import FastAPI, HTTPException
import redis
from prometheus_fastapi_instrumentator import Instrumentator

# ---------------------------------------------------------------------------
# Structured (JSON) logging — makes logs greppable/queryable instead of
# free-text, which is what you want once this ships anywhere real.
# ---------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": "gitops-microservice",
        }
        return json.dumps(payload)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("gitops-microservice")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

app = FastAPI(title="GitOps Microservice")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 30))

REDIS_URL = os.getenv("REDIS_URL")  # set by hosted platforms like Render
if REDIS_URL:
    r = redis.from_url(REDIS_URL, decode_responses=True)
else:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Expose Prometheus /metrics endpoint automatically
Instrumentator().instrument(app).expose(app)


@app.get("/")
def health_check():
    return {"status": "healthy", "service": "GitOps Microservice"}


# ---------------------------------------------------------------------------
# Raw key-value cache endpoints (manual control over Redis, kept for
# debugging/inspection).
# ---------------------------------------------------------------------------
@app.get("/cache/{key}")
def get_cache(key: str):
    try:
        val = r.get(key)
        if val is None:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"key": key, "value": val}
    except redis.ConnectionError:
        logger.error("Redis connection failed on GET /cache/%s" % key)
        raise HTTPException(status_code=500, detail="Redis connection failed")


@app.post("/cache/{key}/{value}")
def set_cache(key: str, value: str):
    try:
        r.set(key, value)
        return {"status": "success", "key": key, "value": value}
    except redis.ConnectionError:
        logger.error("Redis connection failed on POST /cache/%s" % key)
        raise HTTPException(status_code=500, detail="Redis connection failed")


# ---------------------------------------------------------------------------
# Cache-aside pattern: this is the actual point of having a cache.
# /compute/{n} simulates an expensive operation (e.g. a slow DB query or
# heavy calculation). First call is slow and MISSES the cache; every repeat
# call within CACHE_TTL_SECONDS HITS the cache and returns near-instantly.
# ---------------------------------------------------------------------------
def expensive_computation(n: int) -> int:
    """Pretend this is a slow DB aggregation / external API call."""
    time.sleep(1.5)
    return sum(i * i for i in range(n))


@app.get("/compute/{n}")
def compute(n: int):
    if n < 0 or n > 100_000:
        raise HTTPException(status_code=400, detail="n must be between 0 and 100000")

    cache_key = f"compute:{n}"
    start = time.perf_counter()

    try:
        cached = r.get(cache_key)
    except redis.ConnectionError:
        logger.error("Redis unavailable, falling back to direct computation")
        cached = None

    if cached is not None:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        logger.info(f"cache_hit key={cache_key} elapsed_ms={elapsed}")
        return {"n": n, "result": int(cached), "source": "cache", "elapsed_ms": elapsed}

    result = expensive_computation(n)

    try:
        r.setex(cache_key, CACHE_TTL_SECONDS, result)
    except redis.ConnectionError:
        logger.error("Redis unavailable, could not cache result")

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"cache_miss key={cache_key} elapsed_ms={elapsed}")
    return {"n": n, "result": result, "source": "computed", "elapsed_ms": elapsed}
