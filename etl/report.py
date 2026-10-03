"""ออกรายงานเป็นไฟล์ Excel สำหรับฝ่ายจัดซื้อ

    python -m etl report r1 --from 2026-09-01 --to 2026-10-03
    python -m etl report r2
    python -m etl report r2 --supplier S-38-0001
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import xlsxwriter

from . import config, warehouse

OUT = config.ROOT / "out"

# (หัวคอลัมน์, ชื่อฟิลด์, ความกว้าง, รูปแบบ)
R1_COLS = [
    ("วันที่รับ", "RcvDat", 11, "date"), ("เลขที่ใบรับ", "RcvNo", 14, None),
    ("ประเภท", "DocTypName", 11, None), ("เลขที่ PO", "PoNo", 14, None),
    ("วันที่ PO", "PoDat", 11, "date"), ("ผู้ขาย", "SupNam", 32, None),
    ("รหัสสินค้า", "PdtCd", 19, None), ("ชื่อสินค้า", "PdtNam", 36, None),
    ("จำนวนรับ", "Qty", 12, "qty"), ("หน่วย", "Unit", 8, None),
    ("ราคา", "Price", 10, "qty"), ("มูลค่า", "Amt", 14, "money"),
    ("ที่เก็บ", "LocCd", 9, None), ("กำหนดส่ง", "ShipDat", 11, "date"),
    ("ช้า(วัน)", "DaysLate", 9, "int"), ("เอกสารผู้ขาย", "SupDocNo", 13, None),
    ("ผู้บันทึก", "Enterer", 12, None), ("หมายเหตุ", "Rem", 40, None),
]

R2_COLS = [
    ("เลขที่ PO", "PoNo", 14, None), ("ชนิดเอกสาร", "DocKind", 12, None),
    ("วันที่ PO", "PoDat", 11, "date"),
    ("ผู้สั่ง", "Buyer", 12, None), ("ผู้ขาย", "SupNam", 32, None),
    ("ลำดับ", "PoSeq", 7, None), ("รหัสสินค้า", "PdtCd", 19, None),
    ("ชื่อสินค้า", "PdtNam", 36, None), ("กำหนดส่ง", "ShipDat", 11, "date"),
    ("จำนวนสั่ง", "OrderQty", 12, "qty"), ("รับแล้ว", "RcvQty", 12, "qty"),
    ("ส่งคืน", "RetQty", 11, "qty"), ("รับสุทธิ", "RcvQtyNet", 12, "qty"),
    ("คงค้าง", "OpenQty", 12, "qty"), ("หน่วย", "Unit", 8, None),
    ("ราคา", "Price", 10, "qty"), ("มูลค่าค้าง", "OpenAmt", 14, "money"),
    ("%รับ", "FillPct", 8, "pct"), ("สถานะ", "LineStatus", 12, None),
    ("เกินกำหนด(วัน)", "OverdueDays", 14, "int"),
    ("รับล่าสุด", "LastRcvDat", 11, "date"), ("จำนวนครั้งที่รับ", "RcvDocCount", 15, "int"),
]


def _write_sheet(wb, name, cols, rows, note, money_cols=()):
    ws = wb.add_worksheet(name)
    f = {
        "head": wb.add_format({"bold": True, "bg_color": "#2F5496", "font_color": "white",
                               "border": 1, "align": "center", "valign": "vcenter",
                               "text_wrap": True}),
        "note": wb.add_format({"italic": True, "font_color": "#666666"}),
        "date": wb.add_format({"num_format": "dd/mm/yyyy"}),
        "qty": wb.add_format({"num_format": "#,##0.00"}),
        "money": wb.add_format({"num_format": "#,##0.00"}),
        "int": wb.add_format({"num_format": "#,##0"}),
        "pct": wb.add_format({"num_format": "0.0%"}),
        None: wb.add_format({}),
        "total": wb.add_format({"bold": True, "num_format": "#,##0.00", "top": 1}),
        "totlbl": wb.add_format({"bold": True, "top": 1}),
    }
    ws.write(0, 0, note, f["note"])
    for i, (title, _, width, _fmt) in enumerate(cols):
        ws.write(2, i, title, f["head"])
        ws.set_column(i, i, width)
    ws.freeze_panes(3, 0)
    ws.autofilter(2, 0, 2 + len(rows), len(cols) - 1)

    for r, row in enumerate(rows, start=3):
        for c, (_t, field, _w, fmt) in enumerate(cols):
            v = row.get(field)
            if isinstance(v, str) and fmt == "date":
                try:
                    v = dt.datetime.fromisoformat(v)
                except ValueError:
                    v = None
            if v is None:
                ws.write_blank(r, c, None, f[fmt])
            elif isinstance(v, dt.datetime):
                ws.write_datetime(r, c, v, f["date"])
            else:
                ws.write(r, c, v, f[fmt])

    if rows:
        last = 3 + len(rows)
        ws.write(last, 0, f"รวม {len(rows):,} บรรทัด", f["totlbl"])
        for c, (_t, field, _w, _f) in enumerate(cols):
            if field in money_cols:
                ws.write_formula(last, c, f"=SUBTOTAL(109,{_a1(3,c)}:{_a1(last-1,c)})",
                                 f["total"])
    return ws


def _a1(row: int, col: int) -> str:
    s = ""
    col += 1
    while col:
        col, rem = divmod(col - 1, 26)
        s = chr(65 + rem) + s
    return f"{s}{row + 1}"


def _stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M")


def r1(date_from: str, date_to: str, out: str | None = None) -> Path:
    """R1 — ใบรับเข้าตามช่วงเวลา"""
    eng = warehouse.engine()
    rows = warehouse.read(eng, """
        SELECT * FROM fact_rcv_line
        WHERE RcvDat >= :a AND RcvDat < :b
        ORDER BY RcvDat DESC, RcvNo, RcvSeq
    """, {"a": date_from, "b": _plus_day(date_to)})

    path = Path(out) if out else OUT / f"R1_รับเข้า_{date_from}_ถึง_{date_to}_{_stamp()}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(path, {"default_date_format": "dd/mm/yyyy"})
    note = (f"รายงานใบรับเข้าซื้อ  {date_from} ถึง {date_to}   "
            f"| ออกเมื่อ {dt.datetime.now():%d/%m/%Y %H:%M} "
            f"| ยอดส่งคืนแสดงเป็นจำนวนติดลบ")
    _write_sheet(wb, "ใบรับเข้า", R1_COLS, rows, note, money_cols={"Qty", "Amt"})
    wb.close()
    print(f"R1 : {len(rows):,} บรรทัด -> {path}")
    return path


def r2(out: str | None = None, supplier: str = "", buyer: str = "",
       kind: str = "ใบสั่งซื้อ") -> Path:
    """R2 — ค้างรับ (Open PO)"""
    eng = warehouse.engine()
    where = ["IsOpen = 1"]
    params: dict = {}
    if kind:
        where.append("DocKind = :k")
        params["k"] = kind
    if supplier:
        where.append("SupCd = :s")
        params["s"] = supplier
    if buyer:
        where.append("Buyer = :b")
        params["b"] = buyer
    rows = warehouse.read(eng, f"""
        SELECT * FROM fact_po_line WHERE {' AND '.join(where)}
        ORDER BY ShipDat, PoNo, PoSeq
    """, params)

    path = Path(out) if out else OUT / f"R2_ค้างรับ_{_stamp()}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(path, {"default_date_format": "dd/mm/yyyy"})
    total = sum(float(r["OpenAmt"] or 0) for r in rows)
    overdue = [r for r in rows if (r["OverdueDays"] or 0) > 0]
    note = (f"รายงานของค้างรับ ณ {dt.datetime.now():%d/%m/%Y %H:%M}   "
            f"| ค้างรวม {total:,.2f} บาท | เกินกำหนด {len(overdue):,} บรรทัด "
            f"มูลค่า {sum(float(r['OpenAmt'] or 0) for r in overdue):,.2f} บาท "
            f"| ข้อมูลเริ่มปี 2024 (ปี 2021-2023 สูญหายจากไวรัส)")
    ws = _write_sheet(wb, "ค้างรับ", R2_COLS, rows, note,
                      money_cols={"OrderQty", "RcvQty", "OpenQty", "OpenAmt"})

    # ไฮไลต์แถวที่เกินกำหนดส่งให้เห็นชัด
    col = [c[1] for c in R2_COLS].index("OverdueDays")
    if rows:
        ws.conditional_format(3, 0, 2 + len(rows), len(R2_COLS) - 1, {
            "type": "formula",
            "criteria": f"=${_a1(0, col)[:-1]}4>0",
            "format": wb.add_format({"bg_color": "#FFE3E3"}),
        })
    wb.close()
    print(f"R2 : {len(rows):,} บรรทัด | ค้างรวม {total:,.2f} บาท -> {path}")
    return path


def _plus_day(d: str) -> str:
    return (dt.date.fromisoformat(d) + dt.timedelta(days=1)).isoformat()
