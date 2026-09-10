"""
providers/fake.py: Proveedor simulado determinista para pruebas automatizadas de LocalDesk.
Identificado siempre como simulación (Sección 6.2).
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional
from .base import ModelProvider, ModelCapabilities, ModelResponse
from local_agent.domain.models import TaskProposal


class FakeModelProvider(ModelProvider):
    def __init__(self, canned_responses: Optional[List[ModelResponse]] = None):
        self.canned_responses = canned_responses or []
        self._step_idx = 0
        self.custom_responder: Optional[Callable[[List[Dict[str, Any]]], ModelResponse]] = None

    async def health(self) -> bool:
        return True

    async def list_models(self) -> List[str]:
        return ["fake-model-test:latest"]

    async def get_capabilities(self, model_id: str) -> ModelCapabilities:
        return ModelCapabilities(
            model_id=model_id,
            supports_tools=True,
            supports_vision=True,
            context_length=8192,
            quantization="q4_0",
            digest="fake-sha256-digest",
            tested_locally=True,
            is_simulation=True,
        )

    def set_custom_responder(self, responder: Callable[[List[Dict[str, Any]]], ModelResponse]):
        self.custom_responder = responder

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        model_id: Optional[str] = None,
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ModelResponse:
        if cancellation_token and cancellation_token.is_set():
            raise asyncio.CancelledError("Cancelado antes de la inferencia.")

        if self.custom_responder:
            return self.custom_responder(messages)

        if self._step_idx < len(self.canned_responses):
            resp = self.canned_responses[self._step_idx]
            self._step_idx += 1
            return resp

        # Si no hay respuestas pregrabadas configuradas, actuar de forma heurística para demostración
        # Inspeccionar el último mensaje del usuario para detectar si se requiere un archivo de salida
        user_msgs = [m.get("content", "") for m in messages if m.get("role") == "user"]
        full_user_context = " ".join(user_msgs).lower()

        if self._step_idx == 0:
            self._step_idx += 1
            # Si se menciona un archivo de salida o propuesta, generar files.write
            import re
            match = re.search(r"salida requerido:\s*'([^']+)'", full_user_context) or re.search(r"esperado:\s*([^\s\n]+)", full_user_context)
            out_file = match.group(1) if match else "resultado.md"

            return ModelResponse(
                tool_calls=[
                    TaskProposal(
                        tool="files.write",
                        arguments={
                            "path": out_file,
                            "content": (
                                "# Reporte de Comparación y Diferencias\n\n"
                                "- **Fecha de entrega:** Opción Alfa (15 de marzo de 2026) vs Opción Beta (28 de abril de 2026)\n"
                                "- **Monto total:** Opción Alfa ($45.000 USD) vs Opción Beta ($62.000 USD)\n"
                                "- **Alcance:** Opción Alfa (30 días garantía) vs Opción Beta (12 meses soporte 24/7)\n"
                            ),
                        },
                        brief_reason=f"Generar archivo de salida requerido '{out_file}'",
                        expected_result=f"Existe {out_file} con contenido verificado",
                    )
                ],
                inference_duration_seconds=0.05,
            )

        # Paso final: indicar conclusión
        return ModelResponse(
            content="Todas las acciones requeridas han concluido satisfactoriamente y fueron verificadas.",
            tool_calls=[],
            prompt_tokens=50,
            completion_tokens=20,
            inference_duration_seconds=0.05,
        )
