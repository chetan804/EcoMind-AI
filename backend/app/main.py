import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import APP_VERSION, CORS_ORIGINS, ENVIRONMENT
from app.db.database import engine

from app.api.auth import router as auth_router
from app.api.classification import router as classification_router
from app.api.collections import router as collections_router
from app.api.users import router as users_router
from app.api.waste_reports import router as waste_reports_router
from app.api.routes import router as routes_router
from app.api.complaints import router as complaints_router
from app.api.notifications import router as notifications_router
from app.api.analytics import router as analytics_router
from app.api.carbon import router as carbon_router
from app.api.rewards import router as rewards_router
from app.api.environmental import router as environmental_router
from app.api.assistant import router as assistant_router
from app.api.municipalities import router as municipalities_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ecomind")

app = FastAPI(
    title="EcoMind AI",
    description="AI-powered smart waste management platform",
    version=APP_VERSION,
    docs_url="/docs" if ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def log_startup() -> None:
    logger.info("EcoMind AI starting in %s mode", ENVIRONMENT)


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception("Unhandled request failure: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred"},
    )


app.include_router(users_router)
app.include_router(auth_router)
app.include_router(waste_reports_router)
app.include_router(classification_router)
app.include_router(collections_router)
app.include_router(routes_router)
app.include_router(complaints_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(carbon_router)
app.include_router(rewards_router)
app.include_router(environmental_router)
app.include_router(assistant_router)
app.include_router(municipalities_router)


@app.get("/")
def root():
    return {
        "message": "EcoMind AI backend is running"
    }


@app.get("/health", tags=["System"])
def health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "database": "unavailable"},
        )

    return {
        "status": "healthy",
        "database": "available",
        "version": APP_VERSION,
    }