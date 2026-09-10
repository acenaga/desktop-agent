# Registro de Decisiones de Arquitectura y Supuestos (ADRs) - LocalDesk

**Versión:** 1.0  
**Fecha:** 9 de septiembre de 2026  
**Producto:** LocalDesk

---

## ADR-001: Arquitectura de Puertos y Adaptadores (Hexagonal) y Aislamiento de Plataforma

### Contexto
El objetivo principal del MVP es operar sobre **Windows 11 x64** con control nativo de aplicaciones (caso UC-02: Bloc de notas mediante UI Automation). Sin embargo, el desarrollo y pruebas automatizadas pueden realizarse en otros entornos (por ejemplo, macOS Darwin en estaciones de desarrollo o Linux en integración continua). Adicionalmente, el núcleo debe funcionar de manera 100% autónoma sin depender de Tauri, React o Laravel.

### Decisión
1. Se adopta una arquitectura de puertos y adaptadores. El núcleo (`local_agent.core.engine.AgentCore`) interactúa exclusivamente a través de interfaces tipadas:
   - `ModelProvider`: Proveedor de inferencia.
   - `DesktopAdapterInterface`: Control de ventanas y controles del sistema operativo.
   - `BrowserAdapterInterface`: Automatización del navegador.
   - `FileAdapterInterface`: Manipulación y extracción de documentos.
   - `RepositoryInterface`: Persistencia de tareas, eventos y aprobaciones.
2. Para el escritorio:
   - Se implementa `WindowsUIAutomationAdapter` basado en `pywinauto` para Windows 11.
   - Se implementa `SimulatedDesktopAdapter` / `MockDesktopAdapter` para permitir ejecutar la suite de pruebas completa en macOS y Linux sin fallos de importación.
   - Las dependencias de `pywinauto` se configuran como condicionales (`sys_platform == 'win32'`).
3. Se documenta explícitamente en `docs/limitations.md` y en los reportes de pruebas que las pruebas con adaptador simulado no sustituyen la verificación en un Windows 11 real interactivo.

---

## ADR-002: Inferencia Estrictamente Local y Rechazo de Proxies/Nube

### Contexto
El requisito de privacidad prohíbe terminantemente la inferencia remota, el envío de telemetría y el uso de servicios en la nube en el MVP. La inferencia debe ser servida por una instancia local de Ollama.

### Decisión
1. El proveedor de inferencia por defecto es `OllamaProvider` apuntando a `http://127.0.0.1:11434`.
2. Se verifica que el modelo provenga de la instancia local comprobando `OLLAMA_NO_CLOUD=1` o verificando que no existan redirecciones a proxies remotos.
3. Se rechaza cualquier configuración que intente fallback silencioso a APIs de terceros (OpenAI, Anthropic, Ollama Cloud). Si Ollama no está disponible o el modelo no existe, la tarea falla explícitamente con un código tipado de error (`MODEL_UNAVAILABLE`).
4. Para pruebas automatizadas de regresión y CI se implementa `FakeModelProvider`, el cual emula respuestas estructuradas válidas y llamadas a herramientas sin requerir GPUs ni modelos de varios gigabytes descargados.

---

## ADR-003: Ciclo de Tarea, FSM de Estados y Cancelación en < 1 Segundo

### Contexto
El sistema debe permitir pausar, reanudar y detener tareas en cualquier momento, con una garantía de respuesta de cancelación en menos de 1 segundo para evitar que se ejecuten acciones no deseadas sobre el sistema de archivos o la interfaz.

### Decisión
1. Se define una máquina de estados finitos (FSM) estricta:
   `queued` -> `running` -> (`awaiting_approval` | `awaiting_input` | `paused` | `cancelling`) -> (`completed` | `failed` | `cancelled` | `interrupted`).
