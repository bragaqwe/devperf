import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import init_db
from app.api.routes import router
from app.api.seed import seed_router

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DevPerf API starting — initializing DB…")
    await init_db()
    logger.info("DevPerf API ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.APP_NAME, version="0.3.0",
    description="Developer Performance Assessment System",
    lifespan=lifespan, docs_url="/docs", redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(router, prefix=settings.API_PREFIX)
app.include_router(seed_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME}
