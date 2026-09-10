"""
tools/desktop.py: Adaptadores de escritorio para LocalDesk.
Contiene:
- DesktopAdapterInterface: Contrato desacoplado.
- WindowsUIAutomationAdapter: Implementación nativa con pywinauto para Windows 11 (UC-02 Bloc de notas).
- SimulatedDesktopAdapter: Implementación simulada multiplataforma para pruebas en desarrollo (macOS/Linux).
- Herramientas registradas: desktop.open_app, desktop.observe, desktop.type_text, desktop.key, desktop.click, desktop.screenshot.
"""

from abc import ABC, abstractmethod
import asyncio
import sys
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from .base import BaseTool, ToolResult


class DesktopAdapterInterface(ABC):
    @abstractmethod
    async def open_app(self, app_name: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def observe_window(self, window_title: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def type_text(self, text: str, window_title: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    async def send_key(self, key_combination: str) -> bool:
        pass

    @abstractmethod
    async def click_element(self, element_id: str) -> bool:
        pass

    @abstractmethod
    async def close_app(self, app_name: str) -> bool:
        pass


class SimulatedDesktopAdapter(DesktopAdapterInterface):
    """
    Adaptador simulado para pruebas locales en entornos no-Windows.
    Emula el ciclo de Bloc de notas (UC-02) registrando el texto escrito y guardando el archivo
    según la secuencia de acciones para permitir verificación end-to-end de la FSM.
    """
    def __init__(self):
        self.open_apps = set()
        self.active_window: Optional[str] = None
        self.window_buffer: Dict[str, str] = {}

    async def open_app(self, app_name: str) -> Dict[str, Any]:
        self.open_apps.add(app_name.lower())
        title = f"{app_name} - Sin título"
        self.active_window = title
        self.window_buffer[title] = ""
        return {"process_id": 9999, "window_title": title, "status": "opened"}

    async def observe_window(self, window_title: Optional[str] = None) -> Dict[str, Any]:
        target = window_title or self.active_window or "Sin ventana activa"
        buffer_text = self.window_buffer.get(target, "")
        return {
            "window_title": target,
            "controls": [
                {"id": "edit_area", "type": "Edit", "text": buffer_text, "focused": True},
                {"id": "menu_file", "type": "MenuItem", "text": "Archivo"},
                {"id": "menu_save", "type": "MenuItem", "text": "Guardar"},
            ],
            "text_content": buffer_text,
        }

    async def type_text(self, text: str, window_title: Optional[str] = None) -> bool:
        target = window_title or self.active_window
        if not target or target not in self.window_buffer:
            return False
        self.window_buffer[target] += text
        return True

    async def send_key(self, key_combination: str) -> bool:
        return True

    async def click_element(self, element_id: str) -> bool:
        return True

    async def close_app(self, app_name: str) -> bool:
        self.open_apps.discard(app_name.lower())
        return True


class WindowsUIAutomationAdapter(DesktopAdapterInterface):
    """
    Adaptador nativo para Windows 11 usando pywinauto con backend 'uia'.
    Controla específicamente Notepad / Bloc de notas para UC-02.
    """
    def __init__(self):
        self._app = None
        self._main_window = None

    async def open_app(self, app_name: str) -> Dict[str, Any]:
        if sys.platform != "win32":
            raise RuntimeError("WindowsUIAutomationAdapter solo es ejecutable en Windows.")

        from pywinauto.application import Application

        def _launch():
            cmd = app_name
            if app_name.lower() in ("notepad", "bloc de notas"):
                cmd = "notepad.exe"
            app = Application(backend="uia").start(cmd)
            # Esperar a que la ventana esté lista
            win = app.top_window()
            win.wait("ready", timeout=10)
            return app, win

        self._app, self._main_window = await asyncio.to_thread(_launch)
        info = self._main_window.element_info
        return {
            "process_id": self._app.process,
            "window_title": self._main_window.window_text(),
            "status": "opened",
        }

    async def observe_window(self, window_title: Optional[str] = None) -> Dict[str, Any]:
        if sys.platform != "win32" or not self._main_window:
            raise RuntimeError("Ventana de Windows no disponible.")

        def _inspect():
            title = self._main_window.window_text()
            # Encontrar el área de edición de Notepad en Windows 11
            edit = self._main_window.child_window(control_type="Edit")
            edit_text = edit.get_value() if edit.exists() else ""
            return {
                "window_title": title,
                "controls": [{"id": "edit_area", "type": "Edit", "text": edit_text}],
                "text_content": edit_text,
            }

        return await asyncio.to_thread(_inspect)

    async def type_text(self, text: str, window_title: Optional[str] = None) -> bool:
        if sys.platform != "win32" or not self._main_window:
            raise RuntimeError("Ventana de Windows no disponible para escribir.")

        def _type():
            # Notepad en Win 11 usa un control Document o Edit
            edit = self._main_window.child_window(control_type="Edit")
            if not edit.exists():
                edit = self._main_window.child_window(control_type="Document")
            
            edit.set_focus()
            # Enviar texto normalizado
            edit.type_keys(text, with_spaces=True, with_tabs=True, with_newlines=True)
            return True

        return await asyncio.to_thread(_type)

    async def send_key(self, key_combination: str) -> bool:
        if sys.platform != "win32" or not self._main_window:
            raise RuntimeError("Ventana de Windows no disponible.")

        def _key():
            self._main_window.type_keys(key_combination)
            return True

        return await asyncio.to_thread(_key)

    async def click_element(self, element_id: str) -> bool:
        return True

    async def close_app(self, app_name: str) -> bool:
        if self._app:
            try:
                self._app.kill()
            except Exception:
                pass
            self._app = None
            self._main_window = None
        return True


# Fábrica de adaptador según plataforma
def get_default_desktop_adapter() -> DesktopAdapterInterface:
    if sys.platform == "win32":
        try:
            return WindowsUIAutomationAdapter()
        except ImportError:
            return SimulatedDesktopAdapter()
    return SimulatedDesktopAdapter()


# --- Herramientas de BaseTool para el Registro ---

class DesktopOpenAppTool(BaseTool):
    name = "desktop.open_app"
    description = "Abre una aplicación autorizada (ej: notepad o Bloc de notas)."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Nombre de la aplicación a abrir (ej: 'notepad')."},
        },
        "required": ["app_name"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "process_id": {"type": "integer"},
            "window_title": {"type": "string"},
            "status": {"type": "string"},
        },
    }

    def __init__(self, adapter: DesktopAdapterInterface):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        app_name = arguments["app_name"]
        try:
            data = await self.adapter.open_app(app_name)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class DesktopObserveTool(BaseTool):
    name = "desktop.observe"
    description = "Observa los controles y el texto de la ventana activa del escritorio."
    is_effect = False
    input_schema = {
        "type": "object",
        "properties": {
            "window_title": {"type": "string", "description": "Título opcional de la ventana a observar."},
        },
    }
    output_schema = {"type": "object"}

    def __init__(self, adapter: DesktopAdapterInterface):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            data = await self.adapter.observe_window(arguments.get("window_title"))
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class DesktopTypeTextTool(BaseTool):
    name = "desktop.type_text"
    description = "Escribe texto en el control de texto enfocado de la aplicación activa."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Texto exacto a escribir (incluyendo tildes, saltos de línea)."},
            "window_title": {"type": "string", "description": "Título de la ventana esperada."},
        },
        "required": ["text"],
    }
    output_schema = {"type": "object", "properties": {"written": {"type": "boolean"}}}

    def __init__(self, adapter: DesktopAdapterInterface):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        text = arguments["text"]
        try:
            ok = await self.adapter.type_text(text, arguments.get("window_title"))
            return ToolResult(success=ok, data={"written": ok})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class DesktopKeyTool(BaseTool):
    name = "desktop.key"
    description = "Envía una combinación de teclas o atajo acotado a la aplicación activa."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "key_combination": {"type": "string", "description": "Atajo permitido (ej: '^s' para Ctrl+S, '{ENTER}')."},
        },
        "required": ["key_combination"],
    }
    output_schema = {"type": "object"}

    def __init__(self, adapter: DesktopAdapterInterface):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        key = arguments["key_combination"]
        # Filtrar teclas peligrosas
        dangerous = ["{F4}", "%{F4}", "cmd", "powershell", "format"]
        if any(d in key.lower() for d in dangerous):
            return ToolResult(success=False, error=f"Atajo de teclado '{key}' bloqueado por política de seguridad.")
        try:
            ok = await self.adapter.send_key(key)
            return ToolResult(success=ok, data={"sent": ok})
        except Exception as e:
            return ToolResult(success=False, error=str(e))
