"""ส่องใบสั่งซื้อทีละใบแบบดิบ ๆ จาก ERP เพื่อเทียบว่า "ปิดแล้ว" ต่างจาก "ยังไม่ปิด" ตรงไหน

ดึง SELECT * ทุกคอลัมน์โดยตั้งใจ เพราะตัวบอกสถานะปิดอาจอยู่ในคอลัมน์ที่
etl/extract.py ไม่ได้ดึงมา เช่น SHIPNO, ORDNO, ShipCd, INTDES, PrNo1

    python -m etl inspect PP1-69-02519 PP1-69-02520
    python -m etl diff   --closed PP1-69-0001,PP1-69-0002 --open PP1-69-0003
"""
from __future__ import annotations

from . import source

_QUERIES = [
    ("POC_POH  (หัวใบสั่งซื้อ)", "SELECT * FROM POC_POH WHERE DOCNO = ?"),
    ("POC_POD  (รายการ)", "SELECT * FROM POC_POD WHERE DOCNO = ? ORDER BY SEQ"),
    ("POC_RCVH (ใบรับที่อ้างถึง)", "SELECT * FROM POC_RCVH WHERE PONO = ? ORDER BY DOCDAT"),
]


def _fetch_po(cn, pono: str) -> list[tuple[str, list[str], list[tuple]]]:
    out = []
    for label, sql in _QUERIES:
        cols, rows = source.fetch(cn, sql, (pono,))
        out.append((label, cols, rows))
    return out


def show(ponos: list[str]) -> None:
    with source.connect() as cn:
        for pono in ponos:
            print(f"\n{'=' * 70}\n{pono}\n{'=' * 70}")
            for label, cols, rows in _fetch_po(cn, pono):
                print(f"\n-- {label} : {len(rows)} แถว")
                for row in rows:
                    for c, v in zip(cols, row):
                        if v is not None and str(v).strip() != "":
                            print(f"     {c:<14} {v}")
                    print("     " + "-" * 40)


def _signature(cn, pono: str) -> dict[str, str]:
    """ย่อใบ PO เหลือ dict คอลัมน์ -> ค่า เฉพาะตารางหัว ใช้สำหรับหาความต่าง"""
    cols, rows = source.fetch(cn, "SELECT * FROM POC_POH WHERE DOCNO = ?", (pono,))
    if not rows:
        return {}
    return {c: ("" if v is None else str(v).strip()) for c, v in zip(cols, rows[0])}


def diff(closed: list[str], open_: list[str]) -> None:
    """หาคอลัมน์ที่แยกกลุ่ม 'ปิดแล้ว' ออกจาก 'ยังไม่ปิด' ได้ชัดเจน"""
    with source.connect() as cn:
        a = [_signature(cn, p) for p in closed]
        b = [_signature(cn, p) for p in open_]
    a = [x for x in a if x]
    b = [x for x in b if x]
    if not a or not b:
        print("หาใบสั่งซื้อไม่เจอในฝั่งใดฝั่งหนึ่ง ตรวจเลขที่อีกครั้ง")
        return

    print(f"เทียบ ปิดแล้ว {len(a)} ใบ กับ ยังไม่ปิด {len(b)} ใบ\n")
    print(f"{'คอลัมน์':<16} {'ปิดแล้ว':<28} {'ยังไม่ปิด':<28} ชี้ขาด")
    print("-" * 90)
    for col in a[0]:
        va = {x.get(col, "") for x in a}
        vb = {x.get(col, "") for x in b}
        if va == vb:
            continue
        decisive = "<<< ใช่เลย" if not (va & vb) and len(va) == 1 else ""
        sa = ", ".join(sorted(va))[:26]
        sb = ", ".join(sorted(vb))[:26]
        print(f"{col:<16} {sa:<28} {sb:<28} {decisive}")
    print("\nคอลัมน์ที่ขึ้น '<<< ใช่เลย' คือตัวที่แยกสองกลุ่มออกจากกันได้สนิท")
