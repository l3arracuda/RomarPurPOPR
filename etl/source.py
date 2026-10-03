"""อ่านข้อมูลจาก ROM ERP

เครื่อง 192.168.2.2 เป็น production ที่บอบบางมาก โมดูลนี้จึงบังคับ read-only
และห้ามมีที่ไหนในโปรเจคเปิด connection ไป ERP นอกจากผ่านไฟล์นี้
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import pyodbc

from . import config

# คำสั่งที่เปลี่ยนแปลงข้อมูล — เจอเมื่อไหร่ให้ล้มทันทีก่อนส่งถึง server
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute"
    r"|grant|revoke|backup|restore|sp_\w+|xp_\w+)\b",
    re.IGNORECASE,
)


class ReadOnlyViolation(RuntimeError):
    """มีคนพยายามยิงคำสั่งที่ไม่ใช่ SELECT ไปที่ ERP"""


def _assert_read_only(sql: str) -> None:
    hit = _FORBIDDEN.search(sql)
    if hit:
        raise ReadOnlyViolation(
            f"บล็อกคำสั่ง '{hit.group(1)}' — ห้ามเขียนข้อมูลลง ERP โดยเด็ดขาด"
        )


@contextmanager
def connect() -> Iterator[pyodbc.Connection]:
    cfg = config.erp()
    cn = pyodbc.connect(cfg.odbc, autocommit=False, readonly=True)
    try:
        cn.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        yield cn
    finally:
        # ไม่ commit เด็ดขาด ถึงจะไม่มีอะไรให้ commit ก็ตาม
        cn.rollback()
        cn.close()


def fetch(
    cn: pyodbc.Connection, sql: str, params: Sequence[Any] = ()
) -> tuple[list[str], list[tuple]]:
    """ยิง SELECT แล้วคืน (ชื่อคอลัมน์, แถว)"""
    _assert_read_only(sql)
    cur = cn.cursor()
    cur.execute(sql, *params) if params else cur.execute(sql)
    cols = [c[0] for c in cur.description]
    rows = [tuple(r) for r in cur.fetchall()]
    cur.close()
    return cols, rows
