"""API router aggregation.

All application endpoints are mounted under ``/api``.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import calendar, email, operational, settings, system, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(tasks.router)
api_router.include_router(operational.router)
api_router.include_router(settings.router)
api_router.include_router(calendar.router)
api_router.include_router(email.router)

__all__ = ["api_router"]
