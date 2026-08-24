from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.classification import router as classification_router
from app.api.collections import router as collections_router
from app.api.users import router as users_router
from app.api.waste_reports import router as waste_reports_router


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