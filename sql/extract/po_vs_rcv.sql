/* ============================================================
   po_vs_rcv.sql  —  ชุดข้อมูลแกนกลาง: PO ทุกบรรทัด + ยอดรับจริง
   ------------------------------------------------------------
   ต้นทาง : Romar1 @ 192.168.2.2  (SQL Server 2008)  READ-ONLY
   รองรับ : T-SQL 2008 เท่านั้น (ห้าม IIF / CONCAT / TRY_CONVERT /
            STRING_AGG / FORMAT / OFFSET-FETCH)

   หลักการสำคัญ
     - ยอดรับคำนวณจาก POC_RCVD เสมอ ไม่ใช้ POC_POD.RCVQTY
       (ตรวจแล้วเพี้ยน 599 / 23,778 บรรทัด = 2.5%)
     - DOCTYP 'R' = รับเข้า, 'T' = ส่งคืน (QTY ติดลบอยู่แล้ว)
       รวมทั้งสองประเภท -> ได้ยอดรับสุทธิทันที
     - จับคู่ด้วย RCVH.PONO + RCVD.POSEQ = POD.DOCNO + POD.SEQ
       (ตรวจแล้ว orphan = 0 แถว)
     - 1899-12-30 คือวันที่ว่างของระบบเดิม ต้องแปลงเป็น NULL
     - ห้ามครอบฟังก์ชันบนคอลัมน์ที่ใช้ join เด็ดขาด เครื่อง 2008 จะเลิกใช้ index
       แล้ว scan เต็มตาราง ทำให้ query ค้างเป็นสิบนาที (เคยเจอมาแล้ว)
   ============================================================ */

DECLARE @FromDat datetime, @ToDat datetime, @Tol float;
SET @FromDat = '2024-01-01';   /* ช่วงวันที่ของใบสั่งซื้อ */
SET @ToDat   = '2099-12-31';
SET @Tol     = 0.02;           /* ผ่อนผัน 2% สำหรับงานผ้า/ม้วน */

