"""python -m etl sync   |   python -m etl verify"""
from __future__ import annotations

import argparse

from . import config, sync


def main() -> int:
    ap = argparse.ArgumentParser(prog="etl", description="ดึงข้อมูลจัดซื้อจาก ROM ERP")
    ap.add_argument("command", choices=["sync", "verify"])
    ap.add_argument("--since", default=config.DEFAULT_WINDOW_START,
                    help=f"วันเริ่มหน้าต่างข้อมูล (ค่าเริ่มต้น {config.DEFAULT_WINDOW_START})")
    ap.add_argument("--tolerance", type=float, default=0.02,
                    help="ผ่อนผันตอนตัดสินป้ายสถานะ 0.02 = บวกลบ 2%%")
    args = ap.parse_args()

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
