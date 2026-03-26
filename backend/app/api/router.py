from fastapi import APIRouter

from app.api.routes import analytics, exercises, health, summary, workouts

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(workouts.router, tags=["workouts"])
api_router.include_router(exercises.router, tags=["exercises"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(summary.router, tags=["summary"])
