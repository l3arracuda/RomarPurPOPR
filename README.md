# RomarPurPOPR — ระบบติดตามการสั่งซื้อและรับเข้า

รายงานสำหรับ**ฝ่ายจัดซื้อ** ให้เห็นว่า "สั่งซื้อไปเท่าไหร่ ของเข้ามาแล้วเท่าไหร่ ยังค้างอยู่เท่าไหร่"
ซึ่งปัจจุบันดูไม่ได้ เพราะเอกสารรับเข้าวิ่งจากสต็อกไปบัญชีโดยตรง จัดซื้อไม่เห็นข้อมูล

| | |
|---|---|
| ต้นทาง | ROM ERP — SQL Server 2008 `192.168.2.2` / `Romar1` |
| ปลายทาง (production) | SQL Server 2022 |
| เอกสาร | [ออกแบบระบบ](docs/design.md) · [พจนานุกรมข้อมูล](docs/data-dictionary.md) |

## 🔴 กฎเหล็ก

> **ห้าม INSERT / UPDATE / DELETE / DDL ใด ๆ กับ `192.168.2.2` โดยเด็ดขาด**
> เป็น production ที่บอบบาง ระบบนี้ **อ่านอย่างเดียว** เท่านั้น

บังคับด้วยโค้ด 3 ชั้นใน [`tools/query.ps1`](tools/query.ps1):
1. ตรวจจับคำสั่งที่ไม่ใช่ `SELECT` แล้วโยน error ก่อนส่งถึง server
2. ครอบ transaction `READ UNCOMMITTED` และ `Rollback()` ทุกครั้งใน `finally`
3. `ApplicationIntent=ReadOnly` ใน connection string

นอกจากนี้ SQL ทุกบรรทัดที่ยิงไปต้องเป็น **T-SQL ที่ SQL Server 2008 รองรับ**
(ห้าม `IIF`, `CONCAT`, `TRY_CONVERT`, `STRING_AGG`, `FORMAT`, `OFFSET/FETCH` — ล้วนเป็น 2012+)

## เริ่มใช้งาน

```powershell
copy .env.example .env     # แล้วใส่ค่าจริง  ( .env ถูก gitignore ไว้ )
.\tools\query.ps1 -Sql "SELECT TOP 5 DOCNO, DOCDAT FROM POC_POH ORDER BY DOCDAT DESC"
.\tools\query.ps1 -File .\sql\extract\po_vs_rcv.sql -Csv .\out\po_vs_rcv.csv
```

## สถานะโครงการ

- [x] **เฟส 0** — Discovery: หาตารางจริง ยืนยันคีย์จับคู่ ตรวจคุณภาพข้อมูล
- [x] SQL แกนกลาง `sql/extract/po_vs_rcv.sql` (ตรวจแล้ว 23,778 บรรทัด ปี 2024+)
- [ ] **เฟส 1** — ETL เข้าคลังข้อมูล
- [ ] **เฟส 2** — รายงานค้างรับ + รับเข้ารายวัน (Excel)
- [ ] **เฟส 3** — เว็บ Dashboard + ปุ่ม Export
- [ ] **เฟส 4** — อีเมลสรุปอัตโนมัติ

## โครงสร้าง

```
docs/     เอกสารออกแบบและพจนานุกรมข้อมูล
sql/      SQL ดึงข้อมูล (2008-compatible)
tools/    เครื่องมือ read-only
app/      เว็บแอป (เฟส 3)
out/      ผลลัพธ์ที่ดึงมา — gitignore ไว้
```
