"""
tools/files.py: Adaptador de archivos y documentos para LocalDesk.
Implementa:
- files.list: enumeración con límites de profundidad y archivos.
- files.read: lectura y extracción estructurada (TXT, MD, PDF con pypdf, DOCX con python-docx).
- files.write: escritura atómica verificada con hash sha256 y tamaño.
- files.copy: copia verificada.
- files.move: movimiento verificado.
"""

import asyncio
import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from pypdf import PdfReader
import docx

from .base import BaseTool, ToolResult


def calculate_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class FilesListTool(BaseTool):
    name = "files.list"
    description = "Enumera archivos y subdirectorios de una carpeta autorizada, con límite de elementos."
    is_effect = False
    input_schema = {
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Ruta canónica del directorio a inspeccionar."},
            "max_depth": {"type": "integer", "description": "Profundidad máxima de búsqueda (defecto: 2).", "default": 2},
            "limit": {"type": "integer", "description": "Número máximo de archivos a listar (defecto: 100).", "default": 100},
        },
        "required": ["directory"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                        "is_dir": {"type": "boolean"},
                        "size_bytes": {"type": "integer"},
                    },
                },
            },
            "total_found": {"type": "integer"},
        },
    }

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        dir_path = Path(arguments["directory"])
        max_depth = int(arguments.get("max_depth", 2))
        limit = int(arguments.get("limit", 100))

        if not dir_path.is_dir():
            return ToolResult(success=False, error=f"'{dir_path}' no es un directorio válido.")

        entries = []
        count = 0

        def scan(current: Path, depth: int):
            nonlocal count
            if depth > max_depth or count >= limit:
                return
            try:
                for item in sorted(current.iterdir()):
                    if count >= limit:
                        break
                    try:
                        is_dir = item.is_dir()
                        size = item.stat().st_size if not is_dir else 0
                    except OSError:
                        continue

                    entries.append({
                        "path": str(item),
                        "name": item.name,
                        "is_dir": is_dir,
                        "size_bytes": size,
                    })
                    count += 1
                    if is_dir:
                        scan(item, depth + 1)
            except PermissionError:
                pass

        await asyncio.to_thread(scan, dir_path, 1)

        return ToolResult(
            success=True,
            data={"entries": entries, "total_found": len(entries)},
        )


class FilesReadTool(BaseTool):
    name = "files.read"
    description = "Lee y extrae contenido estructurado de archivos TXT, Markdown, PDF o DOCX con referencias a páginas/secciones."
    is_effect = False
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta canónica del archivo a leer."},
            "max_bytes": {"type": "integer", "description": "Límite de bytes a leer (defecto: 10MB).", "default": 10485760},
        },
        "required": ["path"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "format": {"type": "string"},
            "content": {"type": "string"},
            "sections": {"type": "array"},
            "size_bytes": {"type": "integer"},
            "sha256": {"type": "string"},
            "truncated": {"type": "boolean"},
        },
    }

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        file_path = Path(arguments["path"])
        max_bytes = int(arguments.get("max_bytes", 10 * 1024 * 1024))

        if not file_path.is_file():
            return ToolResult(success=False, error=f"El archivo '{file_path}' no existe o no es un archivo.")

        file_size = file_path.stat().st_size
        if file_size > max_bytes:
            return ToolResult(
                success=False,
                error=f"El archivo ({file_size} bytes) excede el tamaño máximo permitido ({max_bytes} bytes).",
            )

        suffix = file_path.suffix.lower()
        sha256 = calculate_sha256(file_path)

        try:
            # 1. Archivos de texto plano y Markdown
            if suffix in (".txt", ".md", ".json", ".yaml", ".yml", ".csv"):
                content = await asyncio.to_thread(file_path.read_text, encoding="utf-8", errors="replace")
                return ToolResult(
                    success=True,
                    data={
                        "path": str(file_path),
                        "format": suffix[1:],
                        "content": content,
                        "sections": [{"title": "Documento completo", "content": content}],
                        "size_bytes": file_size,
                        "sha256": sha256,
                        "truncated": False,
                    },
                )

            # 2. Documentos PDF con pypdf
            elif suffix == ".pdf":
                def extract_pdf():
                    reader = PdfReader(str(file_path))
                    if reader.is_encrypted:
                        try:
                            reader.decrypt("")
                        except Exception:
                            return None, "El PDF está cifrado o protegido con contraseña."
                    
                    sections = []
                    full_text = []
                    for idx, page in enumerate(reader.pages):
                        text = page.extract_text() or ""
                        sections.append({
                            "page": idx + 1,
                            "title": f"Página {idx + 1}",
                            "content": text.strip(),
                        })
                        full_text.append(f"--- [Página {idx + 1}] ---\n{text.strip()}")
                    
                    joined = "\n\n".join(full_text)
                    if not joined.strip():
                        return None, "El archivo PDF no contiene texto extraíble (posible documento escaneado/imagen sin OCR)."
                    return (joined, sections), None

                res, err = await asyncio.to_thread(extract_pdf)
                if err:
                    return ToolResult(success=False, error=err)
                joined, sections = res
                return ToolResult(
                    success=True,
                    data={
                        "path": str(file_path),
                        "format": "pdf",
                        "content": joined,
                        "sections": sections,
                        "size_bytes": file_size,
                        "sha256": sha256,
                        "truncated": False,
                    },
                )

            # 3. Documentos DOCX con python-docx
            elif suffix == ".docx":
                def extract_docx():
                    doc = docx.Document(str(file_path))
                    sections = []
                    paragraphs = []
                    current_section = {"title": "Inicio", "paragraphs": []}

                    for p in doc.paragraphs:
                        text = p.text.strip()
                        if not text:
                            continue
                        if p.style.name.startswith("Heading"):
                            if current_section["paragraphs"]:
                                sections.append({
                                    "title": current_section["title"],
                                    "content": "\n".join(current_section["paragraphs"]),
                                })
                            current_section = {"title": text, "paragraphs": []}
                        else:
                            current_section["paragraphs"].append(text)
                            paragraphs.append(text)

                    if current_section["paragraphs"]:
                        sections.append({
                            "title": current_section["title"],
                            "content": "\n".join(current_section["paragraphs"]),
                        })

                    joined = "\n\n".join(paragraphs)
                    return joined, sections

                joined, sections = await asyncio.to_thread(extract_docx)
                return ToolResult(
                    success=True,
                    data={
                        "path": str(file_path),
                        "format": "docx",
                        "content": joined,
                        "sections": sections,
                        "size_bytes": file_size,
                        "sha256": sha256,
                        "truncated": False,
                    },
                )

            else:
                return ToolResult(
                    success=False,
                    error=f"Formato de archivo '{suffix}' no soportado para extracción directa.",
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error al procesar el archivo '{file_path.name}': {str(e)}",
            )


