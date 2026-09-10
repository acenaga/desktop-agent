"""
providers/ollama.py: Proveedor local para Ollama (Sección 6).
Verifica:
- Conexión loopback local estricta (rechazo de proxies remotos y cloud).
- Consulta de tags (/api/tags) y detalles de modelo (/api/show).
- Ejecución de chat con llamada a herramientas (/api/chat con tools).
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
import httpx

from .base import ModelProvider, ModelCapabilities, ModelResponse
from local_agent.domain.models import TaskProposal


class OllamaProviderError(Exception):
    pass


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        request_timeout_seconds: float = 120.0,
        require_local_execution: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds
        self.require_local_execution = require_local_execution

        # Validación estricta de ejecución local (Sección 6.1)
        if self.require_local_execution:
            from urllib.parse import urlparse
            parsed = urlparse(self.base_url)
            host = parsed.hostname or ""
            if host not in ("127.0.0.1", "localhost", "::1"):
                raise OllamaProviderError(
                    f"Inferencia remota rechazada por política: '{self.base_url}' no es una dirección loopback local."
                )

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.request_timeout_seconds,
            headers={"User-Agent": "LocalDesk/1.0"},
        )

    async def health(self) -> bool:
        try:
            async with await self._get_client() as client:
                res = await client.get("/api/tags", timeout=3.0)
                return res.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        try:
            async with await self._get_client() as client:
                res = await client.get("/api/tags")
                if res.status_code != 200:
                    return []
                data = res.json()
                return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception as e:
            return []

    async def get_capabilities(self, model_id: str) -> ModelCapabilities:
        try:
            async with await self._get_client() as client:
                res = await client.post("/api/show", json={"model": model_id})
                if res.status_code != 200:
                    return ModelCapabilities(
                        model_id=model_id,
                        supports_tools=False,
                        supports_vision=False,
                        context_length=4096,
                    )
                data = res.json()
                details = data.get("details", {})
                modelfile = data.get("modelfile", "")
                
                # Heurística de capacidades a partir de detalles y modelfile
                supports_tools = "tools" in data or "tool_calls" in modelfile.lower() or "qwen" in model_id.lower()
                supports_vision = "clip" in modelfile.lower() or "vision" in modelfile.lower() or "vision" in model_id.lower()

                return ModelCapabilities(
                    model_id=model_id,
                    supports_tools=supports_tools,
                    supports_vision=supports_vision,
                    context_length=data.get("model_info", {}).get("general.context_length", 8192),
                    quantization=details.get("quantization_level"),
                    digest=data.get("digest"),
                    tested_locally=True,
                    is_simulation=False,
                )
        except Exception:
            return ModelCapabilities(
                model_id=model_id,
                supports_tools=False,
                supports_vision=False,
                context_length=4096,
            )

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_id: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ModelResponse:
        if not model_id:
            raise OllamaProviderError("No se ha seleccionado ningún modelo para inferencia.")

        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Cancelado antes de enviar la solicitud a Ollama.")

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        start_time = time.time()
        try:
            async with await self._get_client() as client:
                req_task = asyncio.create_task(client.post("/api/chat", json=payload))
                
                # Chequeo periódico de cancelación mientras espera respuesta del modelo (Sección 7.2)
                while not req_task.done():
                    if cancellation_token and cancellation_token.is_set():
                        req_task.cancel()
                        raise asyncio.CancelledError("Solicitud al modelo cancelada por el usuario.")
                    await asyncio.sleep(0.1)

                res = await req_task
                if res.status_code != 200:
                    raise OllamaProviderError(f"Ollama respondió con error HTTP {res.status_code}: {res.text}")

                data = res.json()
        except httpx.RequestError as e:
            raise OllamaProviderError(f"Error de comunicación con Ollama local: {str(e)}")

        duration = time.time() - start_time
        msg = data.get("message", {})
        content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])

        proposals: List[TaskProposal] = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            fname = func.get("name")
            fargs = func.get("arguments", {})
            if isinstance(fargs, str):
                try:
                    fargs = json.loads(fargs)
                except Exception:
                    fargs = {"raw_args": fargs}

            proposals.append(
                TaskProposal(
                    tool=fname,
                    arguments=fargs,
                    brief_reason=f"Ejecución de {fname} propuesta por el modelo",
                    expected_result=f"Resultado exitoso de {fname}",
                )
            )

        return ModelResponse(
            content=content,
            tool_calls=proposals,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            inference_duration_seconds=duration,
            raw_response=data,
        )
