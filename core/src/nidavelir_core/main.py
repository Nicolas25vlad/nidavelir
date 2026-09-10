from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .execution.router import router as execution_router
from .execution.service import cleanup_orphaned_resources
from .logging import configure_logging
from .settings import get_settings
from .tasks.router import router as tasks_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    cleanup_orphaned_resources()
    yield


settings = get_settings()
app = FastAPI(
    title="Nidavelir Core",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks_router)
app.include_router(execution_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    current_settings = get_settings()
    return {
        "status": "ok",
        "service": "nidavelir-core",
        "environment": current_settings.env,
    }
