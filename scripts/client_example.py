#!/usr/bin/env python3
"""
scripts/client_example.py: Ejemplo de cliente Python autorizado para LocalDesk API /v1.
Demuestra:
- Autenticación con Bearer token.
- Creación de tarea con Idempotency-Key.
- Consulta de progreso y artefactos generados.
"""

import os
import sys
import time
import httpx

API_BASE = os.getenv("LOCALDESK_API_BASE", "http://127.0.0.1:8000")
SESSION_TOKEN = os.getenv("LOCALDESK_SESSION_TOKEN", "test-secret-token")


def main():
    print("=" * 60)
    print(" CLIENTE DE INTEGRACIÓN PYTHON - LocalDesk API /v1")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {SESSION_TOKEN}",
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=API_BASE, headers=headers, timeout=10.0) as client:
        # 1. Comprobar salud del servicio
        try:
            health = client.get("/v1/health")
            if health.status_code != 200:
                print(f"[!] Error al conectar: {health.status_code} - {health.text}")
                return
            print(f"[+] Conexión establecida. Estado: {health.json()}")
        except Exception as e:
            print(f"[!] Error de conexión: {e}")
            print("Asegúrate de haber iniciado el servicio con: python -m local_agent.cli serve --token test-secret-token")
            return

        # 2. Consultar alcances disponibles
        scopes_res = client.get("/v1/scopes")
        scopes = scopes_res.json()
        scope_id = scopes[0]["scope_id"] if scopes else "default_scope"

        # 3. Crear una tarea con Idempotency-Key
        idem_key = f"python-client-job-{int(time.time())}"
        payload = {
            "instruction": "Compara las propuestas de desarrollo en mi carpeta autorizada.",
            "scope_id": scope_id,
            "input_refs": ["fixtures/uc01/propuesta_alfa.md", "fixtures/uc01/propuesta_beta.docx"],
            "output_name": "comparacion.md",
        }

        print(f"\n[+] Enviando tarea con Idempotency-Key: {idem_key}")
        task_res = client.post("/v1/tasks", json=payload, headers={"Idempotency-Key": idem_key})
        task_data = task_res.json()
        task_id = task_data["task_id"]
        print(f"[+] Tarea creada con ID: {task_id}, Estado inicial: {task_data['state']}")

        # 4. Polling de estado hasta finalización
        print("[+] Esperando resolución de la tarea...")
        for _ in range(30):
            res = client.get(f"/v1/tasks/{task_id}")
            detail = res.json()
            state = detail["task"]["state"]
            print(f"  - Estado actual: {state} (Pasos: {detail['task']['steps_count']})")
            if state in ("completed", "failed", "cancelled", "interrupted"):
                print(f"\n[+] Tarea finalizada con estado: {state}")
                if detail["artifacts"]:
                    print("[+] Artefactos producidos:")
                    for a in detail["artifacts"]:
                        print(f"    * {a['file_name']} ({a['size_bytes']} bytes, SHA256: {a['sha256'][:12]}...)")
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
