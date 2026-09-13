#!/usr/bin/env python3
"""
diagnose_env.py: Diagnóstico del entorno de desarrollo y ejecución de LocalDesk.
Inspecciona:
- Sistema operativo y arquitectura
- Python, Node.js, npm, Rust/Cargo
- Memoria RAM y procesador
- Disponibilidad y modelos de Ollama
- Soporte para Playwright (incluida la descarga real del navegador) y pywinauto
"""

import sys
import platform
import subprocess
import json
import urllib.request
import urllib.error
import os

def check_cmd(cmd):
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return res.returncode == 0, res.stdout.strip()
    except Exception as e:
        return False, str(e)

def get_system_info():
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python": sys.version.split()[0],
        "python_path": sys.executable,
    }
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
        info["ram_available_gb"] = round(mem.available / (1024 ** 3), 2)
        info["cpu_cores"] = psutil.cpu_count(logical=True)
    except ImportError:
        info["ram_total_gb"] = "psutil no instalado"
        info["cpu_cores"] = "desconocido"
    return info

def check_ollama(base_url="http://127.0.0.1:11434"):
    report = {
        "reachable": False,
        "base_url": base_url,
        "models": [],
        "version": None,
        "error": None
    }
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "LocalDesk-Diag/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                report["reachable"] = True
                report["models"] = [m.get("name") for m in data.get("models", [])]
        
        # Check version endpoint if available
        try:
            v_req = urllib.request.Request(f"{base_url}/api/version")
            with urllib.request.urlopen(v_req, timeout=2) as v_resp:
                if v_resp.status == 200:
                    v_data = json.loads(v_resp.read().decode("utf-8"))
                    report["version"] = v_data.get("version")
        except Exception:
            pass

    except Exception as e:
        report["error"] = str(e)
    return report

def check_playwright_chromium():
    """
    Comprueba que el navegador de Playwright esté realmente utilizable.
    Instalar el paquete 'playwright' con pip NO descarga los binarios del
    navegador, así que aquí se lanza Chromium headless y se cierra: es la
    única verificación equivalente a lo que hacen BrowserAdapter y la
    prueba UC-03 (headless usa 'chrome-headless-shell', un binario distinto
    del Chromium completo que reporta executable_path).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "no aplicable (paquete playwright no instalado)"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                return f"disponible (Chromium {browser.version})"
            finally:
                browser.close()
    except Exception as e:
        detalle = str(e).splitlines()[0]
        return (
            f"NO utilizable -> ejecuta 'playwright install chromium'. Detalle: {detalle}"
        )


def check_tools():
    tools = {}
    ok_node, out_node = check_cmd(["node", "--version"])
    tools["node"] = out_node if ok_node else "no instalado"

    ok_npm, out_npm = check_cmd(["npm", "--version"])
    tools["npm"] = out_npm if ok_npm else "no instalado"

    ok_cargo, out_cargo = check_cmd(["cargo", "--version"])
    tools["cargo"] = out_cargo if ok_cargo else "no instalado"

    try:
        import playwright
        tools["playwright_python"] = playwright.__file__
    except ImportError:
        tools["playwright_python"] = "no instalado en este entorno"

    tools["playwright_chromium"] = check_playwright_chromium()

    try:
        import pywinauto
        tools["pywinauto"] = "disponible (Windows UIA nativo)"
    except ImportError:
        tools["pywinauto"] = "no disponible (se usará SimulatedDesktopAdapter para pruebas)"

    return tools

def main():
    print("=" * 60)
    print(" DIAGNÓSTICO DEL ENTORNO - LocalDesk")
    print("=" * 60)
    
    sys_info = get_system_info()
    print("\n[+] Sistema:")
    for k, v in sys_info.items():
        print(f"  - {k}: {v}")

    tools = check_tools()
    print("\n[+] Herramientas y Bibliotecas:")
    for k, v in tools.items():
        print(f"  - {k}: {v}")

    print("\n[+] Servicio Ollama Local:")
    ollama_info = check_ollama()
    print(f"  - Accesible: {'SÍ' if ollama_info['reachable'] else 'NO'}")
    if ollama_info["reachable"]:
        print(f"  - Versión: {ollama_info.get('version', 'N/D')}")
        print(f"  - Modelos instalados ({len(ollama_info['models'])}):")
        for m in ollama_info["models"]:
            print(f"      * {m}")
    else:
        print(f"  - Detalle: {ollama_info['error']}")

    print("\n" + "=" * 60)
    print(" Diagnóstico finalizado.")
    print("=" * 60)

if __name__ == "__main__":
    main()
