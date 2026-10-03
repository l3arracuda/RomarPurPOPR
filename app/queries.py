"""คิวรีสำหรับเว็บแอป — อ่านจากคลังข้อมูลในเครื่องเท่านั้น ไม่แตะ ERP"""
from __future__ import annotations

import datetime as dt

from etl import warehouse


def _range(date_from: str, date_to: str) -> dict:
    return {"a": date_from, "b": (dt.date.fromisoformat(date_to) + dt.timedelta(days=1)).isoformat()}


def _filters(supplier: str, buyer: str, q: str, prefix: str = "") -> tuple[str, dict]:
    where, params = "", {}
    if supplier:
        where += f" AND {prefix}SupCd = :sup"
        params["sup"] = supplier
    if buyer:
        where += f" AND {prefix}Buyer = :buy"
        params["buy"] = buyer
    if q:
        where += (f" AND ({prefix}PdtCd LIKE :q OR {prefix}PdtNam LIKE :q"
                  f" OR {prefix}PoNo LIKE :q OR {prefix}SupNam LIKE :q)")
        params["q"] = f"%{q}%"
    return where, params


def summary(date_from: str, date_to: str) -> dict:
    eng = warehouse.engine()
    p = _range(date_from, date_to)

    po = warehouse.read(eng, """
        SELECT COUNT(DISTINCT PoNo) docs, COUNT(*) lines, SUM(OrderAmt) amt
        FROM fact_po_line WHERE PoDat >= :a AND PoDat < :b""", p)[0]
    rcv = warehouse.read(eng, """
        SELECT COUNT(DISTINCT RcvNo) docs, COUNT(*) lines, SUM(Amt) amt
        FROM fact_rcv_line WHERE RcvDat >= :a AND RcvDat < :b AND DocTyp = 'R'""", p)[0]
    ret = warehouse.read(eng, """
        SELECT COUNT(*) lines, SUM(Amt) amt FROM fact_rcv_line
        WHERE RcvDat >= :a AND RcvDat < :b AND DocTyp = 'T'""", p)[0]
    op = warehouse.read(eng, """
        SELECT COUNT(*) lines, SUM(OpenAmt) amt,
               SUM(CASE WHEN OverdueDays > 0 THEN 1 ELSE 0 END) od_lines,
               SUM(CASE WHEN OverdueDays > 0 THEN OpenAmt ELSE 0 END) od_amt
        FROM fact_po_line WHERE IsOpen = 1 AND DocKind = 'ใบสั่งซื้อ'""")[0]
    ontime = warehouse.read(eng, """
        SELECT SUM(CASE WHEN DaysLate <= 0 THEN 1 ELSE 0 END) ok, COUNT(*) n
        FROM fact_rcv_line
        WHERE RcvDat >= :a AND RcvDat < :b AND DocTyp = 'R' AND DaysLate IS NOT NULL""", p)[0]
    dq = warehouse.read(eng, """
        SELECT CheckName, Severity, Description, COUNT(*) n
        FROM dq_issue GROUP BY CheckName, Severity, Description ORDER BY n DESC""")

    return {
        "po": po, "rcv": rcv, "ret": ret, "open": op,
        "ontime_pct": (ontime["ok"] / ontime["n"]) if ontime["n"] else None,
        "ontime_n": ontime["n"],
        "dq": dq,
    }


def monthly(months: int = 12) -> list[dict]:
    eng = warehouse.engine()
    po = {r["PoYm"]: r for r in warehouse.read(eng, """
        SELECT PoYm, SUM(OrderAmt) amt, COUNT(DISTINCT PoNo) docs
        FROM fact_po_line WHERE PoYm IS NOT NULL GROUP BY PoYm""")}
    rc = {r["RcvYm"]: r for r in warehouse.read(eng, """
        SELECT RcvYm, SUM(Amt) amt, COUNT(DISTINCT RcvNo) docs
        FROM fact_rcv_line WHERE RcvYm IS NOT NULL GROUP BY RcvYm""")}
    keys = sorted(set(po) | set(rc))[-months:]
    return [{
        "ym": k,
        "po_amt": float((po.get(k) or {}).get("amt") or 0),
        "po_docs": int((po.get(k) or {}).get("docs") or 0),
        "rcv_amt": float((rc.get(k) or {}).get("amt") or 0),
        "rcv_docs": int((rc.get(k) or {}).get("docs") or 0),
    } for k in keys]


def receipts(date_from, date_to, supplier="", buyer="", q="", limit=5000) -> list[dict]:
    eng = warehouse.engine()
    p = _range(date_from, date_to)
    # fact_rcv_line ไม่มีคอลัมน์ Buyer จึงกรองผู้สั่งซื้อผ่านใบ PO
    where, fp = _filters(supplier, "", q)
    if buyer:
        where += " AND PoNo IN (SELECT PoNo FROM fact_po_line WHERE Buyer = :buy)"
        fp["buy"] = buyer
    return warehouse.read(eng, f"""
        SELECT * FROM fact_rcv_line
        WHERE RcvDat >= :a AND RcvDat < :b {where}
        ORDER BY RcvDat DESC, RcvNo, RcvSeq LIMIT {int(limit)}""", {**p, **fp})


def open_po(supplier="", buyer="", q="", overdue_only=False, kind="ใบสั่งซื้อ",
            limit=5000) -> list[dict]:
    eng = warehouse.engine()
    where, fp = _filters(supplier, buyer, q)
    if kind:
        where += " AND DocKind = :kind"
        fp["kind"] = kind
    if overdue_only:
        where += " AND OverdueDays > 0"
    return warehouse.read(eng, f"""
        SELECT * FROM fact_po_line WHERE IsOpen = 1 {where}
        ORDER BY ShipDat, PoNo, PoSeq LIMIT {int(limit)}""", fp)


def suppliers() -> list[dict]:
    return warehouse.read(warehouse.engine(), """
        SELECT SupCd, SupNam, COUNT(*) n FROM fact_po_line
        WHERE SupNam IS NOT NULL GROUP BY SupCd, SupNam ORDER BY SupNam""")


def buyers() -> list[dict]:
    return warehouse.read(warehouse.engine(), """
        SELECT Buyer, COUNT(*) n FROM fact_po_line
        WHERE Buyer IS NOT NULL AND Buyer <> '' GROUP BY Buyer ORDER BY Buyer""")


def data_range() -> dict:
    r = warehouse.read(warehouse.engine(), """
        SELECT MIN(RcvDat) lo, MAX(RcvDat) hi FROM fact_rcv_line""")[0]
    return {"lo": str(r["lo"] or "")[:10], "hi": str(r["hi"] or "")[:10]}
