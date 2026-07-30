import http.server
import socketserver
import json
import subprocess
import sys
import os
from pathlib import Path

PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"

class JobAgentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        """Mapear rutas al directorio correcto."""
        # Normalizar la ruta quitando query strings
        path = path.split('?')[0].split('#')[0]

        # La raíz y /index.html -> web/index.html
        if path in ('/', '/index.html'):
            return str(WEB_DIR / 'index.html')

        # Archivos de la API -> no mapear a archivos
        if path.startswith('/api/'):
            return path

        # /data/... -> data/
        if path.startswith('/data/'):
            return str(DATA_DIR / path[6:])

        # Todo lo demás busca primero en web/, luego en raíz
        local = path.lstrip('/')
        candidate = WEB_DIR / local
        if candidate.exists():
            return str(candidate)
        return str(BASE_DIR / local)

    def log_message(self, format, *args):
        print(f"[Server] {self.address_string()} - {format % args}")

    def do_GET(self):
        """Manejar peticiones GET normales."""
        super().do_GET()

    def do_POST(self):
        """Manejar peticiones POST de la API."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = {}
        if content_length > 0:
            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode('utf-8'))
            except Exception:
                body = {}

        # Guardar datos enviados desde el frontend
        if "applied" in body:
            with open(DATA_DIR / "applied.json", "w", encoding="utf-8") as f:
                json.dump(body["applied"], f, ensure_ascii=False, indent=2)

        if "profile" in body:
            with open(DATA_DIR / "profile.json", "w", encoding="utf-8") as f:
                json.dump(body["profile"], f, ensure_ascii=False, indent=2)

        if self.path == "/api/refresh":
            self._handle_refresh()

        elif self.path == "/api/sync-applied":
            self._handle_sync_applied()

        else:
            self.send_error(404, "Endpoint no encontrado")

    def _handle_refresh(self):
        """Ejecuta el agente para buscar nuevas vacantes en LinkedIn."""
        print("[Server] ▶ Iniciando búsqueda de nuevas vacantes en LinkedIn...")
        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "src" / "agent" / "main.py")],
                capture_output=True, text=True, cwd=str(BASE_DIR)
            )

            jobs = self._load_json(DATA_DIR / "jobs.json")
            applied = self._load_json(DATA_DIR / "applied.json")

            self._json_response(200, {
                "success": True,
                "message": f"Búsqueda completada. {len(jobs)} empleos procesados.",
                "jobs": jobs,
                "applied": applied,
                "stdout": result.stdout[-2000:] if result.stdout else ""
            })

        except Exception as e:
            self._json_response(500, {"success": False, "error": str(e)})

    def _handle_sync_applied(self):
        """Ejecuta el scraper de postulaciones de LinkedIn Jobs Tracker."""
        print("[Server] ▶ Sincronizando postulaciones desde LinkedIn Jobs Tracker...")
        try:
            result = subprocess.run(
                [sys.executable, str(BASE_DIR / "src" / "agent" / "main.py"), "--sync-applied"],
                capture_output=True, text=True, cwd=str(BASE_DIR),
                timeout=60
            )

            applied = self._load_json(DATA_DIR / "applied.json")

            self._json_response(200, {
                "success": True,
                "message": f"Sincronización completada. {len(applied)} postulaciones encontradas.",
                "applied": applied,
                "stdout": result.stdout[-2000:] if result.stdout else ""
            })

        except subprocess.TimeoutExpired:
            self._json_response(200, {
                "success": False,
                "message": "La sincronización tardó demasiado. Puede que LinkedIn requiera más tiempo. Intenta de nuevo.",
                "applied": self._load_json(DATA_DIR / "applied.json")
            })
        except Exception as e:
            self._json_response(500, {"success": False, "error": str(e)})

    def _json_response(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _load_json(self, path: Path) -> list:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

if __name__ == "__main__":
    os.chdir(str(BASE_DIR))
    handler = JobAgentHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print("=" * 65)
        print(f"🚀 Dashboard disponible en: http://localhost:{PORT}")
        print("   Presiona Ctrl+C para detener el servidor.")
        print("=" * 65)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Servidor detenido.")
