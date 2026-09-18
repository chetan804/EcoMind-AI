import logging
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError
from jose import JWTError, jwt

from app.core.config import (
    APP_VERSION,
    CORS_ORIGINS,
    ENVIRONMENT,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    JWT_ALGORITHM,
    SECRET_KEY,
)
from app.db.database import engine
from app.db.database import SessionLocal
from app.models.user import User
from app.realtime import manager

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
rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)
rate_limit_lock = Lock()

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


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path not in {"/health", "/liveness", "/readiness"}:
        client_key = request.client.host if request.client else "unknown"
        now = monotonic()
        with rate_limit_lock:
            hits = rate_limit_hits[client_key]
            while hits and now - hits[0] >= RATE_LIMIT_WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests"},
                    headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
                )
            hits.append(now)
    return await call_next(request)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


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


@app.exception_handler(IntegrityError)
async def integrity_error_handler(
    request: Request,
    exc: IntegrityError,
) -> JSONResponse:
    logger.warning("Database integrity conflict on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "The requested resource conflicts with existing data"},
    )


@app.exception_handler(DataError)
async def data_error_handler(
    request: Request,
    exc: DataError,
) -> JSONResponse:
    logger.warning("Invalid database value on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "One or more values are invalid"},
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


@app.websocket("/ws/events")
async def event_socket(websocket: WebSocket, token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
        if user is None:
            await websocket.close(code=1008)
            return
        await manager.connect(user.id, websocket)
        await websocket.send_json({"event": "connected", "user_id": user.id})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    finally:
        db.close()


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


@app.get("/liveness", tags=["System"])
def liveness_check():
    return {"status": "alive", "version": APP_VERSION}


@app.get("/readiness", tags=["System"])
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "unavailable"},
        )

    return {"status": "ready", "database": "available", "version": APP_VERSION}