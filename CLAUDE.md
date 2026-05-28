# transcriptor — app web local de audio → texto

Herramienta propia (JRAM). Transcribe audio con faster-whisper en GPU, servida como web
local (FastAPI). El usuario arrastra un audio, elige carpeta destino, ve progreso y consumo
de GPU/CPU en vivo, y descarga el `.txt`.

## Nivel DevSecOps: **L2** (repo público — github.com/c0hete/transcriptor)

Ver `SECURITY.md`. Lo crítico: **audios y transcripciones son datos del usuario y están
gitignored** — solo se versiona código. CI con gitleaks (bloquea) + ruff.

## Stack y arquitectura

- `app/engine.py` — motor: carga el modelo una vez, transcribe en streaming. Incluye
  `cargar_dlls_cuda()` (fix del namespace package nvidia), fallback cuda→cpu, y escritura
  tolerante a fallo parcial.
- `app/monitor.py` — métricas GPU (`nvidia-smi`) + CPU/RAM (`psutil`).
- `app/server.py` — FastAPI: endpoints `/api/*` + sirve la UI estática.
- `app/static/index.html` — UI completa (HTML+CSS+JS, sin frameworks).
- `run.py` / `transcriptor.bat` — lanzador (carga `.env`, abre el navegador).

## Apagado del servidor (no dejar zombies)

El lanzador silencioso (`run_silencioso.pyw` / acceso directo del Desktop) corre sin consola,
así que no hay ventana que cerrar. Tres mecanismos cubren que no queden servidores andando:

1. **Botón "⏻ Apagar"** en la UI → `POST /api/apagar` → mata el proceso (bloquea si hay
   trabajos activos).
2. **Autoapagado por inactividad** (`TRANSCRIPTOR_INACTIVIDAD_MIN`, default 20 min): un hilo
   guardián apaga el proceso si pasa ese tiempo sin requests del navegador Y no hay trabajos
   activos. 0 = nunca.
3. **Anti-duplicado:** `run_silencioso.pyw` chequea el puerto antes de arrancar; si ya hay una
   instancia, solo abre el navegador y sale (no levanta un segundo server).

⚠️ **Apagado en Windows:** `os.kill(getpid(), SIGINT)` sobre uno mismo NO baja uvicorn de forma
fiable en Windows. Por eso `_apagar_proceso()` intenta SIGINT y luego fuerza `os._exit(0)`.

## Gotchas

- **CUDA en Windows:** ctranslate2 necesita `cublas64_12.dll` + cuDNN de los pips
  `nvidia-*-cu12`. El paquete `nvidia` es namespace package (`__file__` = None) → resolver por
  `find_spec(...).submodule_search_locations`. Si no, escribe `.txt` vacíos sin avisar claro.
- **Encoding:** nunca volcar el texto transcrito a stdout en Windows (cp1252 crashea con
  caracteres no-latin). Por eso el motor escribe al archivo, no a consola. `run.py` fuerza
  stdout a UTF-8 igual.
- **VRAM 8 GB:** el motor procesa **un trabajo a la vez** (lock). `large-v3` entra cómodo.

## Origen

Consolida el flujo manual de `c:\CODIGO\transcripciones\INACAP\_transcribir_inacap.py`
(script GPU validado). Misma receta de motor, ahora con interfaz.
