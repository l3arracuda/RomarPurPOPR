const $ = s => document.querySelector(s);
const el = (t, c, x) => { const n = document.createElement(t); if (c) n.className = c;
  if (x !== undefined) n.textContent = x; return n; };
const num = (v, d = 2) => v === null || v === undefined || v === "" ? "" :
  Number(v).toLocaleString("th-TH", { minimumFractionDigits: d, maximumFractionDigits: d });
const int = v => v === null || v === undefined ? "" : Number(v).toLocaleString("th-TH");
const date = v => { if (!v) return ""; const d = new Date(v);
  return isNaN(d) ? String(v).slice(0, 10) :
    `${String(d.getDate()).padStart(2,"0")}/${String(d.getMonth()+1).padStart(2,"0")}/${d.getFullYear()}`; };
const baht = v => num(v, 2) + " ฿";

let TAB = "overview", SORT = { receipts: null, open: null, po: null }, CACHE = {};

const RCV_COLS = [
  ["วันที่รับ","RcvDat","date"], ["เลขที่ใบรับ","RcvNo"], ["ประเภท","DocTypName"],
  ["เลขที่ PO","PoNo"], ["วันที่ PO","PoDat","date"], ["ผู้ขาย","SupNam"],
  ["รหัสสินค้า","PdtCd"], ["ชื่อสินค้า","PdtNam"], ["จำนวนรับ","Qty","num"],
  ["หน่วย","Unit"], ["ราคา","Price","num"], ["มูลค่า","Amt","num"],
  ["ที่เก็บ","LocCd"], ["กำหนดส่ง","ShipDat","date"], ["ช้า(วัน)","DaysLate","int"],
  ["เอกสารผู้ขาย","SupDocNo"], ["ผู้บันทึก","Enterer"], ["หมายเหตุ","Rem"],
];
const OPEN_COLS = [
  ["เลขที่ PO","PoNo"], ["ชนิดเอกสาร","DocKind"], ["วันที่ PO","PoDat","date"], ["ผู้สั่ง","Buyer"],
  ["ผู้ขาย","SupNam"], ["ลำดับ","PoSeq"], ["รหัสสินค้า","PdtCd"], ["ชื่อสินค้า","PdtNam"],
  ["กำหนดส่ง","ShipDat","date"], ["จำนวนสั่ง","OrderQty","num"], ["รับแล้ว","RcvQty","num"],
  ["ส่งคืน","RetQty","num"], ["คงค้าง","OpenQty","num"], ["หน่วย","Unit"],
  ["มูลค่าค้าง","OpenAmt","num"], ["%รับ","FillPct","pct"], ["สถานะ","LineStatus"],
  ["เกินกำหนด(วัน)","OverdueDays","int"], ["รับล่าสุด","LastRcvDat","date"],
];

function fmt(v, kind) {
  if (kind === "date") return date(v);
  if (kind === "num") return num(v);
  if (kind === "int") return int(v);
  if (kind === "pct") return v == null ? "" : (Number(v) * 100).toFixed(1) + "%";
  return v == null ? "" : String(v);
}

function table(node, cols, rows, key) {
  node.innerHTML = "";
  const thead = el("thead"), tr = el("tr");
  cols.forEach(([title, field]) => {
    const th = el("th", null, title);
    if (SORT[key] && SORT[key].f === field) th.textContent = title + (SORT[key].d > 0 ? " ▲" : " ▼");
    th.onclick = () => {
      const cur = SORT[key];
      SORT[key] = { f: field, d: cur && cur.f === field ? -cur.d : 1 };
      render();
    };
    tr.appendChild(th);
  });
  thead.appendChild(tr); node.appendChild(thead);

  const s = SORT[key];
  let data = rows.slice();
  if (s) data.sort((a, b) => {
    const x = a[s.f], y = b[s.f];
    if (x == null) return 1; if (y == null) return -1;
    const nx = Number(x), ny = Number(y);
    const c = (!isNaN(nx) && !isNaN(ny) && x !== "" && y !== "") ? nx - ny : String(x).localeCompare(String(y), "th");
    return c * s.d;
  });

  const tb = el("tbody");
  data.forEach(r => {
    const row = el("tr");
    if (Number(r.OverdueDays) > 0) row.className = "overdue";
    cols.forEach(([, field, kind]) => {
      const td = el("td", ["num", "int", "pct"].includes(kind) ? "num" : null, fmt(r[field], kind));
      row.appendChild(td);
    });
    tb.appendChild(row);
  });
  node.appendChild(tb);
}

