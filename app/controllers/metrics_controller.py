"""Métricas del panel: resumen, visitas, recorridos y suscriptoras."""
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ..deps import require_admin
from ..services.metrics_services import MetricsServices

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
service = MetricsServices()


@router.get("/stats")
def summary(days: int = 30, month: Optional[str] = None):
    return service.summary(days, month)


@router.get("/visitors")
def visitors(days: int = 30, filter: str = "all"):
    return service.visitors(days, filter)


@router.get("/visitors/{sid}")
def timeline(sid: str):
    return service.timeline(sid)


@router.get("/subscribers")
def subscribers():
    return service.subscribers()


@router.get("/subscribers.csv")
def subscribers_csv():
    return PlainTextResponse(service.subscribers_csv(), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": 'attachment; filename="suscriptoras.csv"'})


@router.post("/reset-metrics")
def reset():
    return {"ok": True, "deleted": service.reset()}
