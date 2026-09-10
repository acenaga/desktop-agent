#!/usr/bin/env python3
"""
scripts/package_backend.py: Script de empaquetado del servicio Python como binario ejecutable
para su integración como sidecar de Tauri 2 (Sección 4.2 y 13 Fase 4).
"""

import os
import sys
import platform
import subprocess
from pathlib import Path

def main():
    print("=" * 60)
    print(" EMPAQUETADOR DE SERVICIO PYTHON - LocalDesk Sidecar")
    print("=" * 60)

    target_os = platform.system()
    arch = platform.machine()
    print(f"[+] Plataforma actual: {target_os} ({arch})")

    tauri_bin_dir = Path("apps/desktop/src-tauri/binaries")
    tauri_bin_dir.mkdir(parents=True, exist_ok=True)

    # Nombre del binario sidecar según convención de Tauri 2 (binario-<target-triple>)
    # En Windows: local-agent-backend-x86_64-pc-windows-msvc.exe
    # En macOS arm64: local-agent-backend-aarch64-apple-darwin
    ext = ".exe" if target_os == "Windows" else ""
    target_triple = "x86_64-pc-windows-msvc" if target_os == "Windows" else "aarch64-apple-darwin"
    binary_name = f"local-agent-backend-{target_triple}{ext}"
    output_target = tauri_bin_dir / binary_name

    print(f"[+] Destino del binario sidecar: {output_target}")
    
    # Comprobar si PyInstaller está instalado
    try:
        import PyInstaller
        has_pyinstaller = True
    except ImportError:
        has_pyinstaller = False

    if not has_pyinstaller:
        print("[!] PyInstaller no está instalado en el entorno.")
        print("    Para generar el ejecutable nativo, instala PyInstaller: pip install pyinstaller")
        print("    Comando de empaquetado previsto:")
        print(f"    pyinstaller --onefile --name {binary_name} python/src/local_agent/cli.py --distpath {tauri_bin_dir}")
        return

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name",
        binary_name,
        "--distpath",
        str(tauri_bin_dir),
        "python/src/local_agent/cli.py",
    ]

    print(f"[+] Ejecutando PyInstaller: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"[+] Empaquetado exitoso en {output_target}")
    else:
        print(f"[!] Falló la compilación de PyInstaller con código {res.returncode}")

if __name__ == "__main__":
    main()
