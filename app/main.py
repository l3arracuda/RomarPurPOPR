"""เว็บแอปรายงานจัดซื้อ

    python -m app          แล้วเปิด http://127.0.0.1:8080

อ่านจากคลังข้อมูลในเครื่อง (data/purchase.sqlite) เท่านั้น ไม่ต่อ ERP โดยตรง
ถ้าต้องการข้อมูลล่าสุดให้กดปุ่มอัปเดตในหน้าเว็บ หรือรัน python -m etl sync
"""
from __future__ import annotations

import datetime as dt
import io
import re
import threading
from urllib.parse import quote

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from etl import config, report, sync
from . import queries

app = FastAPI(title="รายงานจัดซื้อ ROMAR", docs_url=None, redoc_url=None)
STATIC = config.ROOT / "app" / "static"
_sync_lock = threading.Lock()
_sync_state: dict = {"running": False, "last": None, "error": None}


@app.get("/")
def index():
    """ส่งหน้าเว็บพร้อมติดหมายเลขรุ่นให้ไฟล์ css/js

    ถ้าไม่ทำแบบนี้ เบราว์เซอร์จะใช้ไฟล์เก่าที่แคชไว้หลังอัปเดตโค้ด
    ผู้ใช้จะเห็นหน้าเดิมและนึกว่าของใหม่ยังไม่มา ต้องสั่ง hard refresh เอง
    """
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    ver = int(max((STATIC / f).stat().st_mtime for f in ("app.js", "style.css")))
    html = html.replace("/static/app.js", f"/static/app.js?v={ver}")
    html = html.replace("/static/style.css", f"/static/style.css?v={ver}")
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


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


@app.get("/api/receipts/docs")
def receipt_docs(date_from: str = Query(...), date_to: str = Query(...),
                 supplier: str = "", buyer: str = "", q: str = ""):
    return queries.rcv_docs(date_from, date_to, supplier, buyer, q)


@app.get("/api/receipts/detail")
def receipt_detail(rcvno: str = Query(...)):
    return queries.rcv_doc_detail(rcvno)


@app.get("/api/po")
def po_docs(date_from: str = Query(...), date_to: str = Query(...),
            supplier: str = "", buyer: str = "", q: str = "",
            sort: str = "lastrcv", only_open: bool = False,
            kind: str = "ใบสั่งซื้อ"):
    return queries.po_docs(date_from, date_to, supplier, buyer, q, sort, only_open, kind)


@app.get("/api/po/detail")
def po_detail(pono: str = Query(...)):
    return queries.po_detail(pono)


@app.get("/api/export/r1")
def export_r1(date_from: str = Query(...), date_to: str = Query(...)):
    path = report.r1(date_from, date_to)
    return _send(path)


@app.get("/api/export/r2")
def export_r2(supplier: str = "", buyer: str = "", kind: str = "ใบสั่งซื้อ"):
    path = report.r2(None, supplier, buyer, kind)
    return _send(path)


def _send(path):
    """ส่งไฟล์ Excel กลับไปให้เบราว์เซอร์

    ชื่อไฟล์เป็นภาษาไทย ซึ่งใส่ลง HTTP header ตรง ๆ ไม่ได้เพราะ header รองรับแค่
    latin-1 จึงต้องส่งสองแบบคู่กันตาม RFC 5987 คือชื่อสำรองที่เป็น ASCII ล้วน
    สำหรับเบราว์เซอร์เก่า และ filename* ที่เข้ารหัส UTF-8 สำหรับเบราว์เซอร์ปัจจุบัน
    """
    data = path.read_bytes()
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.name).strip("_") or "report.xlsx"
    disposition = (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(path.name)}"
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disposition},
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
