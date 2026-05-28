# -*- coding: utf-8 -*-
"""transcriptor — servidor web local. Audio -> texto con faster-whisper en GPU.

Corre en 127.0.0.1 (solo tu máquina). Abrí http://127.0.0.1:8731 en el navegador.
"""
import os
import uuid
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import monitor
from .engine import Motor, Trabajo

# --- Config desde entorno (.env cargado por run.py) ---
MODELO = os.environ.get("WHISPER_MODEL", "large-v3")
DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
COMPUTE = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")
LANG = os.environ.get("WHISPER_LANGUAGE", "es")
SALIDA_BASE = os.environ.get("SALIDA_BASE", str(Path.home() / "transcripciones"))

EXT_AUDIO = {".opus", ".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".webm"}

app = FastAPI(title="transcriptor")
motor = Motor(modelo=MODELO, device=DEVICE, compute_type=COMPUTE, language=LANG)

# Registro en memoria de trabajos (id -> Trabajo)
TRABAJOS: dict[str, Trabajo] = {}
_tmpdir = Path(tempfile.gettempdir()) / "transcriptor_uploads"
_tmpdir.mkdir(exist_ok=True)


def _safe_dir(p: str) -> Path:
    """Valida una ruta de carpeta de destino (evita rutas vacías/archivos)."""
    if not p or not p.strip():
        raise HTTPException(400, "Ruta de destino vacía")
    path = Path(p).expanduser()
    if path.exists() and not path.is_dir():
        raise HTTPException(400, "La ruta existe y no es una carpeta")
    return path


@app.get("/api/config")
def config():
    return {
        "modelo": MODELO, "device_pedido": DEVICE,
        "device_real": motor.device_real, "salida_base": SALIDA_BASE,
        "extensiones": sorted(EXT_AUDIO),
    }


@app.get("/api/metrics")
def metrics():
    return monitor.todo()


@app.get("/api/listar-carpetas")
def listar_carpetas(base: str = SALIDA_BASE):
    """Lista subcarpetas de `base` para que la UI deje elegir destino."""
    b = Path(base).expanduser()
    if not b.exists():
        return {"base": str(b), "existe": False, "carpetas": []}
    carpetas = sorted([d.name for d in b.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))])
    return {"base": str(b), "existe": True, "carpetas": carpetas}


@app.post("/api/crear-carpeta")
def crear_carpeta(base: str = Form(...), nombre: str = Form(...)):
    """Crea una subcarpeta nueva dentro de `base`."""
    nombre = nombre.strip().strip("\\/")
    if not nombre or any(c in nombre for c in '<>:"|?*'):
        raise HTTPException(400, "Nombre de carpeta inválido")
    destino = _safe_dir(base) / nombre
    destino.mkdir(parents=True, exist_ok=True)
    return {"creada": str(destino)}


@app.post("/api/transcribir")
async def transcribir(audio: UploadFile = File(...), destino: str = Form(...)):
    """Recibe un audio + carpeta destino, lo encola y devuelve el id del trabajo."""
    ext = Path(audio.filename or "").suffix.lower()
    if ext not in EXT_AUDIO:
        raise HTTPException(400, f"Extensión no soportada: {ext}")
    carpeta = _safe_dir(destino)
    carpeta.mkdir(parents=True, exist_ok=True)

    tid = uuid.uuid4().hex[:12]
    tmp_path = _tmpdir / f"{tid}{ext}"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(audio.file, f)

    base = Path(audio.filename).stem
    salida = carpeta / f"{base}.txt"
    trab = Trabajo(id=tid, nombre=audio.filename, destino=str(carpeta), salida_path=str(salida))
    TRABAJOS[tid] = trab

    def _run():
        try:
            motor.transcribir(str(tmp_path), trab)
        finally:
            tmp_path.unlink(missing_ok=True)

    threading.Thread(target=_run, daemon=True).start()
    return {"id": tid}


@app.get("/api/trabajo/{tid}")
def estado_trabajo(tid: str):
    trab = TRABAJOS.get(tid)
    if not trab:
        raise HTTPException(404, "Trabajo no encontrado")
    return trab.snapshot()


@app.get("/api/trabajos")
def lista_trabajos():
    return [t.snapshot() for t in TRABAJOS.values()]


@app.post("/api/cancelar/{tid}")
def cancelar(tid: str):
    """Pide cancelar un trabajo. Si está transcribiendo, corta en el próximo segmento."""
    trab = TRABAJOS.get(tid)
    if not trab:
        raise HTTPException(404, "Trabajo no encontrado")
    if trab.estado in ("hecho", "error", "cancelado"):
        return {"ok": False, "motivo": "ya terminado", "estado": trab.estado}
    trab.pedir_cancelar()
    return {"ok": True}


@app.delete("/api/trabajo/{tid}")
def quitar_trabajo(tid: str):
    """Saca un trabajo de la lista (solo si ya no está activo)."""
    trab = TRABAJOS.get(tid)
    if not trab:
        raise HTTPException(404, "Trabajo no encontrado")
    if trab.estado in ("cargando", "transcribiendo"):
        raise HTTPException(409, "Cancelalo primero")
    TRABAJOS.pop(tid, None)
    return {"ok": True}


@app.get("/api/descargar/{tid}")
def descargar(tid: str):
    trab = TRABAJOS.get(tid)
    if not trab or trab.estado != "hecho":
        raise HTTPException(404, "Transcripción no lista")
    return FileResponse(trab.salida_path, filename=Path(trab.salida_path).name, media_type="text/plain")


# UI estática (montada al final para no tapar /api)
_static = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
