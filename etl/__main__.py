"""python -m etl sync   |   python -m etl verify"""
from __future__ import annotations

import argparse

from . import config, inspect as inspect_po, report, sync, validate as validate_rep


def main() -> int:
    ap = argparse.ArgumentParser(prog="etl", description="ดึงข้อมูลจัดซื้อจาก ROM ERP")
    ap.add_argument("command", choices=["sync", "verify", "inspect", "diff", "validate", "report"])
    ap.add_argument("pono", nargs="*", help="เลขที่ใบสั่งซื้อ (สำหรับ inspect)")
    ap.add_argument("--from", dest="dfrom", default="", help="วันเริ่ม (R1)")
    ap.add_argument("--to", dest="dto", default="", help="วันสิ้นสุด (R1)")
    ap.add_argument("--supplier", default="", help="กรองผู้ขาย (R2)")
    ap.add_argument("--buyer", default="", help="กรองผู้สั่งซื้อ (R2)")
    ap.add_argument("-o", "--out", default="", help="ชื่อไฟล์ผลลัพธ์")
    ap.add_argument("--closed", default="", help="เลขที่ PO ที่ปิดแล้ว คั่นด้วยจุลภาค")
    ap.add_argument("--open", dest="open_", default="", help="เลขที่ PO ที่ยังไม่ปิด")
    ap.add_argument("--since", default=config.DEFAULT_WINDOW_START,
                    help=f"วันเริ่มหน้าต่างข้อมูล (ค่าเริ่มต้น {config.DEFAULT_WINDOW_START})")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="ผ่อนผันตอนตัดสินป้ายสถานะ 0.02 = บวกลบ 2%%")
    args = ap.parse_args()

    if args.command == "report":
        import datetime as _dt
        which = (args.pono[0] if args.pono else "r2").lower()
        if which == "r1":
            dto = args.dto or _dt.date.today().isoformat()
            dfrom = args.dfrom or (_dt.date.fromisoformat(dto) - _dt.timedelta(days=30)).isoformat()
            report.r1(dfrom, dto, args.out or None)
        else:
            report.r2(args.out or None, args.supplier, args.buyer)
        return 0

    if args.command == "validate":
        return validate_rep.run(args.pono[0])

    if args.command == "inspect":
        inspect_po.show(args.pono)
        return 0

    if args.command == "diff":
        split = lambda v: [x.strip() for x in v.split(",") if x.strip()]
        inspect_po.diff(split(args.closed), split(args.open_))
        return 0

    if args.command == "sync":
        print(f"ดึงข้อมูลตั้งแต่ {args.since}")
        counts = sync.run(args.since, args.tolerance)
        print(f"เสร็จใน {counts.pop('_seconds')} วินาที")
        return 0

    problems = sync.verify(args.since)
    if problems:
        print("พบความไม่ตรงกันระหว่าง T-SQL กับ Python:")
        for p in problems:
            print("  -", p)
        return 1
    print("ตรวจผ่าน: ตรรกะฝั่ง Python ตรงกับ T-SQL ทุกบรรทัด")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
