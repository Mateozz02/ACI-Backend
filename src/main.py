from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.database import init_db
from src.api import stores, products, orders, webhook, auth, test, whatsapp, conversations
from src.utils import setup_logging, logger

settings = get_settings()
setup_logging(settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OrderFlow API...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down OrderFlow API")


app = FastAPI(
    title="OrderFlow",
    description="AI-powered WhatsApp store manager",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stores.router, prefix="/api/stores", tags=["stores"])
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(webhook.router)
app.include_router(auth.router)
app.include_router(test.router)
app.include_router(whatsapp.router)
app.include_router(conversations.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "OrderFlow API"}
