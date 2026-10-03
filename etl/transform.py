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

# APPSTS คือธงสถานะงานของใบสั่งซื้อ พิสูจน์จากรายงาน pcsr0511 จำนวน 687 บรรทัด
# ลงตัวทุกบรรทัดไม่มีข้อยกเว้น  P = ปิดงานแล้ว  ส่วน A กับ T = ยังเปิดอยู่
PO_STATUS = {
    "P": "ปิดงานแล้ว",
    "A": "เปิดอยู่ (ยังไม่เคยรับ)",
    "T": "เปิดอยู่ (รับบางส่วนแล้ว)",
    "C": "เลิกใช้แล้ว (พบเฉพาะก่อนปี 2017)",
}
CLOSED = "P"

# เดิมเคยเข้าใจว่า APPSTS = T คือยกเลิก แต่พิสูจน์แล้วว่าผิด:
# PP1-69-02718 มี APPSTS=T และรายงานของ ERP เองแสดงว่า "ค้างรับ" 4,000 เมตร
# จึงนับ T เป็นใบที่ใช้งานปกติ เหลือแค่ A (รออนุมัติ) ที่ไม่นับเป็นของค้างรับ
_PENDING = {"A"}


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
    n = _write(eng, poh, sup, pdt, agg, tolerance)
    _write_rcv(eng, poh, sup, pdt)
    return n


COLUMNS = [
    "PoNo", "PoDat", "PoYm", "PoStatus", "PoStatusName", "Buyer",
    "SupCd", "SupNam", "PoSeq", "PdtCd", "PdtNam", "PdtGrp",
    "ShipDat", "OrderQty", "Unit", "PackSize", "Price", "OrderAmt",
    "RcvQty", "RcvAmt", "RetQty", "RcvQtyNet", "OpenQty", "OpenAmt",
    "OpenQtyNet", "FillPct",
    "LineStatus", "ErpStatus", "IsOpen", "FirstRcvDat", "LastRcvDat", "RcvYm", "RcvDocCount",
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
        # ERP นับ "รับแล้ว" แบบไม่หักส่งคืน (ตรวจแล้วว่า qtyrcv = POC_POD.RCVQTY
        # ซึ่งรวมเฉพาะใบ PR1) เราจึงให้คอลัมน์หลักตรงกับ ERP เพื่อให้กระทบยอดกันได้
        # แล้วแยกยอดสุทธิไว้อีกคอลัมน์สำหรับคนที่อยากเห็นความจริง
        ret_qty = float(a["ret"]) if a else 0.0           # ติดลบอยู่แล้ว
        rcv_qty = (float(a["qty"]) - ret_qty) if a else 0.0  # รับเข้า ไม่หักคืน
        rcv_net = rcv_qty + ret_qty
        open_qty = max(order_qty - rcv_qty, 0.0)
        open_net = max(order_qty - rcv_net, 0.0)
        status = head["APPSTS"]
        ship = _d(d["ShipDat"])
        first = a["first"] if a else None
        po_dat = _d(head["DOCDAT"])

        if status == CLOSED and open_qty > 0.005:
            line_status = "ปิดด้วยมือ (ยังค้าง)"
        elif rcv_qty <= 0:
            line_status = "ยังไม่รับ"
        elif rcv_qty > order_qty * (1 + tol):
            line_status = "รับเกิน"
        elif rcv_qty >= order_qty * (1 - tol):
            line_status = "รับครบ"
        else:
            line_status = "รับบางส่วน"

        # กฎเดียวกับรายงาน pcsr0511 ของ ERP (ตรวจแล้ว 687/687 บรรทัด):
        #   ค้างรับ  ก็ต่อเมื่อ  APPSTS != P  และยังมียอดค้าง
        #   ปิด      ในกรณีอื่นทั้งหมด รวมถึงใบที่ APPSTS = P แต่ยังค้างอยู่
        #            ซึ่งคือการ "ปิดด้วยมือ" ที่จัดซื้อทำเมื่อตัดสินใจว่าจบงานแล้ว
        is_open = int(status != CLOSED and open_qty > 0.005)
        erp_status = "ค้างรับ" if is_open else "ปิด"
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
            rcv_qty, rcv_qty * price, ret_qty, rcv_net,
            open_qty, open_qty * price, open_net,
            (rcv_qty / order_qty) if order_qty else None,
            line_status, erp_status, is_open,
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


RCV_COLUMNS = [
    "RcvNo", "RcvDat", "RcvYm", "DocTyp", "DocTypName", "SupDocNo",
    "PoNo", "PoDat", "SupCd", "SupNam", "RcvSeq", "PoSeq",
    "PdtCd", "PdtNam", "PdtGrp", "Qty", "Unit", "Price", "Amt",
    "LocCd", "ShipDat", "DaysLate", "Enterer", "Rem",
]

DOC_TYPE = {"R": "รับเข้าซื้อ", "T": "ส่งคืนผู้ขาย"}


def _write_rcv(eng, poh, sup, pdt) -> int:
    """ตารางระดับ 'บรรทัดใบรับ' สำหรับรายงานของเข้ารายวัน (R1)"""
    loc = {
        (r["DOCNO"], r["SEQ"]): r["LOCCD"]
        for r in warehouse.read(eng, "SELECT DOCNO, SEQ, LOCCD FROM rcv_location")
    }
    poline = {
        (r["DOCNO"], r["SEQ"]): r
        for r in warehouse.read(eng, "SELECT DOCNO, SEQ, ShipDat FROM po_detail")
    }
    heads = {
        r["DOCNO"]: r
        for r in warehouse.read(eng, "SELECT * FROM rcv_header")
    }

    rows = []
    for d in warehouse.read(eng, "SELECT * FROM rcv_detail"):
        h = heads.get(d["DOCNO"])
        if h is None:
            continue
        rcv_dat = _d(h["DOCDAT"])
        po = poh.get(h["PONO"])
        pl = poline.get((h["PONO"], d["POSEQ"]))
        ship = _d(pl["ShipDat"]) if pl else None
        qty = float(d["QTY"] or 0)
        price = float(d["PRICE"] or 0)
        rows.append((
            d["DOCNO"], rcv_dat, _ym(rcv_dat), h["DOCTYP"],
            DOC_TYPE.get(h["DOCTYP"], h["DOCTYP"]), h["EXTNO"],
            h["PONO"], _d(po["DOCDAT"]) if po else None,
            h["SUPCD"], (sup.get(h["SUPCD"]) or {}).get("SUPNAM"),
            d["SEQ"], d["POSEQ"], d["PDTCD"],
            (pdt.get(d["PDTCD"]) or {}).get("PDTNAM"),
            (pdt.get(d["PDTCD"]) or {}).get("PDTGRP"),
            qty, d["UNIT"], price, qty * price,
            loc.get((d["DOCNO"], d["SEQ"])), ship,
            _days(ship, rcv_dat), h["Enterer"], h["REM"],
        ))

    n = warehouse.replace_table(eng, "fact_rcv_line", RCV_COLUMNS, rows,
                                pk=("RcvNo", "RcvSeq"))
    warehouse.index(eng, "fact_rcv_line", ["RcvDat"])
    warehouse.index(eng, "fact_rcv_line", ["PoNo"])
    return n
