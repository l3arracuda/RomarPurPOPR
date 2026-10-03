"""ตั้งค่าการเชื่อมต่อ อ่านจาก .env"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ช่วงข้อมูลที่ดึง — ปี 2021-2023 หายจากไวรัส ข้อมูลที่ใช้ได้เริ่มที่ 2024
DEFAULT_WINDOW_START = "2024-01-01"


@dataclass(frozen=True)
class ErpConfig:
    """ต้นทาง ROM ERP — อ่านอย่างเดียวเท่านั้น"""

    host: str
    port: str
    database: str
    user: str
    password: str
    driver: str

    @property
    def odbc(self) -> str:
        return (
            f"DRIVER={{{self.driver}}};SERVER={self.host},{self.port};"
            f"DATABASE={self.database};UID={self.user};PWD={self.password};"
            "TrustServerCertificate=yes;Connection Timeout=15"
        )


def erp() -> ErpConfig:
    missing = [k for k in ("ERP_HOST", "ERP_DATABASE", "ERP_USER") if not os.getenv(k)]
    if missing:
        raise SystemExit(f"ขาดค่าใน .env: {', '.join(missing)} (คัดลอกจาก .env.example)")
    return ErpConfig(
        host=os.getenv("ERP_HOST", ""),
        port=os.getenv("ERP_PORT", "1433"),
        database=os.getenv("ERP_DATABASE", "Romar1"),
        user=os.getenv("ERP_USER", ""),
        password=os.getenv("ERP_PASSWORD", ""),
        driver=os.getenv("ERP_DRIVER", "ODBC Driver 17 for SQL Server"),
    )


def warehouse_url() -> str:
    """คลังข้อมูลปลายทาง — dev=sqlite, prod=SQL Server 2022 (สลับด้วย .env)"""
    kind = os.getenv("WAREHOUSE_KIND", "sqlite").lower()
    if kind == "sqlite":
        path = Path(os.getenv("WAREHOUSE_PATH", "./data/purchase.sqlite"))
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{path}"
    if kind == "mssql":
        drv = os.getenv("ERP_DRIVER", "ODBC Driver 17 for SQL Server").replace(" ", "+")
        return (
            f"mssql+pyodbc://{os.getenv('WH_USER')}:{os.getenv('WH_PASSWORD')}"
            f"@{os.getenv('WH_HOST')}/{os.getenv('WH_DATABASE')}"
            f"?driver={drv}&TrustServerCertificate=yes"
        )
    raise SystemExit(f"WAREHOUSE_KIND ไม่รู้จัก: {kind} (ใช้ sqlite หรือ mssql)")
