"""
api/app.py: Fábrica y ciclo de vida de la aplicación FastAPI para LocalDesk.
"""

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from local_agent.core.engine import AgentCore
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    core: Optional[AgentCore] = getattr(app.state, "core", None)
    if core:
        await core.task_repo.db.migrate()
        recovered = await core.task_repo.db.recover_interrupted_tasks()
        if recovered > 0:
            print(f"[LocalDesk] Se recuperaron {recovered} tareas interrumpidas.")

    yield

    # Shutdown
    if core:
        # Cerrar adaptador de navegador si está activo
        browser_tool = core.tool_registry.get("browser.open")
        if browser_tool and hasattr(browser_tool, "adapter"):
            await browser_tool.adapter.close()
        await core.task_repo.db.close()


def create_app(core: Optional[AgentCore] = None) -> FastAPI:
    app = FastAPI(
        title="LocalDesk API",
        version="0.1.0",
        description="API local versionada para control de agente de escritorio con IA local.",
        lifespan=lifespan,
    )

    # Configuración restrictiva de CORS (Sección 10: cerrado, solo orígenes locales autorizados)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if core:
        app.state.core = core

    app.include_router(router)
    return app
