"""
policy/engine.py: PolicyEngine para validación estricta de permisos, canonicalización de rutas
y clasificación de riesgos de acciones en LocalDesk.
"""

from pathlib import Path
from typing import Any, Tuple, Optional
import os
import re

from local_agent.domain.models import TaskScope, Action, Approval, new_id, now_utc_iso
from local_agent.domain.states import ActionState


class PolicyViolation(Exception):
    def __init__(self, message: str, code: str = "POLICY_VIOLATION"):
        super().__init__(message)
        self.code = code
        self.message = message


class PolicyEngine:
    """
    Motor de políticas de seguridad.
    Aplica principio de cero confianza sobre el LLM:
    - Verificación canónica de rutas (evita traversal ../, junctions, symlinks fuera de raíz).
    - Rechazo de rutas UNC o de red.
    - Clasificación de riesgo:
      * ALLOWED: Ejecución directa sin interrumpir al usuario (lectura o escritura nueva en carpeta autorizada).
      * NEEDS_APPROVAL: Sobrescritura de archivo existente, mover archivo, acciones con riesgo moderado.
      * BLOCKED: Acceso fuera de scope, rutas de sistema, borrado destructivo, shell arbitrario.
    """

    FORBIDDEN_TOOLS = {
        "shell.execute",
        "bash.run",
        "python.eval",
        "system.delete_permanent",
        "system.elevate",
    }

    def __init__(self):
        pass

    def validate_tool_allowed(self, tool_name: str) -> None:
        if tool_name in self.FORBIDDEN_TOOLS:
            raise PolicyViolation(
                f"La herramienta '{tool_name}' está prohibida por la política de seguridad.",
                code="TOOL_FORBIDDEN",
            )

    def validate_authorized_root(self, raw: str) -> str:
        """
        Valida una carpeta que se va a autorizar como raíz de lectura o escritura.
        Debe ser una ruta absoluta local (no UNC) a un directorio existente.
        Devuelve la ruta canónica, la misma forma con la que canonicalize_path
        compara la contención.
        """
        if not raw or not raw.strip():
            raise PolicyViolation("Ruta de carpeta vacía no permitida.", code="INVALID_PATH")

        norm = raw.strip()
        if norm.startswith(r"\\") or norm.startswith("//"):
            raise PolicyViolation(
                f"Rutas UNC y de red no están permitidas: '{norm}'.", code="UNC_PATH_FORBIDDEN"
            )

        path = Path(norm)
        if not path.is_absolute():
            raise PolicyViolation(
                f"La carpeta debe ser una ruta absoluta: '{norm}'.", code="INVALID_PATH"
            )

        resolved = path.resolve()
        if not resolved.exists():
            raise PolicyViolation(f"La carpeta no existe: '{norm}'.", code="ROOT_NOT_FOUND")
        if not resolved.is_dir():
            raise PolicyViolation(f"La ruta no es una carpeta: '{norm}'.", code="ROOT_NOT_FOUND")

        return str(resolved)

    def canonicalize_path(
        self,
        raw_path: str,
        base_roots: list[str],
        allow_must_exist: bool = False,
    ) -> Path:
        """
        Resuelve y valida una ruta frente a una lista de carpetas base autorizadas.
        - Rechaza rutas UNC (\\\\servidor\\recurso).
        - Resuelve symlinks y enlaces canónicos.
        - Comprueba que la ruta resultante resida estrictamente dentro de alguna base_root autorizada.
        """
        if not raw_path or not raw_path.strip():
            raise PolicyViolation("Ruta vacía no permitida.", code="INVALID_PATH")

        norm_path_str = raw_path.strip()

        # Rechazo de rutas UNC de Windows (ej: \\server\share o //server/share)
        if norm_path_str.startswith(r"\\") or norm_path_str.startswith("//"):
            raise PolicyViolation("Rutas UNC y de red no están permitidas.", code="UNC_PATH_FORBIDDEN")

        try:
            target_path = Path(norm_path_str)
        except Exception as e:
            raise PolicyViolation(f"Ruta con formato no válido: {e}", code="INVALID_PATH")

        # Si no es absoluta y tenemos bases autorizadas, intentamos resolverla relativa a la primera base
        if not target_path.is_absolute():
            if not base_roots:
                raise PolicyViolation(
                    "No hay carpetas raíz autorizadas para resolver rutas relativas.",
                    code="OUT_OF_SCOPE",
                )
            target_path = Path(base_roots[0]) / target_path

        # Resolver enlaces simbólicos y ruta canónica
        # Para archivos que aún no existen (creación), resolvemos su directorio padre existente
        if target_path.exists():
            resolved = target_path.resolve()
        else:
            # Subir hasta encontrar el ancestro existente y resolverlo
            parent = target_path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if parent.exists():
                resolved_parent = parent.resolve()
                rel_to_parent = target_path.relative_to(parent)
                resolved = resolved_parent / rel_to_parent
            else:
                resolved = target_path.resolve()

        if allow_must_exist and not resolved.exists():
            raise PolicyViolation(f"El archivo especificado no existe: {resolved}", code="FILE_NOT_FOUND")

        # Verificar contención estricta en al menos una de las raíces autorizadas
        contained = False
        for root in base_roots:
            resolved_root = Path(root).resolve()
            try:
                resolved.relative_to(resolved_root)
                contained = True
                break
            except ValueError:
                continue

        if not contained:
            raise PolicyViolation(
                f"Acceso fuera del alcance autorizado: '{resolved}' no está dentro de ningún directorio autorizado.",
                code="OUT_OF_SCOPE",
            )

        return resolved

    def evaluate_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        scope: TaskScope,
    ) -> Tuple[ActionState, dict[str, Any], Optional[str]]:
        """
        Evalúa una acción frente al TaskScope y clasifica su estado:
        Retorna (ActionState.APPROVED, canonical_arguments, None)
        o (ActionState.PENDING_APPROVAL, canonical_arguments, reason_for_approval)
        o lanza PolicyViolation si debe ser bloqueada inmediatamente.
        """
        self.validate_tool_allowed(tool_name)
        canonical_args = dict(arguments)

        # 1. Herramientas de archivos
        if tool_name == "files.list":
            raw_dir = arguments.get("directory", "")
            can_dir = self.canonicalize_path(raw_dir, scope.read_roots or scope.write_roots, allow_must_exist=True)
            if not can_dir.is_dir():
                raise PolicyViolation(f"'{can_dir}' no es un directorio.", code="NOT_A_DIRECTORY")
            canonical_args["directory"] = str(can_dir)
            return ActionState.APPROVED, canonical_args, None

        elif tool_name == "files.read":
            raw_path = arguments.get("path", "")
            can_path = self.canonicalize_path(raw_path, scope.read_roots, allow_must_exist=True)
            canonical_args["path"] = str(can_path)
            return ActionState.APPROVED, canonical_args, None

        elif tool_name == "files.write":
            raw_path = arguments.get("path", "")
            # Permitir que el archivo sea nuevo dentro de write_roots
            can_path = self.canonicalize_path(raw_path, scope.write_roots, allow_must_exist=False)
            canonical_args["path"] = str(can_path)

            # Si el archivo ya existe y se va a sobrescribir, requiere aprobación explícita
            if can_path.exists():
                reason = f"El archivo '{can_path.name}' ya existe en '{can_path.parent}'. Sobrescribirlo requiere tu aprobación."
                return ActionState.PENDING_APPROVAL, canonical_args, reason

            return ActionState.APPROVED, canonical_args, None

        elif tool_name == "files.copy":
            src = arguments.get("source", "")
            dst = arguments.get("destination", "")
            can_src = self.canonicalize_path(src, scope.read_roots, allow_must_exist=True)
            can_dst = self.canonicalize_path(dst, scope.write_roots, allow_must_exist=False)
            canonical_args["source"] = str(can_src)
            canonical_args["destination"] = str(can_dst)

            if can_dst.exists():
                reason = f"Copiar a '{can_dst.name}' sobrescribirá un archivo existente. Requiere aprobación."
                return ActionState.PENDING_APPROVAL, canonical_args, reason

            return ActionState.APPROVED, canonical_args, None

        elif tool_name == "files.move":
            src = arguments.get("source", "")
            dst = arguments.get("destination", "")
            can_src = self.canonicalize_path(src, scope.write_roots, allow_must_exist=True)
            can_dst = self.canonicalize_path(dst, scope.write_roots, allow_must_exist=False)
            canonical_args["source"] = str(can_src)
            canonical_args["destination"] = str(can_dst)
            reason = f"Mover '{can_src.name}' a '{can_dst}' altera la ubicación del archivo original. Requiere aprobación."
            return ActionState.PENDING_APPROVAL, canonical_args, reason

        # 2. Herramientas de escritorio
        elif tool_name.startswith("desktop."):
            app_name = arguments.get("app_name", "").strip()
            if tool_name == "desktop.open_app":
                if scope.allowed_apps and app_name.lower() not in [a.lower() for a in scope.allowed_apps]:
                    raise PolicyViolation(
                        f"La aplicación '{app_name}' no está en la lista de aplicaciones autorizadas para esta tarea.",
                        code="APP_NOT_ALLOWED",
                    )
            return ActionState.APPROVED, canonical_args, None

        # 3. Herramientas de navegador
        elif tool_name.startswith("browser."):
            url = arguments.get("url", "").strip()
            if tool_name == "browser.open":
                if not url:
                    raise PolicyViolation("URL no proporcionada para browser.open", code="INVALID_URL")
                # Validar dominio si allowed_domains está configurado
                if scope.allowed_domains:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    hostname = parsed.hostname or ""
                    matched = any(
                        hostname == d or hostname.endswith("." + d)
                        for d in scope.allowed_domains
                    )
                    if not matched and not (hostname in ("127.0.0.1", "localhost")):
                        raise PolicyViolation(
                            f"El dominio '{hostname}' no está permitido en el alcance de la tarea.",
                            code="DOMAIN_NOT_ALLOWED",
                        )
            return ActionState.APPROVED, canonical_args, None

        # 4. Herramientas de interacción humana
        elif tool_name in ("user.request_input", "user.request_approval"):
            return ActionState.APPROVED, canonical_args, None

        # Acción no reconocida
        raise PolicyViolation(
            f"Herramienta desconocida o no registrada en política: '{tool_name}'",
            code="UNKNOWN_TOOL",
        )
