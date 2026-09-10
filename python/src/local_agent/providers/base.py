"""
providers/base.py: Contrato base de proveedor de modelos para LocalDesk.
"""

from abc import ABC, abstractmethod
import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from local_agent.domain.models import TaskProposal


class ModelCapabilities(BaseModel):
    model_id: str
    supports_tools: bool = True
    supports_vision: bool = False
    context_length: int = 8192
    quantization: Optional[str] = None
    digest: Optional[str] = None
    tested_locally: bool = False
    is_simulation: bool = False


class ModelResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: List[TaskProposal] = Field(default_factory=list)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    inference_duration_seconds: Optional[float] = None
    raw_response: Optional[Dict[str, Any]] = None


class ModelProvider(ABC):
    @abstractmethod
    async def health(self) -> bool:
        """Comprueba disponibilidad del motor de inferencia."""
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """Lista los modelos instalados y listos para inferencia."""
        pass

    @abstractmethod
    async def get_capabilities(self, model_id: str) -> ModelCapabilities:
        """Devuelve capacidades técnicas del modelo (visión, herramientas, contexto)."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_id: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ModelResponse:
        """Solicita una decisión o generación estructurada al modelo."""
        pass
