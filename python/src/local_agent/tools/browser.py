"""
tools/browser.py: Adaptador de navegador dedicado con Playwright para LocalDesk (UC-03).
Perfil aislado, sin cookies personales ni extensiones.
"""

import asyncio
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .base import BaseTool, ToolResult


class BrowserAdapter:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._lock = asyncio.Lock()

    async def _ensure_page(self) -> Page:
        async with self._lock:
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            if self._browser is None:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            if self._context is None:
                # Perfil dedicado e independiente
                self._context = await self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) LocalDesk/1.0",
                )
            if self._page is None or self._page.is_closed():
                self._page = await self._context.new_page()
            return self._page

    async def close(self) -> None:
        async with self._lock:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            self._page = None

    async def open_url(self, url: str) -> Dict[str, Any]:
        page = await self._ensure_page()
        res = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        status = res.status if res else 200
        title = await page.title()
        return {"url": page.url, "title": title, "status": status}

    async def observe(self) -> Dict[str, Any]:
        page = await self._ensure_page()
        title = await page.title()
        url = page.url

        # Extraer elementos de formulario accesibles
        inputs = await page.evaluate(
            """() => {
                const results = [];
                document.querySelectorAll('input, select, textarea, button').forEach(el => {
                    results.push({
                        tag: el.tagName.toLowerCase(),
                        id: el.id || '',
                        name: el.name || '',
                        type: el.type || '',
                        placeholder: el.placeholder || '',
                        value: el.value || '',
                        text: el.innerText || el.textContent || '',
                    });
                });
                return results;
            }"""
        )
        content = await page.inner_text("body")
        return {"url": url, "title": title, "elements": inputs, "body_text": content[:2000]}

    async def fill_field(self, selector: str, value: str) -> Dict[str, Any]:
        page = await self._ensure_page()
        await page.fill(selector, value, timeout=10000)
        # Verificar que el valor se asignó
        actual_val = await page.input_value(selector)
        return {"selector": selector, "value": actual_val, "verified": actual_val == value}

    async def click_element(self, selector: str) -> Dict[str, Any]:
        page = await self._ensure_page()
        await page.click(selector, timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=5000)
        return {"clicked": selector, "current_url": page.url}


# --- Herramientas para el registro ---

class BrowserOpenTool(BaseTool):
    name = "browser.open"
    description = "Navega a una URL autorizada en un navegador dedicado y aislado."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL a abrir (debe pertenecer a dominios autorizados)."},
        },
        "required": ["url"],
    }
    output_schema = {"type": "object"}

    def __init__(self, adapter: BrowserAdapter):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        url = arguments["url"]
        try:
            data = await self.adapter.open_url(url)
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BrowserObserveTool(BaseTool):
    name = "browser.observe"
    description = "Observa la página web actual: lee campos de formulario, botones y texto."
    is_effect = False
    input_schema = {"type": "object"}
    output_schema = {"type": "object"}

    def __init__(self, adapter: BrowserAdapter):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            data = await self.adapter.observe()
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BrowserFillTool(BaseTool):
    name = "browser.fill"
    description = "Completa un campo de formulario identificado por selector CSS o ID."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "Selector CSS del campo (ej: '#nombre', 'input[name=\"email\"]')."},
            "value": {"type": "string", "description": "Texto a ingresar en el campo."},
        },
        "required": ["selector", "value"],
    }
    output_schema = {"type": "object"}

    def __init__(self, adapter: BrowserAdapter):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            data = await self.adapter.fill_field(arguments["selector"], arguments["value"])
            return ToolResult(success=data.get("verified", True), data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class BrowserClickTool(BaseTool):
    name = "browser.click"
    description = "Hace clic en un botón, enlace o elemento de la página web."
    is_effect = True
    input_schema = {
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "Selector CSS del elemento (ej: '#btn-submit', 'button[type=\"submit\"]')."},
        },
        "required": ["selector"],
    }
    output_schema = {"type": "object"}

    def __init__(self, adapter: BrowserAdapter):
        self.adapter = adapter

    async def execute(
        self,
        arguments: Dict[str, Any],
        cancellation_token: Optional[asyncio.Event] = None,
    ) -> ToolResult:
        try:
            data = await self.adapter.click_element(arguments["selector"])
            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=str(e))