function kpis(s) {
  const box = $("#kpis"); box.innerHTML = "";
  const add = (k, v, sub, cls) => {
    const d = el("div", "kpi" + (cls ? " " + cls : ""));
    d.append(el("div", "k", k), el("div", "v", v), el("div", "s", sub || ""));
    box.appendChild(d);
  };
  add("มูลค่าสั่งซื้อในช่วง", baht(s.po.amt), `${int(s.po.docs)} ใบ · ${int(s.po.lines)} บรรทัด`);
  add("มูลค่ารับเข้าในช่วง", baht(s.rcv.amt), `${int(s.rcv.docs)} ใบ · ${int(s.rcv.lines)} บรรทัด`);
  add("ส่งคืนในช่วง", baht(s.ret.amt), `${int(s.ret.lines)} บรรทัด`);
  add("ค้างรับทั้งหมด", baht(s.open.amt), `${int(s.open.lines)} บรรทัด (ณ ปัจจุบัน)`);
  add("ค้างเกินกำหนด", baht(s.open.od_amt), `${int(s.open.od_lines)} บรรทัด`, "bad");
  add("ส่งตรงเวลา",
      s.ontime_pct == null ? "—" : (s.ontime_pct * 100).toFixed(1) + "%",
      `จากใบรับ ${int(s.ontime_n)} บรรทัดในช่วง`,
      s.ontime_pct != null && s.ontime_pct >= 0.8 ? "good" : "");
}

function chart(rows) {
  const box = $("#chart"); box.innerHTML = "";
  const max = Math.max(1, ...rows.map(r => Math.max(r.po_amt, r.rcv_amt)));
  const bars = el("div", "bars");
  rows.forEach(r => {
    const g = el("div", "bargrp"), pair = el("div", "pair");
    const b1 = el("div", "bar1"), b2 = el("div", "bar2");
    b1.style.height = (r.po_amt / max * 100) + "%";
    b2.style.height = (r.rcv_amt / max * 100) + "%";
    b1.title = `สั่ง ${baht(r.po_amt)} (${r.po_docs} ใบ)`;
    b2.title = `รับ ${baht(r.rcv_amt)} (${r.rcv_docs} ใบ)`;
    pair.append(b1, b2); g.append(pair, el("div", "barlbl", r.ym.slice(2)));
    bars.appendChild(g);
  });
  const lg = el("div", "legend");
  lg.innerHTML = '<span><i style="background:#2f5496"></i>มูลค่าสั่งซื้อ</span>' +
                 '<span><i style="background:#7aa0dd"></i>มูลค่ารับเข้า</span>';
  box.append(bars, lg);
}

function dq(rows) {
  const box = $("#dq"); box.innerHTML = "";
  if (!rows.length) { box.append(el("div", "muted small", "ไม่พบความผิดปกติ")); return; }
  rows.forEach(r => {
    const d = el("div", "dqrow");
    d.append(el("span", "sev " + r.Severity, r.Severity),
             el("span", null, r.Description),
             el("span", "dqn", int(r.n)));
    box.appendChild(d);
  });
}

function params() {
  const p = new URLSearchParams();
  p.set("date_from", $("#dfrom").value); p.set("date_to", $("#dto").value);
  if ($("#supplier").value) p.set("supplier", $("#supplier").value);
  if ($("#buyer").value) p.set("buyer", $("#buyer").value);
  if ($("#q").value.trim()) p.set("q", $("#q").value.trim());
  return p;
}

