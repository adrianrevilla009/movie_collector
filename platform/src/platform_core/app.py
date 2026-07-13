from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from platform_core.config import get_settings
from platform_core.errors import register_exception_handlers
from platform_core.routers import account, auth, catalog, health, interactions, moderation
from platform_core.security.rate_limit import limiter

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title="Cine Platform API", version="0.1.0")

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_allowed_origin],  # se restringe mas en Fase 6
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(interactions.router)
    app.include_router(moderation.router)
    app.include_router(account.router)
    app.include_router(account.notif_router)

    return app


app = create_app()
