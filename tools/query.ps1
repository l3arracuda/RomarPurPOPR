<#
.SYNOPSIS
  ยิง SELECT ไปที่ ERP (Romar1) แบบอ่านอย่างเดียว

.DESCRIPTION
  เครื่อง 192.168.2.2 เป็น production ที่บอบบางมาก สคริปต์นี้จึงบังคับ read-only 3 ชั้น:
    1. ตรวจคำสั่งต้องห้ามใน SQL ก่อนส่ง
    2. เปิด transaction READ UNCOMMITTED แล้ว Rollback ทุกครั้ง
    3. ApplicationIntent=ReadOnly ใน connection string
  รหัสผ่านอ่านจาก .env (ซึ่งถูก gitignore) ไม่ฝังในโค้ด

.EXAMPLE
  .\tools\query.ps1 -Sql "SELECT TOP 10 * FROM POC_POH ORDER BY DOCDAT DESC"
  .\tools\query.ps1 -File .\sql\extract\po_lines.sql -Csv .\out\po.csv
#>
param(
  [string]$Sql,
  [string]$File,
  [string]$Csv,
  [int]$Timeout = 180
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8

if (-not $Sql -and -not $File) { throw "ต้องระบุ -Sql หรือ -File อย่างใดอย่างหนึ่ง" }
if ($File) { $Sql = Get-Content -Raw -Encoding UTF8 $File }

# ---- ชั้นที่ 1: กันคำสั่งที่เปลี่ยนแปลงข้อมูล ----
$forbidden = '(?is)\b(insert|update|delete|merge|drop|alter|create|truncate|exec|execute|grant|revoke|backup|restore|sp_\w+|xp_\w+)\b'
if ($Sql -match $forbidden) {
  throw "BLOCKED: พบคำสั่งที่ไม่ใช่ SELECT ('$($Matches[1])') — สคริปต์นี้อ่านอย่างเดียว"
}

# ---- อ่าน .env ----
$envPath = Join-Path $PSScriptRoot '..\.env'
if (-not (Test-Path $envPath)) { throw "ไม่พบไฟล์ .env — คัดลอกจาก .env.example ก่อน" }
$cfg = @{}
Get-Content $envPath | Where-Object { $_ -match '^\s*[^#]\S*\s*=' } | ForEach-Object {
  $k, $v = $_ -split '=', 2
  $cfg[$k.Trim()] = $v.Trim()
}

[Net.ServicePointManager]::SecurityProtocol =
  [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls11 -bor [Net.SecurityProtocolType]::Tls

$cs = "Server=$($cfg.ERP_HOST),$($cfg.ERP_PORT);Database=$($cfg.ERP_DATABASE);" +
      "User ID=$($cfg.ERP_USER);Password=$($cfg.ERP_PASSWORD);" +
      "Connect Timeout=15;ApplicationIntent=ReadOnly"

$cn = New-Object System.Data.SqlClient.SqlConnection $cs
$cn.Open()
# ---- ชั้นที่ 2: transaction ที่ Rollback เสมอ ----
$tx = $cn.BeginTransaction([System.Data.IsolationLevel]::ReadUncommitted)
try {
  $cmd = $cn.CreateCommand()
  $cmd.Transaction = $tx
  $cmd.CommandTimeout = $Timeout
  $cmd.CommandText = $Sql
  $da = New-Object System.Data.SqlClient.SqlDataAdapter $cmd
  $ds = New-Object System.Data.DataSet
  [void]$da.Fill($ds)

  if ($Csv) {
    $dir = Split-Path -Parent $Csv
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $ds.Tables[0] | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $Csv
    Write-Host "เขียน $($ds.Tables[0].Rows.Count) แถว -> $Csv"
  } else {
    foreach ($t in $ds.Tables) { $t | Format-Table -AutoSize | Out-String -Width 400 }
  }
} finally {
  $tx.Rollback()   # ไม่มีทาง commit อะไรกลับไปที่ ERP
  $cn.Close()
}
