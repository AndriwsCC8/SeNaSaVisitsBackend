"""Router agregador de la API. Los routers de dominio (usuarios, visitas, etc.)
se registrarán aquí en fases posteriores.
"""
from fastapi import APIRouter

from app.api.routes import audit, auth, dashboard, health, reports, users, visitors, visits

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(visitors.router)
api_router.include_router(visits.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
