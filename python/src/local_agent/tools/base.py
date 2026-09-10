"""
tools/base.py: Abstracción base para herramientas, registro y ejecutor con verificación de postcondiciones.
"""

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)  # Rutas de archivos generados/modificados


class BaseTool(ABC):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    timeout_seconds: float = 15.0
    is_effect: bool = False  # True si altera el entorno (escritura, clic, atajo)

    @abstractmethod
    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        """Ejecuta la herramienta con los argumentos canónicos validados."""
        pass

    async def verify_postcondition(
        self, arguments: Dict[str, Any], result: ToolResult
    ) -> bool:
        """
        Verificación de postcondición independiente de la palabra del modelo.
        Por defecto retorna result.success, pero herramientas con efectos
        (ej: files.write o desktop.type_text) sobreescriben esto para comprobar el sistema real.
        """
        return result.success


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_definitions_for_llm(self) -> List[Dict[str, Any]]:
        """Formato normalizado de herramientas para OpenAI/Ollama tool calling."""
        defs = []
        for t in self._tools.values():
            defs.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            })
        return defs


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute_tool(
        self,
        tool_name: str,
        canonical_args: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
        custom_timeout: Optional[float] = None,
    ) -> ToolResult:
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Herramienta '{tool_name}' no encontrada en el registro.",
            )

        if cancellation_token and cancellation_token.is_set():
            return ToolResult(
                success=False,
                error="Ejecución cancelada antes de iniciar la herramienta.",
            )

        timeout = custom_timeout or tool.timeout_seconds
        try:
            # Ejecutar con timeout estricto
            result = await asyncio.wait_for(
                tool.execute(canonical_args, cancellation_token),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Timeout de {timeout}s superado al ejecutar '{tool_name}'.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Excepción no controlada en herramienta '{tool_name}': {str(e)}",
            )

        # Verificación de postcondición independiente
        try:
            verified = await tool.verify_postcondition(canonical_args, result)
            if not verified:
                return ToolResult(
                    success=False,
                    error=f"La postcondición de '{tool_name}' no se pudo verificar externamente.",
                    data=result.data,
                )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error al verificar postcondición de '{tool_name}': {str(e)}",
            )

        return result
