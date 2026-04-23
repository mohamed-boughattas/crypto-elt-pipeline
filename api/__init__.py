"""FastAPI application factory."""

from api.main import app
from api.routers.health import router as health_router
from api.routers.market import router as market_router

app.include_router(health_router)
app.include_router(market_router)

__all__ = ["app"]
