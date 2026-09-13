"""
tests/integration/test_default_scope.py: Alcance 'default_scope' y edición de sus carpetas.
- La interfaz (TaskNewView) crea tareas con scope_id='default_scope'; si no existía,
  POST /v1/tasks respondía 400 "El scope_id 'default_scope' no existe."
- config.permissions solo siembra el scope la primera vez; después las carpetas se
  gestionan desde Configuración mediante PUT /v1/scopes/{scope_id}/roots.
"""

import httpx
import pytest

from local_agent.api.app import DEFAULT_SCOPE_ID, create_app, ensure_default_scope
from local_agent.api.auth import set_session_token
from local_agent.config import AppConfig, PermissionsConfig
from local_agent.core.engine import AgentCore
from local_agent.core.queue import TaskQueueManager
from local_agent.policy.engine import PolicyEngine
from local_agent.providers.fake import FakeModelProvider
from local_agent.storage.database import Database
from local_agent.storage.repository import (
    ActionRepository,
    ApprovalRepository,
    ArtifactRepository,
    EventRepository,
    ScopeRepository,
    TaskRepository,
)
from local_agent.tools.base import ToolRegistry

TOKEN = "token-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ROOTS_URL = f"/v1/scopes/{DEFAULT_SCOPE_ID}/roots"


def build_core(db: Database, permissions: PermissionsConfig) -> AgentCore:
    task_repo = TaskRepository(db)
    event_repo = EventRepository(db)
    return AgentCore(
        config=AppConfig(permissions=permissions),
        model_provider=FakeModelProvider(),
        tool_registry=ToolRegistry(),
        policy_engine=PolicyEngine(),
        task_repo=task_repo,
        event_repo=event_repo,
        action_repo=ActionRepository(db),
        approval_repo=ApprovalRepository(db),
        artifact_repo=ArtifactRepository(db),
        scope_repo=ScopeRepository(db),
        queue_manager=TaskQueueManager(task_repo, event_repo),
    )


def api_client(core: AgentCore) -> httpx.AsyncClient:
    set_session_token(TOKEN)
    transport = httpx.ASGITransport(app=create_app(core))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "default_scope.db")
    await database.migrate()
    yield database
    await database.close()


@pytest.fixture
def dirs(tmp_path):
    lectura = tmp_path / "lectura"
    escritura = tmp_path / "escritura"
    lectura.mkdir()
    escritura.mkdir()
    return lectura, escritura


# --- Siembra inicial desde la configuración ---


async def test_default_scope_created_from_config(db, tmp_path):
    perms = PermissionsConfig(
        read_roots=[str(tmp_path)],
        write_roots=[str(tmp_path)],
        allowed_apps=["notepad"],
        allowed_origins=["http://127.0.0.1:8765", "localhost"],
    )
    core = build_core(db, perms)

    scope = await ensure_default_scope(core)

    stored = await core.scope_repo.get_scope(DEFAULT_SCOPE_ID)
    assert stored is not None
    assert stored.version == 1
    assert stored.read_roots == [str(tmp_path)]
    assert stored.allowed_apps == ["notepad"]
    # Los orígenes con esquema se reducen al hostname que compara la política
    assert stored.allowed_domains == ["127.0.0.1", "localhost"]
    assert scope.scope_id == DEFAULT_SCOPE_ID


async def test_default_scope_is_idempotent(db):
    core = build_core(db, PermissionsConfig(allowed_apps=["notepad"]))

    first = await ensure_default_scope(core)
    second = await ensure_default_scope(core)

    assert second.version == first.version == 1
    assert second.created_at == first.created_at


async def test_default_scope_not_overwritten_by_config(db, tmp_path):
    # La interfaz manda: un cambio posterior en el YAML no pisa el scope existente
    config_a = PermissionsConfig(read_roots=[str(tmp_path / "a")], allowed_apps=["notepad"])
    config_b = PermissionsConfig(read_roots=[str(tmp_path / "b")], allowed_apps=["calc"])

    first = await ensure_default_scope(build_core(db, config_a))
    again = await ensure_default_scope(build_core(db, config_b))

    assert again.version == 1
    assert again.read_roots == first.read_roots == [str(tmp_path / "a")]
    assert again.allowed_apps == ["notepad"]


async def test_api_lists_default_scope_for_frontend(db):
    core = build_core(db, PermissionsConfig())
    await ensure_default_scope(core)

    async with api_client(core) as client:
        res = await client.get("/v1/scopes", headers=AUTH)

    assert res.status_code == 200
    assert [s["scope_id"] for s in res.json()] == [DEFAULT_SCOPE_ID]


