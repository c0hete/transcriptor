# transcriptor

App web local para transcribir audio a texto con [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
acelerada por GPU. Corre **100 % en tu máquina** (nada se sube a internet): levantás un
servidor local, lo abrís en el navegador, arrastrás un audio, elegís dónde guardar el `.txt`
y ves el progreso y el consumo de GPU/CPU en vivo.

## Por qué

Transcribir clases, reuniones o notas de voz sin depender de servicios en la nube (privacidad)
y aprovechando la GPU local en vez de esperar horas en CPU. Nació de un flujo manual con
scripts y se consolidó en una herramienta con interfaz.

## Stack

- **Motor:** faster-whisper sobre ctranslate2, modelo `large-v3` por defecto.
- **GPU:** CUDA 12 (cuBLAS + cuDNN vía pips `nvidia-*-cu12`). Fallback automático a CPU.
- **Web:** FastAPI + uvicorn, UI estática sin frameworks.
- **Monitoreo:** `nvidia-smi` (GPU) y `psutil` (CPU/RAM).

## Uso

```bash
pip install -r requirements.txt     # primera vez
cp .env.example .env                # ajustar si hace falta
python run.py                       # o doble clic a transcriptor.bat (Windows)
```

Abre solo `http://127.0.0.1:8731` en el navegador. El servidor **no escucha en red**, solo en
localhost.

## Configuración (`.env`)

| Variable | Default | Qué hace |
|----------|---------|----------|
| `WHISPER_MODEL` | `large-v3` | Modelo (tiny…large-v3). |
| `WHISPER_DEVICE` | `auto` | `cuda` / `cpu` / `auto` (intenta GPU, cae a CPU). |
| `WHISPER_LANGUAGE` | `es` | Idioma, o vacío para autodetectar. |
| `SALIDA_BASE` | — | Carpeta raíz sugerida para guardar transcripciones. |
| `TRANSCRIPTOR_PORT` | `8731` | Puerto local. |

## Seguridad

Ver [SECURITY.md](SECURITY.md). En resumen: los **audios y transcripciones son datos del
usuario y están gitignored** — el repo solo versiona código. El CI corre **gitleaks** (bloquea
si hay secretos) y **ruff** (lint).

## Notas técnicas

- En Windows, ctranslate2 necesita `cublas64_12.dll` + cuDNN. El paquete `nvidia` es un
  *namespace package* (sin `__file__`), por eso las DLLs se resuelven vía
  `importlib.util.find_spec("nvidia").submodule_search_locations` y se agregan al PATH
  (`app/engine.py: cargar_dlls_cuda`). Sin esto, falla con *"Library cublas64_12.dll is not found"*.
- La salida se escribe **en streaming**: si una transcripción larga se interrumpe, lo ya
  procesado queda en el `.txt`.
