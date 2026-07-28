"""REST routers. The contract they implement is frozen by planning/TEAM.md section 4."""

from app.api.health import router as health_router
from app.api.portfolio import router as portfolio_router
from app.api.watchlist import router as watchlist_router

__all__ = ["health_router", "portfolio_router", "watchlist_router"]
