from fastapi import APIRouter

from app.api.routes import (
    analytics,
    exercises,
    health,
    measurements,
    profile,
    summary,
    workouts,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(workouts.router, tags=["workouts"])
api_router.include_router(exercises.router, tags=["exercises"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(measurements.router, tags=["measurements"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(summary.router, tags=["summary"])
