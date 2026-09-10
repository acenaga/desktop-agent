"""
tests/unit/test_policy.py: Pruebas unitarias de PolicyEngine según Sección 14.1.
"""

import pytest
from pathlib import Path
from local_agent.domain.models import TaskScope
from local_agent.domain.states import ActionState
from local_agent.policy.engine import PolicyEngine, PolicyViolation


@pytest.fixture
def temp_workspace(tmp_path):
    read_dir = tmp_path / "read_dir"
    read_dir.mkdir()
    write_dir = tmp_path / "write_dir"
    write_dir.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()

    # Archivo de lectura
    doc = read_dir / "documento.txt"
    doc.write_text("Contenido autorizado")

    # Archivo fuera de scope
    secret = outside_dir / "secreto.txt"
    secret.write_text("Confidencial")

    # Archivo existente en write_dir
    existing = write_dir / "existente.txt"
    existing.write_text("Archivo previo")

    scope = TaskScope(
        name="test_scope",
        read_roots=[str(read_dir.resolve())],
        write_roots=[str(write_dir.resolve())],
        allowed_apps=["notepad"],
        allowed_domains=["localhost", "127.0.0.1"],
    )

    return {
        "read_dir": read_dir,
        "write_dir": write_dir,
        "outside_dir": outside_dir,
        "doc": doc,
        "secret": secret,
        "existing": existing,
        "scope": scope,
    }


def test_path_traversal_blocked(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]

    # Intento de path traversal usando ../ para salir de read_dir
    traversal_path = str(temp_workspace["read_dir"] / ".." / "outside_dir" / "secreto.txt")

    with pytest.raises(PolicyViolation) as exc_info:
        policy.canonicalize_path(traversal_path, scope.read_roots, allow_must_exist=True)
    assert exc_info.value.code == "OUT_OF_SCOPE"


def test_unc_path_blocked(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]

    with pytest.raises(PolicyViolation) as exc_info:
        policy.canonicalize_path(r"\\servidor\carpeta\archivo.txt", scope.read_roots)
    assert exc_info.value.code == "UNC_PATH_FORBIDDEN"


def test_forbidden_tools_blocked():
    policy = PolicyEngine()
    for forbidden in ["shell.execute", "bash.run", "python.eval", "system.delete_permanent"]:
        with pytest.raises(PolicyViolation) as exc_info:
            policy.validate_tool_allowed(forbidden)
        assert exc_info.value.code == "TOOL_FORBIDDEN"


def test_files_read_within_scope_allowed(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]

    state, args, reason = policy.evaluate_action(
        "files.read",
        {"path": str(temp_workspace["doc"])},
        scope,
    )
    assert state == ActionState.APPROVED
    assert args["path"] == str(temp_workspace["doc"].resolve())
    assert reason is None


def test_files_write_new_allowed(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]
    new_file = temp_workspace["write_dir"] / "nuevo.md"

    state, args, reason = policy.evaluate_action(
        "files.write",
        {"path": str(new_file), "content": "Nuevo informe"},
        scope,
    )
    assert state == ActionState.APPROVED
    assert args["path"] == str(new_file.resolve())
    assert reason is None


def test_files_write_overwrite_requires_approval(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]
    existing_file = temp_workspace["existing"]

    state, args, reason = policy.evaluate_action(
        "files.write",
        {"path": str(existing_file), "content": "Sobrescritura"},
        scope,
    )
    assert state == ActionState.PENDING_APPROVAL
    assert "Sobrescribirlo requiere tu aprobación" in reason


def test_files_move_requires_approval(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]

    state, args, reason = policy.evaluate_action(
        "files.move",
        {
            "source": str(temp_workspace["existing"]),
            "destination": str(temp_workspace["write_dir"] / "movido.txt"),
        },
        scope,
    )
    assert state == ActionState.PENDING_APPROVAL
    assert "altera la ubicación del archivo original" in reason


def test_unauthorized_app_blocked(temp_workspace):
    policy = PolicyEngine()
    scope = temp_workspace["scope"]

    with pytest.raises(PolicyViolation) as exc_info:
        policy.evaluate_action(
            "desktop.open_app",
            {"app_name": "cmd.exe"},
            scope,
        )
    assert exc_info.value.code == "APP_NOT_ALLOWED"