class FilesWriteTool(BaseTool):
    name = "files.write"
    description = "Escribe o genera un archivo de forma atómica en una carpeta de salida autorizada."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta canónica completa de destino para el archivo."},
            "content": {"type": "string", "description": "Contenido de texto a escribir en el archivo."},
            "encoding": {"type": "string", "description": "Codificación del texto (defecto: utf-8).", "default": "utf-8"},
        },
        "required": ["path", "content"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "sha256": {"type": "string"},
            "written_at": {"type": "string"},
        },
    }

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        dest_path = Path(arguments["path"])
        content = arguments["content"]
        encoding = arguments.get("encoding", "utf-8")

        # Comprobar cancelación antes de escribir
        if cancellation_token and cancellation_token.is_set():
            return ToolResult(success=False, error="Cancelado antes de la escritura de archivos.")

        dest_dir = dest_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        def atomic_write():
            # Escribir en un archivo temporal en el mismo directorio y mover atómicamente
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(dest_dir),
                encoding=encoding,
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)

            shutil.move(str(tmp_path), str(dest_path))
            size = dest_path.stat().st_size
            sha256 = calculate_sha256(dest_path)
            return size, sha256

        try:
            size, sha256 = await asyncio.to_thread(atomic_write)
            return ToolResult(
                success=True,
                data={
                    "path": str(dest_path),
                    "size_bytes": size,
                    "sha256": sha256,
                },
                artifacts=[str(dest_path)],
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error durante escritura atómica: {str(e)}")

    async def verify_postcondition(
        self, arguments: Dict[str, Any], result: ToolResult
    ) -> bool:
        """Verifica independientemente que el archivo existe en disco y su hash coincide."""
        if not result.success:
            return False
        dest_path = Path(arguments["path"])
        if not dest_path.is_file():
            return False
        expected_sha = result.data.get("sha256")
        if not expected_sha:
            return False
        actual_sha = calculate_sha256(dest_path)
        return actual_sha == expected_sha


class FilesCopyTool(BaseTool):
    name = "files.copy"
    description = "Copia un archivo autorizado a otra ubicación autorizada."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
        "required": ["source", "destination"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
            "size_bytes": {"type": "integer"},
        },
    }

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        src = Path(arguments["source"])
        dst = Path(arguments["destination"])
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(shutil.copy2, str(src), str(dst))
            return ToolResult(
                success=True,
                data={"source": str(src), "destination": str(dst), "size_bytes": dst.stat().st_size},
                artifacts=[str(dst)],
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error al copiar archivo: {str(e)}")

    async def verify_postcondition(
        self, arguments: Dict[str, Any], result: ToolResult
    ) -> bool:
        dst = Path(arguments["destination"])
        src = Path(arguments["source"])
        return dst.is_file() and calculate_sha256(dst) == calculate_sha256(src)


class FilesMoveTool(BaseTool):
    name = "files.move"
    description = "Mueve un archivo autorizado a otra ubicación autorizada."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
        "required": ["source", "destination"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "source": {"type": "string"},
            "destination": {"type": "string"},
        },
    }

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        src = Path(arguments["source"])
        dst = Path(arguments["destination"])
        dst.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(shutil.move, str(src), str(dst))
            return ToolResult(
                success=True,
                data={"source": str(src), "destination": str(dst)},
                artifacts=[str(dst)],
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error al mover archivo: {str(e)}")

    async def verify_postcondition(
        self, arguments: Dict[str, Any], result: ToolResult
    ) -> bool:
        src = Path(arguments["source"])
        dst = Path(arguments["destination"])
        return not src.exists() and dst.exists()
