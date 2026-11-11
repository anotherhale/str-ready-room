"""API router aggregation.

All application endpoints are mounted under ``/api``.
"""
from __future__ import annotations

from fastapi import APIRouter

from . import operational, settings, system, tasks

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(tasks.router)
api_router.include_router(operational.router)
api_router.include_router(settings.router)

__all__ = ["api_router"]
