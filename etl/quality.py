"""ตรวจคุณภาพข้อมูลหลังดึงเข้าคลัง

ทำงานบนคลังข้อมูลในเครื่อง ไม่แตะ ERP จึงรันได้ทุกรอบโดยไม่กวนเครื่อง production

SQL ในไฟล์นี้ใช้เฉพาะไวยากรณ์กลางที่ทั้ง SQLite และ SQL Server เข้าใจตรงกัน
ส่วนการประกอบข้อความและการเทียบค่าทำในฝั่ง Python เหมือน transform.py

ตัวที่สำคัญที่สุดคือ orphan_rcv_line กับ po_seq_gap สองตัวนี้คือสัญญาณว่า
มีคนลบใบสั่งซื้อหรือลบบรรทัดในใบสั่งซื้อทิ้ง ซึ่งจะทำให้ยอดรับหายจากรายงาน
แบบเงียบ ๆ ปัจจุบัน (ข้อมูล 2024+) เป็นศูนย์ทั้งคู่ ถ้าวันหนึ่งขึ้นมาต้องรู้ทันที
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.engine import Engine

from . import warehouse


def _year(v) -> int | None:
    """SQLite คืนวันที่มาเป็น str เมื่ออ่านด้วย raw SQL ส่วน SQL Server คืน datetime"""
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return dt.datetime.fromisoformat(v).year
        except ValueError:
            return None
    return v.year

COLUMNS = ["CheckName", "Severity", "Description", "PoNo", "PoSeq", "Detail", "Value"]

HIGH, MED, LOW = "สูง", "กลาง", "ต่ำ"


def _orphan_rcv_line(eng):
    """ใบรับอ้างบรรทัด PO ที่หายไป ทั้งที่ตัวใบ PO ยังอยู่ในหน้าต่างข้อมูล

    นี่คือสัญญาณจริงว่ามีคนลบบรรทัดใน PO ทิ้ง
    ส่วนกรณีที่ตัวใบ PO เองอยู่นอกหน้าต่าง (PO เก่ากว่าปี 2024 แต่เพิ่งมี
    ใบส่งคืนปีนี้) ไม่ใช่ความผิดปกติ แยกไปเป็น rcv_po_out_of_window
    """
    rows = warehouse.read(eng, """
        SELECT h.PONO AS PoNo, d.POSEQ AS PoSeq, h.DOCNO AS RcvNo, d.QTY AS Qty
        FROM rcv_detail d JOIN rcv_header h ON h.DOCNO = d.DOCNO
        WHERE EXISTS (SELECT 1 FROM po_header p WHERE p.DOCNO = h.PONO)
          AND NOT EXISTS (
            SELECT 1 FROM po_detail o WHERE o.DOCNO = h.PONO AND o.SEQ = d.POSEQ)
    """)
    return [(r["PoNo"], r["PoSeq"], f"ใบรับ {r['RcvNo']} รับ {r['Qty']}", r["Qty"]) for r in rows]


def _rcv_po_out_of_window(eng):
    """ใบรับที่อ้าง PO เก่ากว่าหน้าต่างข้อมูล - ปกติ ไม่ใช่ข้อผิดพลาด"""
    rows = warehouse.read(eng, """
        SELECT h.PONO AS PoNo, d.POSEQ AS PoSeq, h.DOCNO AS RcvNo, d.QTY AS Qty
        FROM rcv_detail d JOIN rcv_header h ON h.DOCNO = d.DOCNO
        WHERE NOT EXISTS (SELECT 1 FROM po_header p WHERE p.DOCNO = h.PONO)
    """)
    return [(r["PoNo"], r["PoSeq"], f"ใบรับ {r['RcvNo']} รับ {r['Qty']}", r["Qty"]) for r in rows]


def _po_seq_gap(eng):
    seqs: dict[str, list[int]] = {}
    for r in warehouse.read(eng, "SELECT DOCNO, SEQ FROM po_detail"):
        try:
            seqs.setdefault(r["DOCNO"], []).append(int(r["SEQ"]))
        except (TypeError, ValueError):
            continue
    out = []
    for doc, nums in seqs.items():
        if len(nums) != max(nums):
            out.append((doc, "", f"มี {len(nums)} บรรทัด แต่เลขสูงสุดคือ {max(nums)}",
                        max(nums) - len(nums)))
    return out


def _erp_rcvqty_mismatch(eng):
    rows = warehouse.read(eng, """
        SELECT PoNo, PoSeq, ErpRcvQty, RcvQty FROM fact_po_line WHERE ErpRcvQtyMismatch = 1
    """)
    return [(r["PoNo"], r["PoSeq"],
             f"ERP บอก {r['ErpRcvQty']} แต่รวมจากใบรับจริง {r['RcvQty']}",
             r["ErpRcvQty"] - r["RcvQty"]) for r in rows]


def _rcv_before_po(eng):
    rows = warehouse.read(eng, """
        SELECT PoNo, PoSeq, PoDat, FirstRcvDat, LeadTimeDays
        FROM fact_po_line WHERE LeadTimeDays < 0
    """)
    return [(r["PoNo"], r["PoSeq"],
             f"PO ลง {str(r['PoDat'])[:10]} แต่รับ {str(r['FirstRcvDat'])[:10]}",
             r["LeadTimeDays"]) for r in rows]


def _stale_open(eng):
    rows = warehouse.read(eng, """
        SELECT PoNo, PoSeq, OpenQty, OpenAmt, OverdueDays
        FROM fact_po_line WHERE IsOpen = 1 AND OverdueDays > 90
    """)
    return [(r["PoNo"], r["PoSeq"],
             f"ค้าง {r['OpenQty']} เกินกำหนด {r['OverdueDays']} วัน",
             r["OpenAmt"]) for r in rows]


def _bad_date(eng):
    rows = warehouse.read(eng, "SELECT PoNo, PoSeq, PoDat FROM fact_po_line")
    out = []
    for r in rows:
        y = _year(r["PoDat"])
        if y is not None and not (2000 <= y <= 2035):
            out.append((r["PoNo"], r["PoSeq"], f"PoDat = {r['PoDat']}", 0))
    return out


CHECKS = [
    ("orphan_rcv_line", HIGH, "ใบรับอ้างบรรทัด PO ที่ไม่มีอยู่จริง (อาจมีคนลบใบสั่งซื้อทิ้ง)", _orphan_rcv_line),
    ("rcv_po_out_of_window", LOW, "ใบรับอ้าง PO ที่เก่ากว่าหน้าต่างข้อมูล (ปกติ ไม่ใช่ข้อผิดพลาด)", _rcv_po_out_of_window),
    ("po_seq_gap", HIGH, "เลขลำดับบรรทัดใน PO ไม่ต่อเนื่อง (อาจมีคนลบบรรทัดทิ้ง)", _po_seq_gap),
    ("erp_rcvqty_mismatch", MED, "RCVQTY ใน ERP ไม่ตรงกับยอดรวมจากใบรับจริง", _erp_rcvqty_mismatch),
    ("rcv_before_po", MED, "วันที่รับของก่อนวันที่ในใบสั่งซื้อ (บันทึกเอกสารย้อนหลัง)", _rcv_before_po),
    ("stale_open", LOW, "ค้างรับเกิน 90 วัน ควรพิจารณาปิด", _stale_open),
    ("bad_date", LOW, "วันที่ผิดปกติ นอกช่วงปี 2000-2035", _bad_date),
]


def run(eng: Engine) -> dict[str, tuple[str, int]]:
    rows: list[tuple] = []
    summary: dict[str, tuple[str, int]] = {}
    for name, sev, desc, fn in CHECKS:
        found = fn(eng)
        summary[name] = (sev, len(found))
        rows.extend((name, sev, desc, *f) for f in found)
    warehouse.replace_table(eng, "dq_issue", COLUMNS, rows)
    warehouse.index(eng, "dq_issue", ["CheckName"])
    return summary
