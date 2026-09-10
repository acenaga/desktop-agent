"""
cli.py: Interfaz de línea de comandos para LocalDesk.
Permite:
- Ejecutar el servicio FastAPI en modo headless (para Tauri o uso independiente).
- Ejecutar una tarea directamente desde la consola.
- Diagnosticar el entorno.
"""

import argparse
import asyncio
import sys
from pathlib import Path
import uvicorn

from local_agent.config import AppConfig
from local_agent.domain.models import Task, TaskScope, new_id
from local_agent.domain.states import TaskState
from local_agent.policy.engine import PolicyEngine
from local_agent.providers.base import ModelProvider
from local_agent.providers.fake import FakeModelProvider
from local_agent.providers.ollama import OllamaProvider
from local_agent.tools.base import ToolRegistry
from local_agent.tools.files import FilesListTool, FilesReadTool, FilesWriteTool, FilesCopyTool, FilesMoveTool
from local_agent.tools.desktop import (
    get_default_desktop_adapter,
    DesktopOpenAppTool,
    DesktopObserveTool,
    DesktopTypeTextTool,
    DesktopKeyTool,
)
from local_agent.tools.browser import (
    BrowserAdapter,
    BrowserOpenTool,
    BrowserObserveTool,
    BrowserFillTool,
    BrowserClickTool,
)
from local_agent.storage.database import Database
from local_agent.storage.repository import (
    TaskRepository,
    EventRepository,
    ActionRepository,
    ApprovalRepository,
    ArtifactRepository,
    ScopeRepository,
)
from local_agent.core.queue import TaskQueueManager
from local_agent.core.engine import AgentCore
from local_agent.api.app import create_app
from local_agent.api.auth import set_session_token, generate_session_token


def build_agent_core(
    config: AppConfig,
    db_path: str = "local_agent.db",
    force_fake_provider: bool = False,
) -> AgentCore:
    db = Database(db_path)
    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    action_repo = ActionRepository(db)
    approval_repo = ApprovalRepository(db)
    artifact_repo = ArtifactRepository(db)
    scope_repo = ScopeRepository(db)

    queue_manager = TaskQueueManager(task_repo, event_repo)
    policy_engine = PolicyEngine()

    # Inferencia
    if force_fake_provider or config.inference.provider == "fake":
        provider: ModelProvider = FakeModelProvider()
    else:
        provider = OllamaProvider(
            base_url=config.inference.base_url,
            request_timeout_seconds=config.inference.request_timeout_seconds,
            require_local_execution=config.inference.require_local_execution,
        )

    # Registro de herramientas
    tool_registry = ToolRegistry()
    # Archivos
    tool_registry.register(FilesListTool())
    tool_registry.register(FilesReadTool())
    tool_registry.register(FilesWriteTool())
    tool_registry.register(FilesCopyTool())
    tool_registry.register(FilesMoveTool())

    # Escritorio
    desktop_adapter = get_default_desktop_adapter()
    tool_registry.register(DesktopOpenAppTool(desktop_adapter))
    tool_registry.register(DesktopObserveTool(desktop_adapter))
    tool_registry.register(DesktopTypeTextTool(desktop_adapter))
    tool_registry.register(DesktopKeyTool(desktop_adapter))

    # Navegador
    browser_adapter = BrowserAdapter(headless=True)
    tool_registry.register(BrowserOpenTool(browser_adapter))
    tool_registry.register(BrowserObserveTool(browser_adapter))
    tool_registry.register(BrowserFillTool(browser_adapter))
    tool_registry.register(BrowserClickTool(browser_adapter))

    return AgentCore(
        config=config,
        model_provider=provider,
        tool_registry=tool_registry,
        policy_engine=policy_engine,
        task_repo=task_repo,
        event_repo=event_repo,
        action_repo=action_repo,
        approval_repo=approval_repo,
        artifact_repo=artifact_repo,
        scope_repo=scope_repo,
        queue_manager=queue_manager,
    )


