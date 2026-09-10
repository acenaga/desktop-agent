# Contrato de API y Guía de Integración - LocalDesk v1

**Versión:** 1.0  
**Prefijo base:** `/v1`  
**Host por defecto:** `http://127.0.0.1:8000` (Loopback IPv4 estricto)

---

## 1. Principios de Seguridad y Autenticación

1. **Enlace a Loopback**: El servicio FastAPI solo escucha en `127.0.0.1` o sockets locales asignados por el sistema operativo. No se expone a interfaces de red externas.
2. **Autenticación por Token**: Todas las peticiones deben incluir el encabezado HTTP:
   ```http
   Authorization: Bearer <SESSION_TOKEN>
   ```
   El token de sesión es un secreto criptográfico aleatorio generado en el arranque y comunicado de forma privada al cliente local o host de Tauri.
3. **Idempotencia**: Las operaciones de creación de tareas soportan el encabezado `Idempotency-Key: <clave-única>`. Enviar la misma clave garantiza que no se duplicará la tarea y devolverá la misma instancia creada.

---

## 2. Catálogo de Endpoints

### 2.1 Salud y Capacidades

#### `GET /v1/health`
Verifica el estado del servicio, la disponibilidad del modelo local en Ollama y el adaptador de escritorio activo.

**Respuesta (200 OK):**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "os_platform": "Darwin",
  "inference_available": true,
  "model_id": "qwen2.5:14b",
  "desktop_adapter": "windows_uia",
  "active_tasks_count": 0
}
```

#### `GET /v1/models`
Lista los modelos locales instalados en Ollama y sus capacidades técnicas verificadas.

**Respuesta (200 OK):**
```json
{
  "models": [
    {
      "name": "qwen2.5:14b",
      "supports_tools": true,
      "supports_vision": false,
      "context_length": 8192,
      "quantization": "Q4_K_M",
      "tested": true,
      "is_simulation": false
    }
  ]
}
```

---

### 2.2 Gestión de Tareas

#### `POST /v1/tasks`
Crea una nueva tarea para ejecución dentro de un alcance autorizado.

**Headers:**
- `Authorization: Bearer <TOKEN>`
- `Idempotency-Key: <JOB-UUID>` (Opcional, recomendado)

**Cuerpo de la Solicitud:**
```json
{
  "instruction": "Compara las dos propuestas de desarrollo y guarda las diferencias en mi carpeta de salida.",
  "scope_id": "scope_uc01",
  "input_refs": [
    "fixtures/uc01/propuesta_alfa.md",
    "fixtures/uc01/propuesta_beta.docx"
  ],
  "output_name": "comparacion.md"
}
```

**Respuesta (201 Created):**
```json
{
  "task_id": "task_4f89a2b10c9d",
  "state": "queued",
  "instruction": "Compara las dos propuestas de desarrollo y guarda las diferencias en mi carpeta de salida.",
  "scope_id": "scope_uc01",
  "created_at": "2026-09-09T18:00:00Z"
}
```

#### `GET /v1/tasks/{task_id}`
Consulta el detalle completo, estado actual, acciones ejecutadas y artefactos verificados de la tarea.

**Respuesta (200 OK):**
```json
{
  "task": {
    "task_id": "task_4f89a2b10c9d",
    "instruction": "Compara las dos propuestas...",
    "state": "completed",
    "scope_id": "scope_uc01",
    "steps_count": 3,
    "active_duration_seconds": 4.2,
    "created_at": "2026-09-09T18:00:00Z",
    "completed_at": "2026-09-09T18:00:04Z"
  },
  "actions": [
    {
      "action_id": "act_8820c01",
      "tool": "files.read",
      "state": "completed",
      "brief_reason": "Leer propuesta Alfa",
      "expected_result": "Contenido de propuesta_alfa.md"
    }
  ],
  "artifacts": [
    {
      "artifact_id": "art_19002a",
      "file_name": "comparacion.md",
      "file_path": "/Users/usuario/salida/comparacion.md",
      "size_bytes": 1420,
      "sha256": "3a88c...b20f"
    }
  ]
}
```

#### `GET /v1/tasks/{task_id}/events`
Stream de eventos en tiempo real mediante **Server-Sent Events (SSE)**.
Permite reconexión indicando el parámetro `?after_seq=N`.

**Ejemplo de Eventos Emitidos:**
```
event: task_state_changed
data: {"event_id": "evt_01", "task_id": "task_4f89a2b10c9d", "sequence": 1, "payload": {"state": "running"}}

event: task_plan_explained
data: {"event_id": "evt_02", "task_id": "task_4f89a2b10c9d", "sequence": 2, "payload": {"plan": "Iniciando lectura..."}}

event: action_started
data: {"event_id": "evt_03", "task_id": "task_4f89a2b10c9d", "sequence": 3, "payload": {"action_id": "act_01", "tool": "files.read"}}

event: task_completed
data: {"event_id": "evt_04", "task_id": "task_4f89a2b10c9d", "sequence": 4, "payload": {"result": "Tarea completada"}}
```

---

### 2.3 Control Interactivo de Ejecución

- `POST /v1/tasks/{task_id}/pause`: Pausa la ejecución de la tarea activa.
- `POST /v1/tasks/{task_id}/resume`: Reanuda la tarea pausada.
- `POST /v1/tasks/{task_id}/cancel`: Detiene de forma inmediata la tarea (< 1s).
- `POST /v1/tasks/{task_id}/approvals/{approval_id}`:
  Resuelve una solicitud de aprobación sensible:
  ```json
  { "approved": true }
  ```

---

## 3. Integración con Clientes Externos

### 3.1 Integración desde PHP / Laravel

Un servidor local o proceso de Laravel en el mismo equipo puede invocar al agente usando Guzzle o cURL estándar:

```php
$client = new \GuzzleHttp\Client(['base_uri' => 'http://127.0.0.1:8000']);
$response = $client->post('/v1/tasks', [
    'headers' => [
        'Authorization' => 'Bearer ' . env('LOCALDESK_SESSION_TOKEN'),
        'Idempotency-Key' => 'laravel-job-' . Str::uuid(),
    ],
    'json' => [
        'instruction' => 'Generar reporte de métricas locales',
        'scope_id' => 'scope_informes',
        'output_name' => 'metricas.md',
    ]
]);

$task = json_decode($response->getBody(), true);
$taskId = $task['task_id'];
```
Ver script completo en: `scripts/client_example.php`.

### 3.2 Integración desde Python

```python
import httpx

with httpx.Client(base_url="http://127.0.0.1:8000", headers={"Authorization": f"Bearer {token}"}) as client:
    res = client.post("/v1/tasks", json={
        "instruction": "Compara las dos propuestas",
        "scope_id": "scope_uc01",
        "output_name": "comparacion.md"
    })
    task_id = res.json()["task_id"]
```
Ver script completo en: `scripts/client_example.py`.
