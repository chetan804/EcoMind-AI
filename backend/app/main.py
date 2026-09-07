from fastapi import FastAPI

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


app = FastAPI(
    title="EcoMind AI",
    description="AI-powered smart waste management platform",
    version="1.0.0",
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


@app.get("/")
def root():
    return {
        "message": "EcoMind AI backend is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }