"""เทียบ fact_po_line กับไฟล์ Excel ที่ export จากรายงาน pcsr0511 ของ ERP

รายงาน pcsr0511 คือสิ่งที่จัดซื้อใช้อยู่จริง ถ้าตัวเลขของเราตรงกับมันทุกบรรทัด
ผู้ใช้จะเชื่อระบบใหม่ทันทีโดยไม่ต้องอธิบาย ไฟล์ export จึงเป็นมาตรวัดที่ดีที่สุด

คอลัมน์ในไฟล์ : refpono shpdat docno supcd supnam rem seq pdtcd pdtnam
                pdttyp unitnam shpdat1 qty qtyrcv qtybal stsnam

    python -m etl validate Tmp_Export_pcsr0511_*.xlsx
"""
from __future__ import annotations

from pathlib import Path

import openpyxl

from . import warehouse


def _load(path: Path) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    head = [str(h).strip().lower() if h else "" for h in rows[0]]
    out = []
    for r in rows[1:]:
        d = dict(zip(head, r))
        if not d.get("docno"):
            continue
        d["docno"] = str(d["docno"]).strip()
        d["seq"] = str(d["seq"]).strip()
        # stsnam มาในรูป "ปิด|Closed"
        d["sts"] = str(d.get("stsnam") or "").split("|")[0].strip()
        out.append(d)
    return out


def run(path: str) -> int:
    rep = _load(Path(path))
    eng = warehouse.engine()
    mine = {
        (r["PoNo"], r["PoSeq"]): r
        for r in warehouse.read(
            eng, "SELECT PoNo, PoSeq, OrderQty, RcvQty, OpenQty, ErpStatus FROM fact_po_line")
    }

    bad_qty = bad_rcv = bad_sts = missing = 0
    print(f"เทียบ {len(rep)} บรรทัดจากรายงาน pcsr0511\n")
    for r in rep:
        key = (r["docno"], r["seq"])
        m = mine.get(key)
        if m is None:
            print(f"  ไม่พบในคลังข้อมูล : {key[0]} บรรทัด {key[1]}")
            missing += 1
            continue
        q, qr = float(r["qty"] or 0), float(r["qtyrcv"] or 0)
        if abs(q - float(m["OrderQty"])) >= 0.005:
            print(f"  จำนวนสั่งไม่ตรง  {key[0]} บ.{key[1]} : รายงาน {q} vs เรา {m['OrderQty']}")
            bad_qty += 1
        if abs(qr - float(m["RcvQty"])) >= 0.005:
            print(f"  จำนวนรับไม่ตรง   {key[0]} บ.{key[1]} : รายงาน {qr} vs เรา {m['RcvQty']}")
            bad_rcv += 1
        if r["sts"] != m["ErpStatus"]:
            print(f"  สถานะไม่ตรง      {key[0]} บ.{key[1]} : รายงาน '{r['sts']}' vs เรา "
                  f"'{m['ErpStatus']}' (สั่ง {q} รับ {qr} ค้าง {r['qtybal']})")
            bad_sts += 1

    n = len(rep)
    print(f"\n{'ผลการเทียบ':<18} ตรง / ทั้งหมด")
    print(f"{'  จำนวนสั่ง':<18} {n - bad_qty - missing:>4} / {n}")
    print(f"{'  จำนวนรับ':<18} {n - bad_rcv - missing:>4} / {n}")
    print(f"{'  สถานะ ปิด/ค้าง':<18} {n - bad_sts - missing:>4} / {n}")
    if missing:
        print(f"  หาไม่เจอในคลัง {missing} บรรทัด")
    return 1 if (bad_qty or bad_rcv or bad_sts or missing) else 0
