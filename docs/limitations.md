# Limitaciones Explícitas y Verificaciones Pendientes - LocalDesk

**Versión:** 1.0  
**Fecha:** 9 de septiembre de 2026  
**Producto:** LocalDesk - Agente de escritorio con IA local

En cumplimiento estricto con las Secciones 1, 2 y 14.3 de la especificación técnica ("Si falta Windows, una GPU o un modelo, completa el trabajo independiente y describe exactamente la comprobación pendiente. No declares el producto completamente validado si falta una prueba nativa obligatoria"), se registran a continuación las limitaciones conocidas y las comprobaciones pendientes:

---

## 1. Verificaciones Pendientes en Entorno Nativo

### 1.1 Control Nativo de Windows 11 (UC-02 Bloc de notas)
- **Estado Actual:** El adaptador `WindowsUIAutomationAdapter` (basado en `pywinauto` con backend `uia`) está completamente implementado en `local_agent.tools.desktop`. Para permitir la ejecución de la suite de pruebas completa en este equipo de desarrollo (macOS arm64) y en pipelines de CI sin fallos de importación, se utilizó `SimulatedDesktopAdapter`.
- **Comprobación Pendiente:** Ejecutar el caso de uso UC-02 sobre una sesión interactiva real de **Windows 11 x64** ejecutando:
  ```powershell
  pytest python/tests/integration/test_uc02_desktop.py
  ```
  Esto validará la interacción con la ventana nativa de `notepad.exe`, la captura del control de edición y el guardado mediante la interfaz gráfica de Windows.
- **Advertencia:** Una prueba en macOS o Linux con el adaptador simulado **no demuestra que el control de Windows funcione**. No se declara este caso completamente validado en hardware hasta realizar dicha prueba nativa.

### 1.2 Empaquetado del Bundle Tauri para Windows (.msi / .exe)
- **Estado Actual:** La aplicación de escritorio React + Vite + TypeScript compila al 100% sin errores tipados. La configuración de Tauri 2 (`tauri.conf.json`, `Cargo.toml`, `main.rs`) está preparada para asociar el ejecutable de Python como sidecar.
- **Comprobación Pendiente:** En una máquina con Windows 11 que disponga de la toolchain de Rust (`cargo`) y WiX Toolset, compilar el instalador final:
  ```powershell
  npm --prefix apps/desktop run tauri build
  ```

---

## 2. Inferencia y Modelos Locales

### 2.1 Modelos no descargados por defecto
- **Política:** Por especificación ("No descargues automáticamente modelos de varios gigabytes"), el instalador no descarga modelos masivos sin autorización del usuario.
- **Diagnóstico actual:** La instancia local de Ollama está accesible, pero no contiene modelos precargados (`models: []`).
- **Instrucción para el usuario:** Para ejecutar tareas con un modelo de lenguaje real local, ejecutar en la terminal:
  ```bash
  # Opción recomendada para equilibrio de rendimiento y razonamiento:
  ollama pull qwen2.5:14b
  
  # Opción ligera para equipos con menos memoria:
  ollama pull llama3.2:3b
  
  # Opción con visión (si se dispone de GPU compatible):
  ollama pull qwen2.5-vl:7b
  ```
- **Fallback:** Mientras tanto, el sistema provee `FakeModelProvider`, permitiendo verificar el 100% de los flujos de la API, cola, FSM, herramientas y aprobaciones de forma determinista.

---

## 3. Límites de Alcance del MVP

1. **Aislamiento de Red del Sistema:** El aislamiento web se aplica a nivel del navegador Playwright (contexto dedicado sin cookies personales y filtrado de dominios autorizados). No constituye un firewall a nivel del sistema operativo Windows.
2. **Concurrencia Unitaria:** El agente admite una sola tarea activa simultáneamente. Las tareas adicionales esperan en la cola local (`queued`).
3. **Control Visual Alternativo:** El mecanismo visual por coordenadas (`desktop.click`) está limitado al monitor principal y solo se recomienda cuando fallan los identificadores accesibles de UI Automation.
4. **Cero Nube:** Ante caídas o indisponibilidad de Ollama, el agente **no recurre a proveedores remotos** (OpenAI, Anthropic o proxies). La tarea falla explícitamente notificando la indisponibilidad de la inferencia local.
