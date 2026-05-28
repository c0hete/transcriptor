# -*- coding: utf-8 -*-
"""Lanzador de transcriptor: carga .env, levanta el servidor y abre el navegador."""
import os
import sys
import threading
import webbrowser
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _cargar_env():
    """Carga .env simple (KEY=VALUE) sin dependencia externa."""
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for linea in env.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main():
    _cargar_env()
    host = os.environ.get("TRANSCRIPTOR_HOST", "127.0.0.1")
    port = int(os.environ.get("TRANSCRIPTOR_PORT", "8731"))
    url = f"http://{host}:{port}"

    print(f"transcriptor -> {url}  (Ctrl+C para detener)", flush=True)
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn
    uvicorn.run("app.server:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
