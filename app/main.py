"""เว็บแอปรายงานจัดซื้อ

    python -m app          แล้วเปิด http://127.0.0.1:8080

อ่านจากคลังข้อมูลในเครื่อง (data/purchase.sqlite) เท่านั้น ไม่ต่อ ERP โดยตรง
ถ้าต้องการข้อมูลล่าสุดให้กดปุ่มอัปเดตในหน้าเว็บ หรือรัน python -m etl sync
"""
from __future__ import annotations

import datetime as dt
import io
import threading

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from etl import config, report, sync
from . import queries

app = FastAPI(title="รายงานจัดซื้อ ROMAR", docs_url=None, redoc_url=None)
STATIC = config.ROOT / "app" / "static"
_sync_lock = threading.Lock()
_sync_state: dict = {"running": False, "last": None, "error": None}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    return {
        "range": queries.data_range(),
        "suppliers": queries.suppliers(),
        "buyers": queries.buyers(),
        "today": dt.date.today().isoformat(),
        "sync": _sync_state,
    }


@app.get("/api/summary")
def summary(date_from: str = Query(...), date_to: str = Query(...)):
    return queries.summary(date_from, date_to)


@app.get("/api/monthly")
def monthly(months: int = 12):
    return queries.monthly(months)


@app.get("/api/receipts")
def receipts(date_from: str = Query(...), date_to: str = Query(...),
             supplier: str = "", buyer: str = "", q: str = ""):
    return queries.receipts(date_from, date_to, supplier, buyer, q)


@app.get("/api/open")
def open_po(supplier: str = "", buyer: str = "", q: str = "",
            overdue_only: bool = False, kind: str = "ใบสั่งซื้อ"):
    return queries.open_po(supplier, buyer, q, overdue_only, kind)


@app.get("/api/export/r1")
def export_r1(date_from: str = Query(...), date_to: str = Query(...)):
    path = report.r1(date_from, date_to)
    return _send(path)


@app.get("/api/export/r2")
def export_r2(supplier: str = "", buyer: str = "", kind: str = "ใบสั่งซื้อ"):
    path = report.r2(None, supplier, buyer, kind)
    return _send(path)


def _send(path):
    data = path.read_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.post("/api/sync")
def do_sync():
    """ดึงข้อมูลใหม่จาก ERP — ทำทีละคนเท่านั้น กันไม่ให้ยิงซ้อนใส่เครื่อง production"""
    if not _sync_lock.acquire(blocking=False):
        return JSONResponse({"ok": False, "msg": "กำลังอัปเดตอยู่ กรุณารอสักครู่"}, 409)

    def work():
        _sync_state.update(running=True, error=None)
        try:
            sync.run()
            _sync_state["last"] = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        except Exception as exc:                      # noqa: BLE001
            _sync_state["error"] = str(exc)
        finally:
            _sync_state["running"] = False
            _sync_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "msg": "เริ่มอัปเดตข้อมูลแล้ว ใช้เวลาประมาณ 20 วินาที"}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