WITH rcv AS (
    SELECT
        h.PONO                       AS PoNo,
        d.POSEQ                      AS PoSeq,
        SUM(d.QTY)                   AS RcvQtyNet,
        SUM(CASE WHEN h.DOCTYP = 'R' THEN d.QTY ELSE 0 END)  AS RcvQtyGross,
        SUM(CASE WHEN h.DOCTYP = 'T' THEN d.QTY ELSE 0 END)  AS RetQty,
        MIN(CASE WHEN h.DOCTYP = 'R' THEN h.DOCDAT END)      AS FirstRcvDat,
        MAX(CASE WHEN h.DOCTYP = 'R' THEN h.DOCDAT END)      AS LastRcvDat,
        COUNT(DISTINCT CASE WHEN h.DOCTYP = 'R' THEN h.DOCNO END) AS RcvDocCount
    FROM POC_RCVH h
    JOIN POC_RCVD d ON d.DOCNO = h.DOCNO
    WHERE h.DOCTYP IN ('R', 'T')
    GROUP BY h.PONO, d.POSEQ
)
SELECT
    /* ---- ใบสั่งซื้อ ---- */
    LTRIM(RTRIM(ph.DOCNO))                         AS PoNo,
    ph.DOCDAT                               AS PoDat,
    ph.APPSTS                               AS PoStatus,
    LTRIM(RTRIM(ph.ADDUSERID))                     AS Buyer,
    LTRIM(RTRIM(ph.SUPCD))                         AS SupCd,
    LTRIM(RTRIM(ISNULL(s.SUPNAM, '')))             AS SupNam,
    LTRIM(RTRIM(pd.SEQ))                           AS PoSeq,
    LTRIM(RTRIM(pd.PDTCD))                         AS PdtCd,
    LTRIM(RTRIM(ISNULL(p.PDTNAM, '')))             AS PdtNam,
    LTRIM(RTRIM(ISNULL(p.PDTGRP, '')))             AS PdtGrp,
    NULLIF(pd.ShipDat,  '1899-12-30')       AS ShipDat,
    NULLIF(pd.sShipDat, '1899-12-30')       AS ShipDatOrig,

    /* ---- จำนวน / มูลค่า (ก่อน VAT) ---- */
    pd.QTY                                  AS OrderQty,
    LTRIM(RTRIM(ISNULL(pd.UNIT, '')))              AS Unit,
    ISNULL(pd.PACKSIZE, 1)                  AS PackSize,
    pd.PRICE                                AS Price,
    pd.AMT                                  AS OrderAmt,
    ISNULL(r.RcvQtyNet, 0)                  AS RcvQty,
    ISNULL(r.RcvQtyNet, 0) * pd.PRICE       AS RcvAmt,
    ISNULL(r.RetQty, 0)                     AS RetQty,
    CASE WHEN pd.QTY - ISNULL(r.RcvQtyNet, 0) > 0
         THEN pd.QTY - ISNULL(r.RcvQtyNet, 0) ELSE 0 END          AS OpenQty,
    CASE WHEN pd.QTY - ISNULL(r.RcvQtyNet, 0) > 0
         THEN (pd.QTY - ISNULL(r.RcvQtyNet, 0)) * pd.PRICE ELSE 0 END AS OpenAmt,
    CASE WHEN pd.QTY = 0 THEN NULL
         ELSE ISNULL(r.RcvQtyNet, 0) / pd.QTY END                 AS FillPct,

    /* ---- สถานะบรรทัด ---- */
    CASE
        WHEN ph.APPSTS = 'A'                                   THEN N'รออนุมัติ'
        WHEN ph.APPSTS IN ('C','T')                            THEN N'ยกเลิก'
        WHEN ISNULL(r.RcvQtyNet, 0) <= 0                       THEN N'ยังไม่รับ'
        WHEN ISNULL(r.RcvQtyNet, 0) > pd.QTY * (1 + @Tol)      THEN N'รับเกิน'
        WHEN ISNULL(r.RcvQtyNet, 0) >= pd.QTY * (1 - @Tol)     THEN N'รับครบ'
        ELSE                                                        N'รับบางส่วน'
    END                                     AS LineStatus,

    /* ---- เวลา ---- */
    r.FirstRcvDat,
    r.LastRcvDat,
    ISNULL(r.RcvDocCount, 0)                AS RcvDocCount,
    DATEDIFF(day, ph.DOCDAT, r.FirstRcvDat)                     AS LeadTimeDays,
    DATEDIFF(day, NULLIF(pd.ShipDat, '1899-12-30'), r.FirstRcvDat) AS DaysLate,
    CASE WHEN ISNULL(r.RcvQtyNet, 0) < pd.QTY * (1 - @Tol)
           AND NULLIF(pd.ShipDat, '1899-12-30') < GETDATE()
         THEN DATEDIFF(day, pd.ShipDat, GETDATE()) END          AS OverdueDays,

    /* ---- ธงตรวจสอบคุณภาพข้อมูล ---- */
    ISNULL(pd.RCVQTY, 0)                    AS ErpRcvQty,
    CASE WHEN ABS(ISNULL(pd.RCVQTY,0) - ISNULL(r.RcvQtyNet,0)) >= 0.005
         THEN 1 ELSE 0 END                  AS ErpRcvQtyMismatch

FROM POC_POD pd
JOIN POC_POH ph ON ph.DOCNO = pd.DOCNO
LEFT JOIN rcv     r ON r.PoNo = pd.DOCNO AND r.PoSeq = pd.SEQ
LEFT JOIN APC_SUP s ON s.SUPCD = ph.SUPCD
LEFT JOIN INV_PDT p ON p.PDTCD = pd.PDTCD
WHERE ph.DOCDAT >= @FromDat AND ph.DOCDAT < @ToDat
ORDER BY ph.DOCDAT DESC, ph.DOCNO, pd.SEQ;
