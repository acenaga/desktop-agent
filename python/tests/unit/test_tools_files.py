"""
tests/unit/test_tools_files.py: Pruebas unitarias de las herramientas de archivos y verificación de postcondiciones.
"""

import pytest
from pathlib import Path
from local_agent.tools.files import (
    FilesListTool,
    FilesReadTool,
    FilesWriteTool,
    FilesCopyTool,
    FilesMoveTool,
    calculate_sha256,
)


@pytest.fixture
def file_env(tmp_path):
    d = tmp_path / "sandbox"
    d.mkdir()

    f1 = d / "prueba.txt"
    f1.write_text("Contenido inicial para lectura", encoding="utf-8")

    sub = d / "subcarpeta"
    sub.mkdir()
    f2 = sub / "otro.md"
    f2.write_text("# Título Markdown", encoding="utf-8")

    return {"dir": d, "f1": f1, "f2": f2, "sub": sub}


@pytest.mark.asyncio
async def test_files_list(file_env):
    tool = FilesListTool()
    res = await tool.execute({"directory": str(file_env["dir"]), "max_depth": 2})
    assert res.success is True
    entries = res.data["entries"]
    names = [e["name"] for e in entries]
    assert "prueba.txt" in names
    assert "subcarpeta" in names


@pytest.mark.asyncio
async def test_files_read_txt(file_env):
    tool = FilesReadTool()
    res = await tool.execute({"path": str(file_env["f1"])})
    assert res.success is True
    assert "Contenido inicial para lectura" in res.data["content"]
    assert res.data["sha256"] == calculate_sha256(file_env["f1"])


@pytest.mark.asyncio
async def test_files_write_atomic_and_verified(file_env):
    tool = FilesWriteTool()
    target = file_env["dir"] / "generado.txt"
    text = "Este texto fue generado de forma atómica y verificada."

    res = await tool.execute({"path": str(target), "content": text})
    assert res.success is True
    assert target.exists()
    assert target.read_text(encoding="utf-8") == text

    # Verificación de postcondición independiente
    verified = await tool.verify_postcondition({"path": str(target)}, res)
    assert verified is True


@pytest.mark.asyncio
async def test_files_copy_and_move(file_env):
    copy_tool = FilesCopyTool()
    dest_copy = file_env["dir"] / "copia.txt"
    res_copy = await copy_tool.execute({
        "source": str(file_env["f1"]),
        "destination": str(dest_copy),
    })
    assert res_copy.success is True
    assert dest_copy.exists()
    assert await copy_tool.verify_postcondition(
        {"source": str(file_env["f1"]), "destination": str(dest_copy)}, res_copy
    )

    move_tool = FilesMoveTool()
    dest_move = file_env["dir"] / "movido.txt"
    res_move = await move_tool.execute({
        "source": str(dest_copy),
        "destination": str(dest_move),
    })
    assert res_move.success is True
    assert not dest_copy.exists()
    assert dest_move.exists()
    assert await move_tool.verify_postcondition(
        {"source": str(dest_copy), "destination": str(dest_move)}, res_move
    )
