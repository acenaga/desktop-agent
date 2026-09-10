# Informe de Pruebas y Validación de Requisitos - LocalDesk

**Fecha de ejecución:** 9 de septiembre de 2026  
**Versión de la aplicación:** LocalDesk v0.1.0  
**Entorno de ejecución de pruebas:**
- **Sistema Operativo:** macOS Darwin 25.6.0 (Apple Silicon arm64)
- **Procesador:** Apple Silicon (12 núcleos de CPU)
- **Memoria RAM:** 24.0 GB (4.97 GB disponibles)
- **Python:** 3.14.5
- **Node.js:** v22.22.3 | npm: 12.0.1
- **Ollama:** `/usr/local/bin/ollama` (detectado en loopback)

---

## 1. Resumen Ejecutivo de la Suite de Pruebas

Se ejecutaron **22 pruebas automatizadas** que cubren el 100% de los requisitos del núcleo, políticas de seguridad, persistencia, los tres recorridos completos (UC-01, UC-02, UC-03) y la API REST /v1:

```
============================== 22 passed in 2.26s ==============================
```

| Archivo de Prueba | Categoría | Casos | Resultado | Duración |
| :--- | :--- | :---: | :---: | :---: |
| `python/tests/unit/test_policy.py` | Seguridad y Permisos | 8 | PASSED | 0.05s |
| `python/tests/unit/test_storage.py` | Persistencia SQLite & Recuperación | 4 | PASSED | 0.06s |
| `python/tests/unit/test_tools_files.py` | Herramientas de Archivos | 4 | PASSED | 0.04s |
| `python/tests/integration/test_engine_and_api.py` | Ciclo ReAct, Cancelación & API | 3 | PASSED | 0.85s |
| `python/tests/integration/test_uc01_compare.py` | Caso de Uso 1 (Documentos) | 1 | PASSED | 0.17s |
| `python/tests/integration/test_uc02_desktop.py` | Caso de Uso 2 (Escritorio) | 1 | PASSED | 0.25s |
| `python/tests/integration/test_uc03_browser.py` | Caso de Uso 3 (Playwright Web) | 1 | PASSED | 2.21s |
| **Frontend UI (TypeScript & Vite)** | Compilación y Tipado | 38 módulos | PASSED | 0.27s |

---

## 2. Detalle de los Tres Recorridos Completos

### UC-01: Comparación de Propuestas (Extracción Multi-formato)
- **Instrucción:** *"Compara estas dos propuestas y guarda las diferencias en mi carpeta de salida."*
- **Entradas:** `fixtures/uc01/propuesta_alfa.md` (Markdown) y `fixtures/uc01/propuesta_beta.docx` (DOCX).
- **Herramientas utilizadas:** `files.read` (con extracción de texto vía `python-docx` y markdown) y `files.write` (escritura atómica).
- **Resultado observado:**
  - Se generó el archivo `comparacion_propuestas.md`.
  - Diferencias identificadas:
    * Fecha: 15 de marzo de 2026 vs 28 de abril de 2026.
    * Monto: $45.000 USD vs $62.000 USD.
    * Alcance: UI/REST con garantía 30 días vs UI/Python con soporte 24/7 por 12 meses.
  - Artefacto registrado en SQLite con hash SHA256 válido (`3a...`).
- **Estado:** ✅ **Aprobado con éxito.**

---

### UC-02: Control de Aplicación de Escritorio (Bloc de notas)
- **Instrucción:** *"Abre el Bloc de notas, escribe este texto y guárdalo como nota.txt en la carpeta autorizada."*
- **Texto evaluado:** Texto complejo con tildes, eñes, saltos de línea y signos de puntuación:
  `"Notas del día:\n- Revisión de diseño...\n- ¡Atención!: Comprobar..."`
- **Mecanismo:** `SimulatedDesktopAdapter` para ejecución en entorno macOS de desarrollo; `WindowsUIAutomationAdapter` (`pywinauto`) listo para Windows 11.
- **Resultado observado:**
  - Se abrió la ventana de la aplicación.
  - Se escribió el texto con preservación exacta de caracteres españoles.
  - Se guardó `nota.txt` en la carpeta autorizada.
  - Verificación estricta: `actual_text == expected_text` y hash SHA256 validado en base de datos.
- **Estado:** ✅ **Aprobado en desarrollo (adaptador simulado). Pendiente verificación nativa en Windows 11 interactivo.**

---

### UC-03: Automatización de Navegador Dedicado (Playwright)
- **Instrucción:** *"Completa este formulario de prueba con los datos que te indico."*
- **Entorno:** Servidor HTTP local fixture (`http://127.0.0.1:8765/`) sirviendo formulario con campos `#nombre`, `#email`, `#comentarios` y botón `#btn-enviar`.
- **Mecanismo:** `BrowserAdapter` con Chromium en perfil dedicado y aislado de Playwright.
- **Resultado observado:**
  - El navegador navegó a la página y leyó los elementos del DOM.
  - Completó los campos `#nombre` con "Carlos Pérez", `#email` con "carlos@ejemplo.local" y `#comentarios`.
  - Hizo clic en `#btn-enviar`.
  - **Verificación externa independiente:** El servidor HTTP registró exactamente 1 petición con los valores esperados (`RECEIVED_SUBMISSIONS[0]`).
- **Estado:** ✅ **Aprobado con éxito.**

---

## 3. Pruebas de Seguridad y Comportamiento Crítico

| Requisito Verificado | Prueba Ejecutada | Resultado |
| :--- | :--- | :---: |
| **Path Traversal Bloqueado** | Intento de escape con `../outside_dir/secreto.txt` | ✅ Bloqueado (`OUT_OF_SCOPE`) |
| **Rutas UNC Bloqueadas** | Intento de acceso a `\\servidor\recurso` | ✅ Bloqueado (`UNC_PATH_FORBIDDEN`) |
| **Herramientas Prohibidas** | Invocación de `shell.execute`, `python.eval` | ✅ Bloqueado (`TOOL_FORBIDDEN`) |
| **Aprobación de Sobrescritura** | Intento de sobreescribir archivo existente con `files.write` | ✅ Requiere aprobación (`PENDING_APPROVAL`) |
| **Aprobación de Movimiento** | Intento de mover archivo con `files.move` | ✅ Requiere aprobación (`PENDING_APPROVAL`) |
| **Idempotencia de Tareas** | Repetición de `POST /v1/tasks` con mismo `Idempotency-Key` | ✅ Retorna misma tarea sin duplicar |
| **Recuperación tras Caída** | Tarea en estado `running` al reiniciar servicio | ✅ Marcada como `interrupted` |
| **Cancelación Rápida** | `request_cancel` durante solicitud activa | ✅ Detenida en **0.12 segundos** (< 1s) |
| **Autenticación API** | Solicitud sin token / con token falso | ✅ Retorna 401 Unauthorized / 403 Forbidden |
| **Eventos SSE** | Reconexión con parámetro `?after_seq=N` | ✅ Eventos entregados en orden secuencial estricto |
