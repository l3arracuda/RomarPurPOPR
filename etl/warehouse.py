"""คลังข้อมูลปลายทาง — เขียนได้ (ตรงข้ามกับ ERP ที่อ่านอย่างเดียว)

dev ใช้ SQLite ไฟล์เดียว, prod สลับเป็น SQL Server 2022 ด้วย WAREHOUSE_KIND ใน .env
โค้ดชั้นนี้ใช้ SQLAlchemy Core จึงไม่ต้องแก้อะไรตอนสลับ
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, Iterable, Sequence

from sqlalchemy import (
    Column, DateTime, Float, Integer, MetaData, String, Table, create_engine, text,
)
from sqlalchemy.engine import Engine

from . import config

_CHUNK = 1000


def engine() -> Engine:
    return create_engine(config.warehouse_url(), future=True)


def _col_type(values: Iterable[Any]):
    """เดาชนิดคอลัมน์จากค่าแรกที่ไม่ใช่ None"""
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            return Integer
        if isinstance(v, dt.datetime):
            return DateTime
        if isinstance(v, (Decimal, float)):
            return Float
        if isinstance(v, int):
            return Integer
        return String(400)
    return String(400)


def replace_table(
    eng: Engine, name: str, cols: Sequence[str], rows: Sequence[tuple],
    pk: Sequence[str] = (),
) -> int:
    """ลบตารางเดิมแล้วเขียนใหม่ทั้งหมด — idempotent รันซ้ำได้ผลเท่าเดิม"""
    md = MetaData()
    columns = [
        Column(c, _col_type(r[i] for r in rows), primary_key=(c in pk))
        for i, c in enumerate(cols)
    ]
    tbl = Table(name, md, *columns)
    with eng.begin() as cn:
        tbl.drop(cn, checkfirst=True)
        tbl.create(cn)
        for start in range(0, len(rows), _CHUNK):
            chunk = rows[start : start + _CHUNK]
            cn.execute(
                tbl.insert(),
                [
                    {c: (float(v) if isinstance(v, Decimal) else v)
                     for c, v in zip(cols, row)}
                    for row in chunk
                ],
            )
    return len(rows)


def index(eng: Engine, table: str, cols: Sequence[str], name: str | None = None) -> None:
    idx = name or f"ix_{table}_{'_'.join(cols)}"
    col_list = ", ".join(f'"{c}"' for c in cols)
    # SQL Server ไม่รองรับ CREATE INDEX IF NOT EXISTS (แม้แต่ 2022)
    # แต่เราสร้างตารางใหม่ทุกรอบอยู่แล้ว index เดิมจึงหายไปด้วย ไม่ชนกัน
    guard = "IF NOT EXISTS " if eng.dialect.name == "sqlite" else ""
    with eng.begin() as cn:
        cn.execute(text(f'CREATE INDEX {guard}{idx} ON "{table}" ({col_list})'))


def read(eng: Engine, sql: str, params: dict | None = None) -> list[dict]:
    with eng.connect() as cn:
        res = cn.execute(text(sql), params or {})
        return [dict(r._mapping) for r in res]