# --- PUT /v1/scopes/{scope_id}/roots ---


async def test_update_roots_saves_canonical_paths_and_bumps_version(db, dirs):
    lectura, escritura = dirs
    core = build_core(
        db,
        PermissionsConfig(allowed_apps=["notepad"], allowed_origins=["http://127.0.0.1:8765"]),
    )
    original = await ensure_default_scope(core)

    async with api_client(core) as client:
        res = await client.put(
            ROOTS_URL,
            json={"read_roots": [f"  {lectura}  "], "write_roots": [str(escritura)]},
            headers=AUTH,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["read_roots"] == [str(lectura.resolve())]
    assert body["write_roots"] == [str(escritura.resolve())]
    assert body["version"] == original.version + 1

    stored = await core.scope_repo.get_scope(DEFAULT_SCOPE_ID)
    assert stored.read_roots == [str(lectura.resolve())]
    assert stored.version == original.version + 1
    # Lo que no se edita desde la interfaz queda intacto
    assert stored.allowed_apps == ["notepad"]
    assert stored.allowed_domains == ["127.0.0.1"]
    assert stored.created_at == original.created_at


async def test_update_roots_collapses_duplicates(db, dirs):
    lectura, _ = dirs
    core = build_core(db, PermissionsConfig())
    await ensure_default_scope(core)

    duplicated = [str(lectura), str(lectura) + "\\", str(lectura)]
    async with api_client(core) as client:
        res = await client.put(
            ROOTS_URL,
            json={"read_roots": duplicated, "write_roots": []},
            headers=AUTH,
        )

    assert res.status_code == 200, res.text
    assert res.json()["read_roots"] == [str(lectura.resolve())]


@pytest.mark.parametrize(
    "bad_root, expected_fragment",
    [
        ("NO_EXISTE", "no existe"),
        ("carpeta_relativa", "ruta absoluta"),
        (r"\\servidor\recurso", "UNC"),
        ("", "vacía"),
    ],
    ids=["inexistente", "relativa", "unc", "vacia"],
)
async def test_update_roots_rejects_invalid_paths(db, dirs, tmp_path, bad_root, expected_fragment):
    lectura, _ = dirs
    if bad_root == "NO_EXISTE":
        bad_root = str(tmp_path / "no_existe")
    core = build_core(db, PermissionsConfig(read_roots=[str(lectura)]))
    original = await ensure_default_scope(core)

    async with api_client(core) as client:
        res = await client.put(
            ROOTS_URL,
            json={"read_roots": [str(lectura)], "write_roots": [bad_root]},
            headers=AUTH,
        )

    assert res.status_code == 400
    assert expected_fragment in res.json()["detail"]
    # Nada se guarda si alguna ruta es inválida
    stored = await core.scope_repo.get_scope(DEFAULT_SCOPE_ID)
    assert stored.version == original.version
    assert stored.write_roots == original.write_roots


async def test_update_roots_rejects_file_instead_of_folder(db, tmp_path):
    archivo = tmp_path / "archivo.txt"
    archivo.write_text("x", encoding="utf-8")
    core = build_core(db, PermissionsConfig())
    await ensure_default_scope(core)

    async with api_client(core) as client:
        res = await client.put(
            ROOTS_URL,
            json={"read_roots": [str(archivo)], "write_roots": []},
            headers=AUTH,
        )

    assert res.status_code == 400
    assert "no es una carpeta" in res.json()["detail"]


async def test_update_roots_unknown_scope_returns_404(db, dirs):
    lectura, _ = dirs
    core = build_core(db, PermissionsConfig())

    async with api_client(core) as client:
        res = await client.put(
            "/v1/scopes/scope_inexistente/roots",
            json={"read_roots": [str(lectura)], "write_roots": []},
            headers=AUTH,
        )

    assert res.status_code == 404


async def test_update_roots_requires_token(db, dirs):
    lectura, _ = dirs
    core = build_core(db, PermissionsConfig())
    await ensure_default_scope(core)

    async with api_client(core) as client:
        res = await client.put(
            ROOTS_URL,
            json={"read_roots": [str(lectura)], "write_roots": []},
        )

    assert res.status_code == 401
    stored = await core.scope_repo.get_scope(DEFAULT_SCOPE_ID)
    assert stored.version == 1