def cmd_serve(args):
    config = AppConfig.load_from_yaml(args.config) if args.config else AppConfig()
    core = build_agent_core(config, db_path=args.db, force_fake_provider=args.fake)

    token = args.token or generate_session_token()
    set_session_token(token)

    # Imprimir puerto y secreto según contrato de arranque con host de Tauri (Sección 4.2)
    print(f"[LocalDesk] Servicio listo. Bind: {args.host}:{args.port}")
    if args.print_token:
        print(f"[LocalDesk] Token de sesión: {token}")

    app = create_app(core)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


async def run_task_cli(args):
    config = AppConfig.load_from_yaml(args.config) if args.config else AppConfig()
    core = build_agent_core(config, db_path=args.db, force_fake_provider=args.fake)

    await core.task_repo.db.migrate()

    # Crear o recuperar scope
    read_root = str(Path(args.scope_read).resolve()) if args.scope_read else str(Path.cwd().resolve())
    write_root = str(Path(args.scope_write).resolve()) if args.scope_write else str(Path.cwd().resolve())

    scope = TaskScope(
        scope_id=new_id("scope_cli"),
        name="cli_scope",
        read_roots=[read_root],
        write_roots=[write_root],
        allowed_apps=["notepad", "calc"],
        allowed_domains=["127.0.0.1", "localhost"],
    )
    await core.scope_repo.save_scope(scope)

    task = Task(
        instruction=args.instruction,
        scope_id=scope.scope_id,
        input_refs=args.input_refs or [],
        output_name=args.output_name,
    )
    await core.task_repo.create_task(task)

    print(f"[LocalDesk CLI] Iniciando tarea: '{task.instruction}'")
    try:
        completed_task = await core.execute_task(task.task_id)

        print(f"\n[LocalDesk CLI] Estado final: {completed_task.state.value}")
        if completed_task.error_message:
            print(f"Error: {completed_task.error_message}")

        artifacts = await core.artifact_repo.get_artifacts_for_task(task.task_id)
        if artifacts:
            print(f"Artefactos generados ({len(artifacts)}):")
            for a in artifacts:
                print(f"  - {a.file_name} ({a.size_bytes} bytes, SHA256: {a.sha256[:12]}...)")
    finally:
        await core.task_repo.db.close()


def main():
    parser = argparse.ArgumentParser(description="LocalDesk - Agente de escritorio con IA local")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # Subcomando serve
    serve_parser = subparsers.add_parser("serve", help="Inicia el servicio FastAPI en loopback")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Dirección loopback (por defecto: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Puerto (0 para asignación automática del SO)")
    serve_parser.add_argument("--config", default=None, help="Ruta al archivo config.yaml")
    serve_parser.add_argument("--db", default="local_agent.db", help="Ruta a la base de datos SQLite")
    serve_parser.add_argument("--token", default=None, help="Token secreto de sesión loopback")
    serve_parser.add_argument("--print-token", action="store_true", help="Mostrar token en consola para desarrollo")
    serve_parser.add_argument("--fake", action="store_true", help="Usar FakeModelProvider en lugar de Ollama")

    # Subcomando run
    run_parser = subparsers.add_parser("run", help="Ejecuta una tarea de forma directa por CLI")
    run_parser.add_argument("--instruction", required=True, help="Instrucción en lenguaje natural")
    run_parser.add_argument("--scope-read", default=".", help="Directorio raíz autorizado para lectura")
    run_parser.add_argument("--scope-write", default=".", help="Directorio raíz autorizado para escritura")
    run_parser.add_argument("--input-refs", nargs="*", default=[], help="Archivos de entrada")
    run_parser.add_argument("--output-name", default=None, help="Nombre del archivo de salida esperado")
    run_parser.add_argument("--config", default=None, help="Ruta al config.yaml")
    run_parser.add_argument("--db", default="local_agent.db", help="Ruta a SQLite")
    run_parser.add_argument("--fake", action="store_true", help="Usar FakeModelProvider")

    args = parser.parse_args()
    if args.subcommand == "serve":
        cmd_serve(args)
    elif args.subcommand == "run":
        asyncio.run(run_task_cli(args))


if __name__ == "__main__":
    main()
