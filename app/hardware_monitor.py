import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone

from fastapi import Depends


def _num(v):
    try:
        return round(float(v), 1)
    except Exception:
        return None


def _gpu():
    if not shutil.which("nvidia-smi"):
        return []
    try:
        p = subprocess.run([
            "nvidia-smi", "--query-gpu=name,utilization.gpu,memory.total,memory.used,temperature.gpu",
            "--format=csv,noheader,nounits"
        ], capture_output=True, text=True, timeout=3, check=True)
        out = []
        for line in p.stdout.strip().splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 5:
                out.append({
                    "name": parts[0],
                    "utilization_percent": _num(parts[1]),
                    "vram_total_mb": _num(parts[2]),
                    "vram_used_mb": _num(parts[3]),
                    "temperature_c": _num(parts[4]),
                })
        return out
    except Exception:
        return []


def _cpu_ram():
    cpu_count = os.cpu_count() or 1
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0, 0, 0)
    mem_total = mem_available = None
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0]) * 1024
        mem_total = info.get("MemTotal")
        mem_available = info.get("MemAvailable")
    except Exception:
        pass
    ram_used = (mem_total - mem_available) if mem_total is not None and mem_available is not None else None
    return {
        "logical_cores": cpu_count,
        "load_1m": _num(load[0]),
        "load_percent_estimate": _num(min(100.0, load[0] / max(cpu_count, 1) * 100.0)),
        "ram_total_bytes": mem_total,
        "ram_used_bytes": ram_used,
        "ram_available_bytes": mem_available,
    }


def snapshot():
    cpu = _cpu_ram()
    gpus = _gpu()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu": cpu,
        "gpus": gpus,
        "gpu_available": bool(gpus),
        "training": {
            "recommended": "gpu" if gpus else "cpu",
            "qlora_available": bool(gpus),
            "lora_available": True,
        },
    }


def install(app):
    @app.get("/v1/admin/hardware", dependencies=[Depends(app.state.require_admin)] if hasattr(app.state, "require_admin") else [])
    def hardware():
        return snapshot()
