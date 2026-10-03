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

ติดตั้งครั้งแรก:

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

ดึงข้อมูลเข้าคลัง แล้วตรวจว่าตรรกะถูกต้อง:

```powershell
.\.venv\Scripts\python -m etl sync
.\.venv\Scripts\python -m etl verify
```

`sync` ใช้เวลาประมาณ 16 วินาที โหลดใหม่ทั้งหน้าต่าง 2024+ ทุกรอบ จึงรันซ้ำได้ผลเท่าเดิมเสมอ
`verify` เทียบผลลัพธ์ฝั่ง Python กับ T-SQL ทีละบรรทัด ถ้าตรรกะสองทางไม่ตรงกันจะฟ้องทันที

ยิง SQL ดูข้อมูลดิบแบบ read-only:

```powershell
.	ools\query.ps1 -Sql "SELECT TOP 5 DOCNO, DOCDAT FROM POC_POH ORDER BY DOCDAT DESC"
.	ools\query.ps1 -File .\sql\extract\po_vs_rcv.sql -Csv .\out\po_vs_rcv.csv
```

## สถานะโครงการ

- [x] **เฟส 0** — Discovery: หาตารางจริง ยืนยันคีย์จับคู่ ตรวจคุณภาพข้อมูล
- [x] SQL แกนกลาง `sql/extract/po_vs_rcv.sql` (ตรวจแล้ว 23,782 บรรทัด ปี 2024+)
- [x] **เฟส 1** — ETL เข้าคลังข้อมูล (16 วินาที/รอบ) + cross-check Python vs T-SQL ผ่าน
- [ ] **เฟส 2** — รายงานค้างรับ + รับเข้ารายวัน (Excel)
- [ ] **เฟส 3** — เว็บ Dashboard + ปุ่ม Export
- [ ] **เฟส 4** — อีเมลสรุปอัตโนมัติ

## โครงสร้าง

```
docs/     เอกสารออกแบบและพจนานุกรมข้อมูล
sql/      SQL ดึงข้อมูล (2008-compatible)
tools/    เครื่องมือ read-only
etl/      ดึงข้อมูลเข้าคลัง + ประกอบตาราง fact_po_line
app/      เว็บแอป (เฟส 3)
data/     คลังข้อมูล SQLite — gitignore ไว้
out/      ผลลัพธ์ที่ดึงมา — gitignore ไว้
```
