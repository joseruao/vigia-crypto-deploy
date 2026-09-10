"""Agendador interno dos workers — substitui os serviços cron do Railway.

Corre DENTRO do processo da API (gunicorn `-w 1` → um único agendador) e lança
cada worker num SUBPROCESSO: os workers são pesados (scikit-learn, pandas,
dezenas de chamadas HTTP com sleeps) e não podem bloquear nem acumular memória
na API de produção.

Os horários são UTC, iguais aos que o Railway tinha:
    06:00 holdings · 07:00 top100 · 08:00 arkham

Controlo: `VIGIA_CRON_ENABLED=false` desliga o agendador (útil para deploys de
teste). A app tem de ter `alwaysOn=true` no App Service, senão adormece e os
jobs não disparam.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("vigia.cron")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent  # -> backend/

# No App Service o persistente é /home; localmente escreve-se em backend/logs/
_HOME_LOGS = Path("/home/LogFiles")
LOG_DIR = Path(os.getenv("CRON_LOG_DIR") or (_HOME_LOGS if _HOME_LOGS.exists() else BACKEND_DIR / "logs"))

# nome -> (expressão cron UTC, script relativo a backend/)
JOBS: dict[str, tuple[str, str]] = {
    "holdings": ("0 6 * * *", "dailyworker/daily_worker_runner.py"),
    "top100": ("0 7 * * *", "worker/vigia_solana_pro_supabase.py"),
    "arkham": ("0 8 * * *", "worker/arkham_scanner.py"),
}

_running: dict[str, subprocess.Popen] = {}
_last: dict[str, dict] = {}
_scheduler = None


def _log_path(name: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / f"cron_{name}.log"


def is_running(name: str) -> bool:
    proc = _running.get(name)
    if proc is None:
        return False
    if proc.poll() is None:
        return True
    _running.pop(name, None)
    return False


def run_worker(name: str) -> dict:
    """Lança um worker em background. Devolve imediatamente (não espera pelo fim)."""
    if name not in JOBS:
        raise KeyError(name)
    if is_running(name):
        return {"started": False, "reason": "já está a correr", "name": name, **_last.get(name, {})}

    _, script = JOBS[name]
    path = _log_path(name)
    started = time.time()
    with path.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(f"\n{'=' * 60}\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] a iniciar {script}\n")
        fh.flush()
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=str(BACKEND_DIR),
            stdout=fh,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
        )
    _running[name] = proc
    _last[name] = {"pid": proc.pid, "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "log": str(path)}
    log.info("cron %s: iniciado (pid %s, log %s)", name, proc.pid, path)
    return {"started": True, "name": name, "pid": proc.pid, "log": str(path), "elapsed_s": round(time.time() - started, 2)}


def status() -> dict:
    return {
        "enabled": os.getenv("VIGIA_CRON_ENABLED", "true").lower() == "true",
        "log_dir": str(LOG_DIR),
        "jobs": {
            name: {
                "cron": cron,
                "script": script,
                "running": is_running(name),
                **_last.get(name, {}),
            }
            for name, (cron, script) in JOBS.items()
        },
    }


def start_scheduler() -> None:
    """Arranca o agendador (chamado no startup da API)."""
    global _scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    if os.getenv("VIGIA_CRON_ENABLED", "true").lower() != "true":
        log.info("cron: desligado (VIGIA_CRON_ENABLED=false)")
        return
    if _scheduler is not None:
        return

    sched = BackgroundScheduler(timezone="UTC")
    for name, (cron, _script) in JOBS.items():
        sched.add_job(
            run_worker,
            CronTrigger.from_crontab(cron),
            args=[name],
            id=name,
            name=f"{name} ({cron} UTC)",
            # se o processo estiver ocupado à hora certa, ainda corre até 1h depois
            misfire_grace_time=3600,
            coalesce=True,
            max_instances=1,
        )
    sched.start()
    _scheduler = sched
    log.info("cron: agendador ligado (UTC) — %s", ", ".join(f"{n}@{c}" for n, (c, _s) in JOBS.items()))


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