async function render() {
  document.querySelectorAll(".pane").forEach(p => p.classList.add("hidden"));
  $("#" + TAB).classList.remove("hidden");
  $("#odwrap").classList.toggle("hidden", TAB !== "open");
  $("#kindwrap").classList.toggle("hidden", TAB !== "open" && TAB !== "po");
  $("#sortwrap").classList.toggle("hidden", TAB !== "po");
  $("#openonlywrap").classList.toggle("hidden", TAB !== "po");

  if (TAB === "overview") {
    const [s, m] = await Promise.all([
      fetch("/api/summary?" + params()).then(r => r.json()),
      fetch("/api/monthly?months=12").then(r => r.json()),
    ]);
    kpis(s); chart(m); dq(s.dq);
  } else if (TAB === "po") {
    const p = params();
    p.set("sort", $("#sort").value);
    p.set("kind", $("#kind").value);
    if ($("#onlyopen").checked) p.set("only_open", "true");
    const rows = CACHE.po || (CACHE.po = await fetch("/api/po?" + p).then(r => r.json()));
    const ord = rows.reduce((a, r) => a + Number(r.OrderAmt || 0), 0);
    const opn = rows.reduce((a, r) => a + Number(r.OpenAmt || 0), 0);
    $("#pometa").textContent =
      `${int(rows.length)} ใบสั่งซื้อ · มูลค่าสั่งรวม ${baht(ord)} · ค้างรวม ${baht(opn)}`
      + ` · คลิกที่เลขที่ PO เพื่อดูใบรับเข้าที่จับคู่กัน`;
    tablePo($("#tblPo"), rows);
  } else if (TAB === "receipts") {
    const rows = CACHE.rcv || (CACHE.rcv = await fetch("/api/receipts?" + params()).then(r => r.json()));
    const amt = rows.reduce((a, r) => a + Number(r.Amt || 0), 0);
    $("#rcvmeta").textContent = `${int(rows.length)} บรรทัด · มูลค่ารวม ${baht(amt)} · ยอดส่งคืนแสดงเป็นจำนวนติดลบ`;
    table($("#tblRcv"), RCV_COLS, rows, "receipts");
  } else {
    const p = params(); p.delete("date_from"); p.delete("date_to");
    if ($("#overdue").checked) p.set("overdue_only", "true");
    p.set("kind", $("#kind").value);
    const rows = CACHE.open || (CACHE.open = await fetch("/api/open?" + p).then(r => r.json()));
    const amt = rows.reduce((a, r) => a + Number(r.OpenAmt || 0), 0);
    $("#openmeta").textContent = `${int(rows.length)} บรรทัด · มูลค่าค้างรวม ${baht(amt)} · แถวแดงคือเกินกำหนดส่ง · ของค้างไม่ขึ้นกับช่วงวันที่ด้านบน`;
    table($("#tblOpen"), OPEN_COLS, rows, "open");
  }
}

function toast(msg, ms = 3500) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}

// toISOString() แปลงเป็น UTC ซึ่งร่นวันที่ของไทยไป 1 วัน ต้องประกอบเองจากเวลาท้องถิ่น
function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function preset(kind) {
  const now = new Date(); let a, b = now;
  if (kind === "7" || kind === "30") { a = new Date(now); a.setDate(a.getDate() - Number(kind)); }
  else if (kind === "tm") a = new Date(now.getFullYear(), now.getMonth(), 1);
  else if (kind === "lm") { a = new Date(now.getFullYear(), now.getMonth() - 1, 1);
                            b = new Date(now.getFullYear(), now.getMonth(), 0); }
  else if (kind === "ty") a = new Date(now.getFullYear(), 0, 1);
  $("#dfrom").value = iso(a); $("#dto").value = iso(b);
}

function invalidate() { CACHE = {}; render(); }

