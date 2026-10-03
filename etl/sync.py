"""ดึงข้อมูลจาก ERP เข้าคลังข้อมูล แล้วประกอบตารางแกนกลาง"""
from __future__ import annotations

import time

from . import config, extract, quality, source, transform, warehouse


def run(window_start: str = config.DEFAULT_WINDOW_START, tolerance: float = 0.02) -> dict:
    t0 = time.perf_counter()
    eng = warehouse.engine()
    counts: dict[str, int] = {}

    with source.connect() as cn:
        for spec in extract.SPECS:
            params = (window_start,) * spec.nparams
            cols, rows = source.fetch(cn, spec.sql, params)
            counts[spec.name] = warehouse.replace_table(
                eng, spec.name, cols, rows, pk=spec.pk
            )
            print(f"  {spec.name:<12} {counts[spec.name]:>8,} แถว")

    warehouse.index(eng, "rcv_header", ["PONO"])
    warehouse.index(eng, "rcv_header", ["DOCDAT"])
    warehouse.index(eng, "rcv_detail", ["DOCNO"])

    counts["fact_po_line"] = transform.build(eng, tolerance)
    print(f"  {'fact_po_line':<12} {counts['fact_po_line']:>8,} แถว")

    print("ตรวจคุณภาพข้อมูล")
    for name, (sev, n) in quality.run(eng).items():
        mark = "  !!" if (n and sev == "สูง") else "    "
        print(f"{mark} {name:<22} {sev:<5} {n:>6,}")

    counts["_seconds"] = round(time.perf_counter() - t0, 1)
    return counts


def verify(window_start: str = config.DEFAULT_WINDOW_START) -> list[str]:
    """เทียบ fact_po_line (Python) กับ sql/extract/po_vs_rcv.sql (T-SQL)

    สองทางนี้คำนวณแยกกันคนละภาษา ถ้าตรงกันแปลว่าตรรกะไม่มีรูรั่ว
    """
    eng = warehouse.engine()
    sql = (config.ROOT / "sql" / "extract" / "po_vs_rcv.sql").read_text(encoding="utf-8")
    with source.connect() as cn:
        cols, rows = source.fetch(cn, sql)
    idx = {c: i for i, c in enumerate(cols)}

    erp = {
        (r[idx["PoNo"]].strip(), r[idx["PoSeq"]].strip()): (
            float(r[idx["RcvQty"]] or 0), float(r[idx["OpenQty"]] or 0)
        )
        for r in rows
    }
    mine = {
        (r["PoNo"].strip(), r["PoSeq"].strip()): (float(r["RcvQty"]), float(r["OpenQty"]))
        for r in warehouse.read(eng, "SELECT PoNo, PoSeq, RcvQty, OpenQty FROM fact_po_line")
    }

    problems: list[str] = []
    if len(erp) != len(mine):
        problems.append(f"จำนวนบรรทัดไม่เท่ากัน: T-SQL {len(erp):,} vs Python {len(mine):,}")
    for key in set(erp) | set(mine):
        a, b = erp.get(key), mine.get(key)
        if a is None or b is None:
            problems.append(f"{key[0]} บรรทัด {key[1]}: มีข้างเดียว")
        elif abs(a[0] - b[0]) >= 0.005 or abs(a[1] - b[1]) >= 0.005:
            problems.append(f"{key[0]} บรรทัด {key[1]}: รับ {a[0]} vs {b[0]} / ค้าง {a[1]} vs {b[1]}")
        if len(problems) >= 20:
            problems.append("... (ตัดแสดงแค่ 20 รายการแรก)")
            break
    return problems
