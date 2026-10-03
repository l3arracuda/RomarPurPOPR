"""สร้างตาราง fact_po_line — ชุดข้อมูลแกนกลางที่รายงานทุกตัวใช้ร่วมกัน

ตรรกะธุรกิจทั้งหมดอยู่ในไฟล์นี้ไฟล์เดียว เขียนด้วย Python ไม่ใช่ SQL
เพื่อให้ผลลัพธ์เหมือนกันทั้งบน SQLite (dev) และ SQL Server (prod)
โดยเฉพาะการคำนวณส่วนต่างวันที่ซึ่งสองระบบเขียนไม่เหมือนกัน

ไฟล์ sql/extract/po_vs_rcv.sql ทำสิ่งเดียวกันด้วย T-SQL ไว้ cross-check
รันคำสั่ง  python -m etl verify  เพื่อเทียบสองทางว่าตรงกัน
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy.engine import Engine

from . import warehouse

# ค่าว่างของ TDateTime ในระบบเดิม
_EMPTY_DATE = dt.datetime(1899, 12, 30)

PO_STATUS = {
    "P": "ใช้งาน",
    "A": "รออนุมัติ",
    "T": "ปิด/ยกเลิก",
    "C": "ปิด/ยกเลิก (เลิกใช้แล้ว)",
}
# สถานะที่ไม่ควรนับเป็นของค้างรับ
_NOT_OPEN = {"A", "T", "C"}


def _d(v: Any) -> dt.datetime | None:
    """แปลงวันที่ โดยถือว่า 1899-12-30 คือค่าว่าง"""
    if v is None:
        return None
    if isinstance(v, str):
        v = dt.datetime.fromisoformat(v)
    return None if v == _EMPTY_DATE else v


def _days(a: dt.datetime | None, b: dt.datetime | None) -> int | None:
    return None if a is None or b is None else (b.date() - a.date()).days


def build(eng: Engine, tolerance: float = 0.02) -> int:
    """ประกอบ fact_po_line แล้วเขียนทับของเดิม

    tolerance ใช้แค่ตัดสิน *ป้ายสถานะ* เท่านั้น ตัวเลขจำนวนและมูลค่าดิบ
    ไม่ถูกปัดหรือตัดทิ้ง ผู้ใช้จึงยังเห็นส่วนต่างจริงเสมอ
    """
    sup = {r["SUPCD"]: r for r in warehouse.read(eng, "SELECT * FROM supplier")}
    pdt = {r["PDTCD"]: r for r in warehouse.read(eng, "SELECT * FROM product")}
    poh = {r["DOCNO"]: r for r in warehouse.read(eng, "SELECT * FROM po_header")}

    # รวมยอดรับต่อบรรทัด PO : DOCTYP R(รับ) + T(ส่งคืน ติดลบอยู่แล้ว) = ยอดสุทธิ
    agg: dict[tuple[str, str], dict] = {}
    for r in warehouse.read(
        eng,
        """
        SELECT h.PONO, d.POSEQ, h.DOCTYP, h.DOCNO, h.DOCDAT, d.QTY
        FROM rcv_detail d JOIN rcv_header h ON h.DOCNO = d.DOCNO
        """,
    ):
        key = (r["PONO"], r["POSEQ"])
        a = agg.setdefault(
            key, {"qty": 0.0, "ret": 0.0, "first": None, "last": None, "docs": set()}
        )
        qty = float(r["QTY"] or 0)
        a["qty"] += qty
        if r["DOCTYP"] == "T":
            a["ret"] += qty
        else:
            when = _d(r["DOCDAT"])
            a["docs"].add(r["DOCNO"])
            if when:
                a["first"] = when if a["first"] is None else min(a["first"], when)
                a["last"] = when if a["last"] is None else max(a["last"], when)
    return _write(eng, poh, sup, pdt, agg, tolerance)


COLUMNS = [
    "PoNo", "PoDat", "PoYm", "PoStatus", "PoStatusName", "Buyer",
    "SupCd", "SupNam", "PoSeq", "PdtCd", "PdtNam", "PdtGrp",
    "ShipDat", "OrderQty", "Unit", "PackSize", "Price", "OrderAmt",
    "RcvQty", "RcvAmt", "RetQty", "OpenQty", "OpenAmt", "FillPct",
    "LineStatus", "IsOpen", "FirstRcvDat", "LastRcvDat", "RcvYm", "RcvDocCount",
    "LeadTimeDays", "DaysLate", "OverdueDays", "ErpRcvQty", "ErpRcvQtyMismatch",
]


def _ym(d: dt.datetime | None) -> str | None:
    return None if d is None else f"{d.year:04d}-{d.month:02d}"


def _write(eng, poh, sup, pdt, agg, tol) -> int:
    today = dt.datetime.now()
    rows: list[tuple] = []

    for d in warehouse.read(eng, "SELECT * FROM po_detail"):
        head = poh.get(d["DOCNO"])
        if head is None:
            continue  # บรรทัดกำพร้า ไม่ควรมี แต่กันไว้

        a = agg.get((d["DOCNO"], d["SEQ"]))
        order_qty = float(d["QTY"] or 0)
        price = float(d["PRICE"] or 0)
        rcv_qty = float(a["qty"]) if a else 0.0
        open_qty = max(order_qty - rcv_qty, 0.0)
        status = head["APPSTS"]
        ship = _d(d["ShipDat"])
        first = a["first"] if a else None
        po_dat = _d(head["DOCDAT"])

        if status in _NOT_OPEN:
            line_status = PO_STATUS.get(status, status)
        elif rcv_qty <= 0:
            line_status = "ยังไม่รับ"
        elif rcv_qty > order_qty * (1 + tol):
            line_status = "รับเกิน"
        elif rcv_qty >= order_qty * (1 - tol):
            line_status = "รับครบ"
        else:
            line_status = "รับบางส่วน"

        is_open = int(
            status not in _NOT_OPEN and rcv_qty < order_qty * (1 - tol)
        )
        overdue = _days(ship, today) if (is_open and ship and ship < today) else None
        erp_rcv = float(d["RCVQTY"] or 0)

        rows.append((
            d["DOCNO"], po_dat, _ym(po_dat), status, PO_STATUS.get(status, status),
            head["Buyer"], head["SUPCD"],
            (sup.get(head["SUPCD"]) or {}).get("SUPNAM"),
            d["SEQ"], d["PDTCD"],
            (pdt.get(d["PDTCD"]) or {}).get("PDTNAM"),
            (pdt.get(d["PDTCD"]) or {}).get("PDTGRP"),
            ship, order_qty, d["UNIT"], float(d["PACKSIZE"] or 1), price,
            float(d["AMT"] or 0),
            rcv_qty, rcv_qty * price, float(a["ret"]) if a else 0.0,
            open_qty, open_qty * price,
            (rcv_qty / order_qty) if order_qty else None,
            line_status, is_open,
            first, a["last"] if a else None, _ym(first),
            len(a["docs"]) if a else 0,
            _days(po_dat, first), _days(ship, first), overdue,
            erp_rcv, int(abs(erp_rcv - rcv_qty) >= 0.005),
        ))

    n = warehouse.replace_table(eng, "fact_po_line", COLUMNS, rows, pk=("PoNo", "PoSeq"))
    warehouse.index(eng, "fact_po_line", ["PoDat"])
    warehouse.index(eng, "fact_po_line", ["SupCd"])
    warehouse.index(eng, "fact_po_line", ["IsOpen"])
    return n
