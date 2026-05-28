# Lanzador sin ventana de consola (.pyw -> pythonw). Para el acceso directo del escritorio.
# Arranca el servidor local y abre el navegador. El log va a un archivo, no a pantalla.
import os
import sys
from pathlib import Path

AQUI = Path(__file__).parent
os.chdir(AQUI)
sys.path.insert(0, str(AQUI))

# Redirigir salida a un log (pythonw no tiene consola; sin esto, un print crashea)
log = open(AQUI / "transcriptor.log", "w", encoding="utf-8", errors="replace")
sys.stdout = sys.stderr = log

# Si ya hay una instancia corriendo en el puerto, solo abrir el navegador y salir.
import socket  # noqa: E402
import webbrowser  # noqa: E402

PORT = int(os.environ.get("TRANSCRIPTOR_PORT", "8731"))
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(0.5)
    ya_corriendo = s.connect_ex(("127.0.0.1", PORT)) == 0

if ya_corriendo:
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    sys.exit(0)

import run  # noqa: E402
run.main()
