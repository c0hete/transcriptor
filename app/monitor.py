# -*- coding: utf-8 -*-
"""Métricas de consumo para la UI: GPU (nvidia-smi) y CPU/RAM (psutil si está)."""
import shutil
import subprocess


def gpu() -> dict | None:
    """Lee uso de GPU vía nvidia-smi. None si no hay GPU/herramienta."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        name, util, mem_used, mem_total, temp = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",")]
        return {
            "nombre": name,
            "uso_pct": float(util),
            "vram_used_mb": float(mem_used),
            "vram_total_mb": float(mem_total),
            "vram_pct": round(100 * float(mem_used) / float(mem_total), 1) if float(mem_total) else 0,
            "temp_c": float(temp),
        }
    except Exception:  # noqa: BLE001
        return None


def cpu() -> dict:
    """Uso de CPU y RAM. Degrada con elegancia si no hay psutil."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {
            "uso_pct": psutil.cpu_percent(interval=None),
            "ram_pct": vm.percent,
            "ram_used_gb": round(vm.used / (1024 ** 3), 1),
            "ram_total_gb": round(vm.total / (1024 ** 3), 1),
        }
    except Exception:  # noqa: BLE001
        return {"uso_pct": None, "ram_pct": None}


def todo() -> dict:
    return {"gpu": gpu(), "cpu": cpu()}