async function boot() {
  const meta = await fetch("/api/meta").then(r => r.json());
  meta.suppliers.forEach(s => {
    const o = el("option", null, `${s.SupNam} (${s.SupCd})`); o.value = s.SupCd;
    $("#supplier").appendChild(o);
  });
  meta.buyers.forEach(b => {
    const o = el("option", null, b.Buyer); o.value = b.Buyer; $("#buyer").appendChild(o);
  });
  preset("tm");
  if (meta.sync.last) $("#syncinfo").textContent = "อัปเดตล่าสุด " + meta.sync.last;

  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    t.classList.add("active"); TAB = t.dataset.tab; render();
  });
  document.querySelectorAll(".chip").forEach(c => c.onclick = () => {
    document.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
    c.classList.add("on"); preset(c.dataset.preset); invalidate();
  });
  ["dfrom", "dto", "supplier", "buyer", "overdue", "kind", "sort", "onlyopen"].forEach(id => $("#" + id).onchange = invalidate);

  let timer; $("#q").oninput = () => { clearTimeout(timer); timer = setTimeout(invalidate, 350); };

  $("#btnExport").onclick = () => {
    const p = params();
    if (TAB === "open" || TAB === "po") { p.delete("date_from"); p.delete("date_to");
      p.set("kind", $("#kind").value);
      location.href = "/api/export/r2?" + p; }
    else location.href = "/api/export/r1?" + p;
    toast("กำลังสร้างไฟล์ Excel…");
  };

  $("#btnSync").onclick = async () => {
    const b = $("#btnSync"); b.disabled = true; b.textContent = "กำลังอัปเดต…";
    const res = await fetch("/api/sync", { method: "POST" }).then(r => r.json());
    toast(res.msg);
    const poll = setInterval(async () => {
      const m = await fetch("/api/meta").then(r => r.json());
      if (!m.sync.running) {
        clearInterval(poll); b.disabled = false; b.textContent = "อัปเดตข้อมูลจาก ERP";
        if (m.sync.error) toast("อัปเดตไม่สำเร็จ: " + m.sync.error, 8000);
        else { $("#syncinfo").textContent = "อัปเดตล่าสุด " + m.sync.last;
               toast("อัปเดตข้อมูลเรียบร้อย"); invalidate(); }
      }
    }, 2000);
  };

  render();
}
boot();

/* ---------- หน้าสั่งซื้อ (PO) พร้อม drilldown ใบรับเข้า ---------- */

const PO_COLS = [
  ["เลขที่ PO","PoNo","link"], ["วันที่ PO","PoDat","date"], ["ผู้สั่ง","Buyer"],
  ["ผู้ขาย","SupNam"], ["รายการ","Lines","int"], ["มูลค่าสั่ง","OrderAmt","num"],
  ["รับแล้ว","RcvAmt","num"], ["ค้าง","OpenAmt","num"],
  ["กำหนดส่ง","ShipDat","date"], ["รับเข้าล่าสุด","LastRcvDat","date"],
  ["ครั้งที่รับ","RcvDocCount","int"], ["สถานะ","ErpStatus","pill"],
  ["เกินกำหนด(วัน)","OverdueDays","int"],
];

const PO_LINE_COLS = [
  ["ลำดับ","PoSeq"], ["รหัสสินค้า","PdtCd"], ["ชื่อสินค้า","PdtNam"],
  ["กำหนดส่ง","ShipDat","date"], ["สั่ง","OrderQty","num"], ["รับแล้ว","RcvQty","num"],
  ["ส่งคืน","RetQty","num"], ["ค้าง","OpenQty","num"], ["หน่วย","Unit"],
  ["ราคา","Price","num"], ["มูลค่า","OrderAmt","num"], ["%รับ","FillPct","pct"],
  ["สถานะ","LineStatus"],
];

const PO_RCV_COLS = [
  ["วันที่รับ","RcvDat","date"], ["เลขที่ใบรับ","RcvNo"], ["ประเภท","DocTypName"],
  ["ลำดับ PO","PoSeq"], ["รหัสสินค้า","PdtCd"], ["จำนวน","Qty","num"],
  ["หน่วย","Unit"], ["มูลค่า","Amt","num"], ["ที่เก็บ","LocCd"],
  ["ช้า(วัน)","DaysLate","int"], ["เอกสารผู้ขาย","SupDocNo"], ["ผู้บันทึก","Enterer"],
];

