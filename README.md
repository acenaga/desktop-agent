# LocalDesk - Agente de Escritorio con IA Local

**Versión:** 0.1.0  
**Idioma:** Español  
**Objetivo:** Permitir a una persona delegar tareas operativas en lenguaje natural (español) utilizando modelos locales (Ollama), archivos, aplicaciones de escritorio y navegador, garantizando privacidad total (cero nube) y control explícito de permisos.

---

## 1. Características Principales

- 🧠 **Inferencia 100% Local**: Conexión exclusiva a Ollama local (`127.0.0.1:11434`). Sin telemetría remota ni almacenamiento en la nube.
- 🛡️ **Seguridad de Cero Confianza**: El motor de políticas (`PolicyEngine`) valida rutas canónicas (previene path traversal `../`, symlinks y junctions) y exige aprobación interactiva de un solo uso para acciones sensibles (sobrescritura o movimiento de archivos).
- ⏱️ **Garantía de Cancelación < 1s**: Interrupción inmediata de tareas mediante token asíncrono y atajo de emergencia `Ctrl+Alt+Esc`.
- 📁 **Gestión Avanzada de Documentos**: Extracción y comparación estructurada de archivos Markdown, TXT, PDF (`pypdf`) y DOCX (`python-docx`), conservando citas a fuentes.
- 🌐 **Navegador Aislado con Playwright**: Automatización de formularios y flujos web en un perfil dedicado sin cookies personales.
- 🖥️ **Control Nativo de Escritorio**: Automatización de aplicaciones de Windows mediante UI Automation (`pywinauto`) con soporte completo para tildes, eñes y caracteres en español.
- 🔌 **API REST Versionada (`/v1`) y Eventos SSE**: Servicio FastAPI local desacoplado, integrable con Laravel, PHP, Python y la interfaz de usuario en Tauri 2 + React.

---

## 2. Estructura del Repositorio

```
control-agent/
├── apps/
│   └── desktop/                  # Interfaz Tauri 2 + React 18 + TypeScript + Vite
├── python/
│   ├── src/local_agent/          # Paquete Python del agente
│   │   ├── domain/               # Entidades, FSM de estados y contratos Pydantic
│   │   ├── core/                 # AgentCore, ciclo ReAct, cola y excepciones
│   │   ├── policy/               # PolicyEngine, control de rutas y permisos
│   │   ├── providers/            # OllamaProvider y FakeModelProvider
│   │   ├── tools/                # Herramientas de archivos, escritorio y navegador
│   │   ├── storage/              # SQLite local, migraciones y repositorios
│   │   └── api/                  # FastAPI /v1, autenticación y streaming SSE
│   ├── tests/                    # 22 pruebas automatizadas (unitarias e integración)
│   ├── pyproject.toml            # Configuración del paquete
│   └── requirements.txt          # Dependencias fijadas
├── fixtures/                     # Documentos sintéticos UC-01 y servidor web UC-03
├── scripts/                      # Scripts de diagnóstico, fixtures, clientes y empaquetado
├── docs/                         # Documentación técnica completa
│   ├── architecture.md           # Arquitectura hexagonal y diagramas
│   ├── api.md                    # Contrato de la API y guía de integración
│   ├── openapi.json              # Especificación OpenAPI exportada
│   ├── testing.md                # Informe de pruebas y métricas
│   ├── decisions.md              # Registro de Decisiones de Arquitectura (ADRs)
│   └── limitations.md            # Limitaciones explícitas y pruebas nativas pendientes
└── config.default.yaml           # Configuración de referencia
```

---

## 3. Instalación y Puesta en Marcha

### Requisitos Previos
- Python 3.11+
- Node.js v20+ y npm
- [Ollama](https://ollama.com/) instalado en el equipo

### 3.1 Entorno Virtual de Python
```bash
# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r python/requirements.txt

# Instalar el paquete local_agent en modo editable (necesario para
# `python -m local_agent.cli`; sin este paso aparece
# "ModuleNotFoundError: No module named 'local_agent'")
pip install -e python

# Instalar navegador para Playwright
playwright install chromium
```

### 3.2 Diagnóstico del Entorno
Ejecuta el script de diagnóstico para verificar hardware, bibliotecas y estado de Ollama:
```bash
python scripts/diagnose_env.py
```

### 3.3 Descargar un Modelo Local en Ollama (Opcional)
Para tareas con lenguaje natural real:
```bash
ollama pull qwen2.5:14b  # Recomendado
# o una alternativa ligera:
ollama pull llama3.2:3b
```
*(Si no tienes un modelo descargado, el sistema incluye `FakeModelProvider` para ejecutar todas las pruebas y demostraciones de inmediato sin descargas).*

---

## 4. Ejecución de Pruebas Automatizadas

Ejecuta la suite completa de 22 pruebas (seguridad, persistencia, ciclo ReAct, UC-01, UC-02, UC-03 y API):
```bash
pytest python/tests
```

> **Nota:** la prueba UC-03 lanza un navegador real, por lo que requiere que el
> binario de Chromium esté descargado (paso `playwright install chromium` de la
> sección 3.1). Instalar `playwright` con `pip` **no** descarga el navegador. Si
> falta, la prueba falla con `BrowserType.launch: Executable doesn't exist at ...`;
> basta con ejecutar:
>
> ```bash
> playwright install chromium
> ```
>
> Este paso también debe repetirse en cualquier máquina nueva o entorno de CI.

---

## 5. Uso y Operación

### 5.1 Iniciar el Servicio FastAPI Headless
```bash
# Iniciar servicio con token de sesión
python -m local_agent.cli serve --host 127.0.0.1 --port 8000 --token mi-secreto-local --print-token
```

### 5.2 Iniciar la Interfaz de Escritorio (Modo Desarrollo)
```bash
cd apps/desktop
npm install
npm run dev
```
Abre en el navegador `http://localhost:5173` para interactuar con la interfaz completa (Inicio, Ejecución en tiempo real con SSE, Historial y Configuración).

Las **carpetas de lectura y escritura** del agente se configuran en *Configuración → Alcances y Carpetas Autorizadas* (una ruta absoluta y existente por línea). La sección `permissions` del YAML solo se usa para crear el alcance por defecto en el primer arranque; después manda lo guardado desde la interfaz.

### 5.3 Ejecución Directa por Línea de Comandos (CLI)
```bash
# Generar fixtures de prueba si no existen
python scripts/generate_uc01_fixtures.py

# Ejecutar tarea de comparación UC-01
python -m local_agent.cli run \
  --instruction "Compara las dos propuestas y guarda las diferencias." \
  --scope-read fixtures/uc01 \
  --scope-write . \
  --input-refs fixtures/uc01/propuesta_alfa.md fixtures/uc01/propuesta_beta.docx \
  --output-name comparacion_cli.md \
  --fake
```

### 5.4 Clientes de Integración (PHP / Laravel y Python)
- **Cliente Python:** `python scripts/client_example.py`
- **Cliente PHP / Laravel:** `php scripts/client_example.php`

---

## 6. Documentación Adicional

- [Arquitectura del Sistema](docs/architecture.md)
- [Contrato de API y Guía de Integración](docs/api.md)
- [Informe de Pruebas](docs/testing.md)
- [Registro de Decisiones (ADRs)](docs/decisions.md)
- [Limitaciones Explícitas y Pruebas Pendientes](docs/limitations.md)