2. Cada tarea posee un `CancellationToken` asíncrono.
3. El bucle de ejecución evalúa el token de cancelación:
   - Antes de solicitar inferencia al modelo.
   - Entre la recepción de la propuesta y la evaluación de la política.
   - Inmediatamente antes de invocar cualquier herramienta con efectos secundarios.
   - Después de la ejecución de cada herramienta.
4. Las llamadas potencialmente bloqueantes se aíslan en hilos/workers con timeouts estrictos (15s para herramientas ordinarias, 120s para el modelo).

---

## ADR-004: Modelo de Seguridad y PolicyEngine de Cero Confianza en el Modelo

### Contexto
El modelo de lenguaje propone acciones y argumentos, pero no tiene autoridad para auto-concederse permisos, ampliar alcances ni omitir verificaciones de seguridad. El contenido extraído de archivos o páginas web debe ser tratado estrictamente como datos no ejecutables.

### Decisión
1. Cada tarea se crea con un `TaskScope` explícito que define:
   - `read_roots`: Carpetas canónicas autorizadas para lectura.
   - `write_roots`: Carpetas canónicas autorizadas para salida.
   - `allowed_apps`: Lista blanca de ejecutables/aplicaciones autorizadas.
   - `allowed_domains`: Dominios web permitidos en el perfil de red.
2. `PolicyEngine` canóniza todas las rutas en el sistema de archivos resolviendo enlaces simbólicos y carpetas junction de Windows para prevenir path traversal (`../`) o fugas de scope.
3. Se clasifican las operaciones:
   - **Lectura/Idempotente autorizada**: Ejecución directa dentro del scope.
   - **Escritura nueva autorizada en output**: Ejecución atómica y verificación posterior.
   - **Sobrescritura o movimiento de archivos**: Requiere aprobación interactiva del usuario (`awaiting_approval`).
   - **Acciones fuera de alcance o prohibidas**: Bloqueo absoluto.
4. Las aprobaciones son de un solo uso, tienen hash del contenido exacto y vencen si cambia el contexto.

---

## ADR-005: Persistencia SQLite Serializada y Event Sourcing de Tareas

### Contexto
La aplicación debe persistir el historial completo, estados, evidencias y preferencias locales, soportando recuperación tras cierres inesperados.

### Decisión
1. Se utiliza SQLite local (`local_agent.db`) gestionado mediante `aiosqlite`.
2. Se definen tablas normalizadas:
   - `tasks`: Metadatos, estado actual, instrucción, scope asignado.
   - `task_events`: Historial inmutable ordenado de eventos emitidos (SSE friendly).
   - `actions`: Propuestas de herramientas, argumentos canónicos, evidencias y resultados.
   - `approvals`: Solicitudes de aprobación con token único, estado y expiración.
   - `artifacts`: Archivos generados verificados con hash sha256 y tamaño.
   - `scopes`: Definiciones de carpetas y permisos asignados por el usuario.
   - `user_preferences`: Configuraciones editables del usuario.
3. Al iniciar el servicio, cualquier tarea en estado `running` o `cancelling` se transiciona automáticamente a `interrupted`.

---

## ADR-006: Protocolo de Comunicación Servicio-Host y FastAPI en Loopback

### Contexto
La interfaz gráfica (Tauri 2 + React) y clientes locales autorizados (por ejemplo, scripts o Laravel) deben comunicarse con el servicio Python de forma segura y sin exponer puertos a la red local.

### Decisión
1. FastAPI se enlaza exclusivamente a `127.0.0.1` (IPv4 loopback) en un puerto efímero asignado por el sistema operativo (`bind_port: 0`).
2. Se genera un token de sesión criptográfico (`session_token`) que se pasa al proceso Python mediante argumento/variable de entorno de arranque.
3. Cada solicitud HTTP a `/v1/*` requiere el encabezado `Authorization: Bearer <session_token>`.
4. CORS está restringido a orígenes locales autorizados.
5. Se incluye soporte para Server-Sent Events (SSE) en `/v1/tasks/{task_id}/events` para actualización en tiempo real de la UI.
