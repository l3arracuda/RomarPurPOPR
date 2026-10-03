"""นิยามว่าจะดึงตารางอะไรจาก ERP บ้าง

ทุก SQL ในไฟล์นี้ต้องเป็น T-SQL ที่ SQL Server 2008 รองรับ
(ห้าม IIF / CONCAT / TRY_CONVERT / STRING_AGG / FORMAT / OFFSET-FETCH)

กลยุทธ์: โหลดใหม่ทั้งหน้าต่างเวลาทุกครั้ง (ไม่ทำ incremental)
เพราะข้อมูลในหน้าต่าง 2024+ มีไม่ถึง 300,000 แถว ดึงใหม่หมดใช้เวลาไม่กี่วินาที
แต่ได้ความถูกต้องเต็มร้อย — จับทั้งการแก้ไขและการลบเอกสาร ซึ่ง incremental
ด้วย UPDDATTIM จับไม่ได้
"""
from __future__ import annotations

from dataclasses import dataclass

# ใบ PO ที่อยู่ในหน้าต่างเวลา — ใช้ซ้ำหลายที่
_PO_IN_WINDOW = "SELECT 1 FROM POC_POH w WHERE w.DOCNO = {col} AND w.DOCDAT >= ?"


@dataclass(frozen=True)
class Spec:
    name: str          # ชื่อตารางในคลังข้อมูล
    sql: str
    nparams: int       # จำนวน ? ที่ต้องส่งวันที่เริ่มหน้าต่างเข้าไป
    pk: tuple[str, ...]


SPECS: list[Spec] = [
    Spec(
        "po_header",
        """
        SELECT LTRIM(RTRIM(DOCNO)) AS DOCNO, DOCDAT, LTRIM(RTRIM(SUPCD)) AS SUPCD, APPSTS,
               LTRIM(RTRIM(ADDUSERID)) AS Buyer, SHIPDAT, SSHIPDAT, CRTERM,
               TLTAMT, DISAMT, VATPCT, VATAMT, NETAMT, REM,
               ADDDATTIM, LTRIM(RTRIM(UPDUSERID)) AS UPDUSERID, UPDDATTIM
        FROM POC_POH WHERE DOCDAT >= ?
        """,
        1,
        ("DOCNO",),
    ),
    Spec(
        "po_detail",
        f"""
        SELECT LTRIM(RTRIM(d.DOCNO)) AS DOCNO, LTRIM(RTRIM(d.SEQ)) AS SEQ, LTRIM(RTRIM(d.PDTCD)) AS PDTCD,
               d.QTY, LTRIM(RTRIM(d.UNIT)) AS UNIT, d.PRICE, d.PACKSIZE, d.DISPCT,
               d.AMT, d.DISAMT, d.RCVQTY, d.RCVAMT, d.sShipDat, d.ShipDat
        FROM POC_POD d
        WHERE EXISTS ({_PO_IN_WINDOW.format(col='d.DOCNO')})
        """,
        1,
        ("DOCNO", "SEQ"),
    ),
    Spec(
        "rcv_header",
        f"""
        SELECT LTRIM(RTRIM(h.DOCNO)) AS DOCNO, h.DOCDAT, h.DOCTYP, LTRIM(RTRIM(h.EXTNO)) AS EXTNO,
               LTRIM(RTRIM(h.PONO)) AS PONO, LTRIM(RTRIM(h.SUPCD)) AS SUPCD, h.APPSTS,
               h.TLTAMT, h.VATAMT, h.NETAMT, h.REM,
               LTRIM(RTRIM(h.ADDUSERID)) AS Enterer, h.ADDDATTIM
        FROM POC_RCVH h
        WHERE h.DOCTYP IN ('R','T')
          AND (h.DOCDAT >= ? OR EXISTS ({_PO_IN_WINDOW.format(col='h.PONO')}))
        """,
        2,
        ("DOCNO",),
    ),
    Spec(
        "rcv_detail",
        f"""
        SELECT LTRIM(RTRIM(d.DOCNO)) AS DOCNO, LTRIM(RTRIM(d.SEQ)) AS SEQ, LTRIM(RTRIM(d.POSEQ)) AS POSEQ,
               LTRIM(RTRIM(d.PDTCD)) AS PDTCD, d.QTY, LTRIM(RTRIM(d.UNIT)) AS UNIT,
               d.PRICE, d.PACKSIZE, d.AMT, d.RetQty
        FROM POC_RCVD d
        WHERE EXISTS (
            SELECT 1 FROM POC_RCVH h
            WHERE h.DOCNO = d.DOCNO AND h.DOCTYP IN ('R','T')
              AND (h.DOCDAT >= ? OR EXISTS ({_PO_IN_WINDOW.format(col='h.PONO')}))
        )
        """,
        2,
        ("DOCNO", "SEQ"),
    ),
    Spec(
        # ที่เก็บของการรับเข้าไม่ได้อยู่ใน POC_RCVD (คอลัมน์ LOCCD ที่นั่นว่างเปล่า)
        # ต้องมาเอาจากความเคลื่อนไหวสต็อก DOCTYP=I1 ซึ่งตรงกับใบรับ 1:1 พอดี
        "rcv_location",
        """
        SELECT LTRIM(RTRIM(DOCNO)) AS DOCNO, LTRIM(RTRIM(SEQ)) AS SEQ,
               LTRIM(RTRIM(LOCCD)) AS LOCCD
        FROM INV_TRN WHERE DOCTYP = 'I1' AND DOCDAT >= ?
        """,
        1,
        ("DOCNO", "SEQ"),
    ),
    Spec(
        "supplier",
        "SELECT LTRIM(RTRIM(SUPCD)) AS SUPCD, SUPNAM, TEL, CONNAM, CRTERM, Sts FROM APC_SUP",
        0,
        ("SUPCD",),
    ),
    Spec(
        "product",
        """
        SELECT LTRIM(RTRIM(PDTCD)) AS PDTCD, PDTNAM, LTRIM(RTRIM(UNITNAM)) AS UNITNAM,
               LTRIM(RTRIM(PDTGRP)) AS PDTGRP, PDTTYP, BALQTY, BALAMT, STDCOST, LSTCOST
        FROM INV_PDT
        """,
        0,
        ("PDTCD",),
    ),
]