function miniTable(cols, rows, emptyMsg) {
  if (!rows.length) return el("div", "empty", emptyMsg);
  const t = el("table"), thead = el("thead"), tr = el("tr");
  cols.forEach(([title]) => tr.appendChild(el("th", null, title)));
  thead.appendChild(tr); t.appendChild(thead);
  const tb = el("tbody");
  rows.forEach(r => {
    const row = el("tr");
    cols.forEach(([, f, kind]) => row.appendChild(
      el("td", ["num","int","pct"].includes(kind) ? "num" : null, fmt(r[f], kind))));
    tb.appendChild(row);
  });
  t.appendChild(tb);
  return t;
}

async function drill(pono, host) {
  host.textContent = "กำลังโหลด…";
  const d = await fetch("/api/po/detail?pono=" + encodeURIComponent(pono)).then(r => r.json());
  host.textContent = "";
  const box = el("div", "drillbox");
  const s1 = el("div");
  s1.append(el("h3", null, `รายการในใบสั่งซื้อ ${pono} (${d.lines.length} บรรทัด)`),
            miniTable(PO_LINE_COLS, d.lines, "ไม่พบรายการ"));
  const n = d.receipts.length;
  const s2 = el("div");
  s2.append(el("h3", null, n ? `ใบรับเข้าที่อ้างถึง PO นี้ (${n} บรรทัด)` : "ใบรับเข้าที่อ้างถึง PO นี้"),
            miniTable(PO_RCV_COLS, d.receipts, "ยังไม่มีใบรับเข้าอ้างถึง PO ใบนี้"));
  box.append(s1, s2);
  host.appendChild(box);
}

function tablePo(node, rows) {
  node.innerHTML = "";
  const thead = el("thead"), tr = el("tr");
  PO_COLS.forEach(([title, field]) => {
    const th = el("th", null, title);
    if (SORT.po && SORT.po.f === field) th.textContent = title + (SORT.po.d > 0 ? " ▲" : " ▼");
    th.onclick = () => {
      const c = SORT.po;
      SORT.po = { f: field, d: c && c.f === field ? -c.d : 1 };
      tablePo(node, rows);
    };
    tr.appendChild(th);
  });
  thead.appendChild(tr); node.appendChild(thead);

  let data = rows.slice();
  const s = SORT.po;
  if (s) data.sort((a, b) => {
    const x = a[s.f], y = b[s.f];
    if (x == null) return 1; if (y == null) return -1;
    const nx = Number(x), ny = Number(y);
    const c = (!isNaN(nx) && !isNaN(ny) && x !== "" && y !== "")
      ? nx - ny : String(x).localeCompare(String(y), "th");
    return c * s.d;
  });

  const tb = el("tbody");
  data.forEach(r => {
    const row = el("tr");
    if (Number(r.OverdueDays) > 0) row.className = "overdue";
    PO_COLS.forEach(([, field, kind]) => {
      let td;
      if (kind === "pill") {
        td = el("td");
        td.appendChild(el("span", "pill " + (r[field] === "ค้างรับ" ? "open" : "done"), r[field]));
      } else if (kind === "link") {
        td = el("td", "link", r[field]);
      } else {
        td = el("td", ["num","int","pct"].includes(kind) ? "num" : null, fmt(r[field], kind));
      }
      row.appendChild(td);
    });
    tb.appendChild(row);

    const sub = el("tr", "drill hidden");
    const cell = el("td"); cell.colSpan = PO_COLS.length;
    sub.appendChild(cell); tb.appendChild(sub);

    row.querySelector("td.link").onclick = () => {
      const show = sub.classList.contains("hidden");
      sub.classList.toggle("hidden", !show);
      row.classList.toggle("expanded", show);
      if (show && !cell.dataset.loaded) { cell.dataset.loaded = "1"; drill(r.PoNo, cell); }
    };
  });
  node.appendChild(tb);
}
