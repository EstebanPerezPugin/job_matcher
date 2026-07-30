import http.server
import socketserver
import json
import subprocess
import os
from pathlib import Path

PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"

class JobAgentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Mapear rutas relativas al directorio raíz o web/
        if path == "/" or path == "/index.html":
            return str(WEB_DIR / "index.html")
        elif path.startswith("/web/"):
            return str(BASE_DIR / path.lstrip("/"))
        elif path.startswith("/data/"):
            return str(BASE_DIR / path.lstrip("/"))
        return super().translate_path(path)

    def do_POST(self):
        if self.path == "/api/refresh":
            print("[Server] Petición recibida para ejecutar nueva búsqueda en LinkedIn...")
            try:
                # Leer payload si viene con datos
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
                    data = json.loads(body.decode('utf-8'))
                    
                    # Si enviaron postulaciones o perfil actualizado desde el navegador, guardarlo primero
                    if "applied" in data:
                        with open(DATA_DIR / "applied.json", "w", encoding="utf-8") as f:
                            json.dump(data["applied"], f, ensure_ascii=False, indent=2)
                    if "profile" in data:
                        with open(DATA_DIR / "profile.json", "w", encoding="utf-8") as f:
                            json.dump(data["profile"], f, ensure_ascii=False, indent=2)

                # Ejecutar script del agente Python
                result = subprocess.run(
                    [sys.executable, str(BASE_DIR / "src" / "agent" / "main.py")],
                    capture_output=True,
                    text=True
                )

                # Cargar empleos actualizados
                jobs_path = DATA_DIR / "jobs.json"
                jobs = []
                if jobs_path.exists():
                    with open(jobs_path, "r", encoding="utf-8") as f:
                        jobs = json.load(f)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                response = {
                    "success": True,
                    "message": "Búsqueda completada exitosamente",
                    "jobs": jobs,
                    "output": result.stdout
                }
                self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

            except Exception as e:
                print(f"[Server] Error ejecutando agente: {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))
        else:
            self.send_error(404, "Endpoint no encontrado")

if __name__ == "__main__":
    import sys
    os.chdir(str(BASE_DIR))
    handler = JobAgentHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print("=" * 65)
        print(f"🚀 Dashboard Servidor en ejecución en: http://localhost:{PORT}")
        print("   Presiona Ctrl+C para detener el servidor.")
        print("=" * 65)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Servidor detenido.")
