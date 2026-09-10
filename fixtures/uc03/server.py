"""
fixtures/uc03/server.py: Servidor HTTP local para la prueba de formulario UC-03.
Sirve un formulario HTML y registra las peticiones recibidas para verificación independiente.
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading


FORM_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Formulario de Prueba LocalDesk (UC-03)</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background: #f5f5f5; }
        .card { background: white; padding: 24px; border-radius: 8px; max-width: 500px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .field { margin-bottom: 16px; }
        label { display: block; font-weight: bold; margin-bottom: 6px; }
        input, textarea { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background: #0066cc; color: white; border: none; padding: 10px 18px; border-radius: 4px; cursor: pointer; }
        .success { color: #008800; font-weight: bold; margin-top: 16px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Registro de Prueba</h2>
        <form id="formulario-registro" action="/submit" method="POST">
            <div class="field">
                <label for="nombre">Nombre Completo:</label>
                <input type="text" id="nombre" name="nombre" placeholder="Ingresa tu nombre" required>
            </div>
            <div class="field">
                <label for="email">Correo Electrónico:</label>
                <input type="email" id="email" name="email" placeholder="usuario@ejemplo.local" required>
            </div>
            <div class="field">
                <label for="comentarios">Comentarios:</label>
                <textarea id="comentarios" name="comentarios" rows="3"></textarea>
            </div>
            <button type="submit" id="btn-enviar">Enviar Registro</button>
        </form>
    </div>
</body>
</html>
"""

SUCCESS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Confirmación</title>
</head>
<body>
    <div id="mensaje-exito" style="color: green; font-weight: bold;">
        Formulario recibido correctamente para {nombre} ({email})
    </div>
    <div id="datos-recibidos">{comentarios}</div>
</body>
</html>
"""

# Almacén en memoria de envíos recibidos por el servidor
RECEIVED_SUBMISSIONS = []


class FormHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silenciar logs en tests

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(FORM_HTML.encode("utf-8"))
        elif parsed.path == "/submissions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(RECEIVED_SUBMISSIONS).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/submit":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            form_data = parse_qs(body)

            nombre = form_data.get("nombre", [""])[0]
            email = form_data.get("email", [""])[0]
            comentarios = form_data.get("comentarios", [""])[0]

            record = {"nombre": nombre, "email": email, "comentarios": comentarios}
            RECEIVED_SUBMISSIONS.append(record)

            html = SUCCESS_HTML_TEMPLATE.format(nombre=nombre, email=email, comentarios=comentarios)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class LocalFormServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        global RECEIVED_SUBMISSIONS
        RECEIVED_SUBMISSIONS.clear()
        self.server = HTTPServer((self.host, self.port), FormHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            if self.thread:
                self.thread.join(timeout=2)


if __name__ == "__main__":
    s = LocalFormServer()
    s.start()
    print(f"Servidor de prueba UC-03 ejecutándose en http://127.0.0.1:8765")
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        s.stop()
