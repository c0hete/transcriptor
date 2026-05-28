# -*- coding: utf-8 -*-
"""Motor de transcripción: faster-whisper sobre GPU (con fallback a CPU).

Incorpora de fábrica los baches ya resueltos en c:\\CODIGO\\transcripciones\\INACAP:
  - Carga de DLLs CUDA (nvidia es namespace package -> resolver por find_spec).
  - Escritura en streaming (tolerante a fallo parcial).
  - Sin volcar texto a una consola cp1252 (eso crasheaba con caracteres no-latin).
"""
import os
import time
import importlib.util
from dataclasses import dataclass, field
from threading import Lock


def cargar_dlls_cuda() -> bool:
    """Agrega al PATH las DLLs CUDA de los paquetes pip nvidia-*-cu12.
    'nvidia' es un namespace package (sin __file__) -> resolver por __path__.
    Devuelve True si encontró al menos una carpeta de DLLs."""
    spec = importlib.util.find_spec("nvidia")
    if not spec or not spec.submodule_search_locations:
        return False
    encontrado = False
    for nvbase in spec.submodule_search_locations:
        for sub in ("cublas/bin", "cudnn/bin", "cuda_nvrtc/bin", "cuda_runtime/bin"):
            d = os.path.join(nvbase, *sub.split("/"))
            if os.path.isdir(d):
                os.add_dll_directory(d)
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                encontrado = True
    return encontrado


@dataclass
class Trabajo:
    """Estado observable de una transcripción (lo que la UI consulta)."""
    id: str
    nombre: str
    destino: str
    estado: str = "en_cola"          # en_cola | cargando | transcribiendo | hecho | error
    duracion_total: float = 0.0       # segundos de audio
    avance_seg: float = 0.0           # segundos de audio ya procesados
    porcentaje: float = 0.0
    n_segmentos: int = 0
    inicio: float = 0.0
    fin: float = 0.0
    salida_path: str = ""
    error: str = ""
    _lock: Lock = field(default_factory=Lock, repr=False)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id, "nombre": self.nombre, "estado": self.estado,
                "duracion_total": round(self.duracion_total, 1),
                "avance_seg": round(self.avance_seg, 1),
                "porcentaje": round(self.porcentaje, 1),
                "n_segmentos": self.n_segmentos,
                "transcurrido": round((self.fin or time.time()) - self.inicio, 1) if self.inicio else 0,
                "salida_path": self.salida_path, "error": self.error,
            }


class Motor:
    """Carga el modelo una vez y transcribe audios escribiendo en streaming.
    La instancia del modelo es cara: se reutiliza entre trabajos."""

    def __init__(self, modelo="large-v3", device="auto", compute_type="float16", language="es"):
        self.modelo_nombre = modelo
        self.language = language or None
        self._device_pedido = device
        self._compute_pedido = compute_type
        self._model = None
        self.device_real = None
        self.compute_real = None
        self._lock = Lock()

    def _cargar(self):
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        cuda_ok = cargar_dlls_cuda()

        intentos = []
        dev = self._device_pedido
        if dev == "auto":
            intentos = [("cuda", "float16"), ("cpu", "int8")]
        elif dev == "cuda":
            intentos = [("cuda", self._compute_pedido), ("cpu", "int8")]
        else:
            intentos = [("cpu", self._compute_pedido or "int8")]

        ultimo_err = None
        for device, compute in intentos:
            if device == "cuda" and not cuda_ok:
                ultimo_err = "DLLs CUDA no encontradas"
                continue
            try:
                kw = {} if device == "cuda" else {"cpu_threads": os.cpu_count() or 8}
                self._model = WhisperModel(self.modelo_nombre, device=device, compute_type=compute, **kw)
                self.device_real, self.compute_real = device, compute
                return
            except Exception as e:  # noqa: BLE001 - probamos el siguiente fallback
                ultimo_err = str(e)
        raise RuntimeError("No pude cargar el modelo en ningún dispositivo: %s" % ultimo_err)

    def transcribir(self, ruta: str, trabajo: Trabajo):
        """Transcribe `ruta` y va actualizando `trabajo` + escribiendo el .txt en streaming."""
        with self._lock:  # un trabajo a la vez (VRAM limitada: 8 GB)
            trabajo.estado = "cargando"
            trabajo.inicio = time.time()
            try:
                self._cargar()
            except Exception as e:  # noqa: BLE001
                trabajo.estado, trabajo.error, trabajo.fin = "error", str(e), time.time()
                return

            trabajo.estado = "transcribiendo"
            try:
                segments, info = self._model.transcribe(
                    ruta, language=self.language, vad_filter=True, beam_size=5
                )
            except Exception as e:  # noqa: BLE001
                trabajo.estado, trabajo.error, trabajo.fin = "error", str(e), time.time()
                return

            total = info.duration or 0.0
            with trabajo._lock:
                trabajo.duracion_total = total

            os.makedirs(os.path.dirname(trabajo.salida_path), exist_ok=True)
            ult, n = 0.0, 0
            try:
                with open(trabajo.salida_path, "w", encoding="utf-8") as f:
                    f.write("TRANSCRIPCION\n")
                    f.write("Audio: %s (%.0fs / %.1f min)\n" % (trabajo.nombre, total, total / 60 if total else 0))
                    f.write("faster-whisper %s (%s/%s, %s). Revisar: puede haber errores.\n"
                            % (self.modelo_nombre, self.device_real, self.compute_real, self.language or "auto"))
                    f.write("=" * 70 + "\n\n")
                    for s in segments:
                        f.write("[%02d:%02d] %s\n" % (int(s.start) // 60, int(s.start) % 60, s.text.strip()))
                        ult, n = s.end, n + 1
                        with trabajo._lock:
                            trabajo.avance_seg = ult
                            trabajo.n_segmentos = n
                            trabajo.porcentaje = (100 * ult / total) if total else 0
            except Exception as e:  # noqa: BLE001 - lo ya escrito queda en disco
                trabajo.estado, trabajo.error, trabajo.fin = "error", str(e), time.time()
                return

            with trabajo._lock:
                trabajo.estado = "hecho"
                trabajo.porcentaje = 100.0
                trabajo.fin = time.time()
