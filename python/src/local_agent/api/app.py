"""
api/app.py: Fábrica y ciclo de vida de la aplicación FastAPI para LocalDesk.
"""

from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from local_agent.core.engine import AgentCore
from local_agent.domain.models import TaskScope
from .routes import router

# Identificador fijo del alcance que usa la interfaz por defecto
# (GET /v1/scopes y TaskNewView lo esperan con este id exacto).
DEFAULT_SCOPE_ID = "default_scope"


def _origin_to_domain(origin: str) -> str:
    """
    config.permissions.allowed_origins admite URLs ("http://127.0.0.1:8765"),
    pero la política compara nombres de host, así que se extrae el hostname.
    """
    origin = origin.strip()
    if "://" in origin:
        return urlparse(origin).hostname or origin
    return origin


async def ensure_default_scope(core: AgentCore) -> TaskScope:
    """
    Garantiza que exista el alcance 'default_scope'. config.permissions solo
    se usa como valor inicial la primera vez: si el scope ya existe se devuelve
    intacto, porque sus carpetas se gestionan desde la interfaz
    (PUT /v1/scopes/{scope_id}/roots) y no deben sobrescribirse al reiniciar.
    """
    existing = await core.scope_repo.get_scope(DEFAULT_SCOPE_ID)
    if existing:
        return existing

    perms = core.config.permissions
    scope = TaskScope(
        scope_id=DEFAULT_SCOPE_ID,
        name=DEFAULT_SCOPE_ID,
        read_roots=list(perms.read_roots),
        write_roots=list(perms.write_roots),
        allowed_apps=list(perms.allowed_apps),
        allowed_domains=[_origin_to_domain(o) for o in perms.allowed_origins],
    )
    return await core.scope_repo.save_scope(scope)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    core: Optional[AgentCore] = getattr(app.state, "core", None)
    if core:
        await core.task_repo.db.migrate()
        await ensure_default_scope(core)
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
    # Starlette compara allow_origins literalmente (no admite comodines de puerto
    # como "http://localhost:*"), así que los orígenes loopback con cualquier
    # puerto (p. ej. Vite en :5173) se autorizan mediante una regex anclada.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_origin_regex=r"^http://(127\.0\.0\.1|localhost)(:\d{1,5})?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if core:
        app.state.core = core

    app.include_router(router)
    return app
