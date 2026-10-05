// สร้างคู่มือการใช้งานระบบรายงานจัดซื้อ เป็นไฟล์ PowerPoint
//   node docs/make_manual.js
// ใช้ฟอนต์ Tahoma เพราะมีอยู่ในทุกเครื่อง Windows และมีอักขระไทยครบ
const pptxgen = require("pptxgenjs");
const path = require("path");

const IMG = (f) => path.join(__dirname, "images", f);

const THEME = {
  name: "Romar Purchase",
  headFontFace: "Tahoma",
  bodyFontFace: "Tahoma",
  colors: {
    dk1: "16243D", lt1: "FFFFFF",
    dk2: "2F5496", lt2: "EDF1F8",
    accent1: "2F5496",  // น้ำเงินหลักของแอป
    accent2: "7AA0DD",  // น้ำเงินอ่อน (แท่งกราฟมูลค่ารับเข้า)
    accent3: "C0392B",  // แดง เกินกำหนด
    accent4: "1B7F4B",  // เขียว ปกติ
    accent5: "B4690E",  // ส้ม เตือน
    accent6: "6B7684",  // เทา ข้อความรอง
    hlink: "2F5496", folHlink: "6B7684",
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // 13.3 x 7.5 นิ้ว
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "ฝ่ายจัดซื้อ";
pres.title = "คู่มือการใช้งาน ระบบรายงานจัดซื้อ";
const C = pres.SchemeColor;

// ใช้ตอนไล่หาสไลด์ที่ทำให้ไฟล์เสีย: MAX_SLIDES=5 node docs/make_manual.js
const _LIMIT = Number(process.env.MAX_SLIDES || 999);
const _addSlide = pres.addSlide.bind(pres);
let _made = 0;
const _NOOP = new Proxy({}, { get: () => () => _NOOP });
pres.addSlide = (o) => (++_made <= _LIMIT ? _addSlide(o) : _NOOP);

const FOOT = { text: "ระบบรายงานจัดซื้อ ROMAR", options: { x: 0.6, y: 7.0, w: 6, h: 0.3,
  fontSize: 10, color: C.accent6, isTextBox: true, margin: 0 } };
const PAGENUM = { x: 12.3, y: 7.0, w: 0.5, h: 0.3, fontSize: 10, color: C.accent6, align: "right" };

pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.5, w: 11.5, h: 1.5,
        fontSize: 44, bold: true, color: C.background1, align: "left", valign: "bottom" }, text: " " } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 4.1, w: 11.5, h: 1.6,
        fontSize: 17, color: C.accent2, align: "left", valign: "top" }, text: " " } },
  ],
});

pres.defineSlideMaster({
  title: "SECTION_DARK",
  background: { color: C.accent1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.9, y: 2.9, w: 11.5, h: 1.2,
        fontSize: 38, bold: true, color: C.background1, align: "left", valign: "middle" }, text: " " } },
    { placeholder: { options: { name: "body", type: "body", x: 0.9, y: 4.2, w: 11.5, h: 1.2,
        fontSize: 16, color: "D7E2F5", align: "left", valign: "top" }, text: " " } },
  ],
});

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.45, w: 12.1, h: 0.8,
        fontSize: 30, bold: true, color: C.text1, align: "left", valign: "middle", margin: 0 }, text: " " } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 1.45, w: 12.1, h: 5.3,
        fontSize: 15, color: C.text1, align: "left", valign: "top", margin: 0 }, text: " " } },
    { text: FOOT },
  ],
  slideNumber: PAGENUM,
});

pres.defineSlideMaster({
  title: "SHOT",
  background: { color: C.background1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.4, w: 12.1, h: 0.65,
        fontSize: 28, bold: true, color: C.text1, align: "left", valign: "middle", margin: 0 }, text: " " } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 1.05, w: 12.1, h: 0.5,
        fontSize: 14, color: C.accent6, align: "left", valign: "top", margin: 0 }, text: " " } },
    { text: FOOT },
  ],
  slideNumber: PAGENUM,
});


/* ---------- ตัวช่วยวาด ---------- */
const card = (s, o) => {
  // PowerPoint ปฏิเสธทั้งไฟล์ถ้ามีรูปทรงสูงหรือกว้างเป็นศูนย์
  if (!(o.w > 0) || !(o.h > 0)) throw new Error(`card ขนาดไม่ถูกต้อง: w=${o.w} h=${o.h}`);
  s.addShape(pres.ShapeType.roundRect, { x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.08,
    fill: { color: o.fill || C.background2 }, line: { color: o.line || C.background2, width: 1 },
    objectName: o.name });
  if (o.tag) s.addText(o.tag, { x: o.x + 0.25, y: o.y + 0.18, w: o.w - 0.5, h: 0.3,
    fontSize: 11, bold: true, color: o.tagColor || C.accent1, isTextBox: true, margin: 0 });
  s.addText(o.head, { x: o.x + 0.25, y: o.y + (o.tag ? 0.5 : 0.22), w: o.w - 0.5, h: 0.4,
    fontSize: o.headSize || 16, bold: true, color: o.headColor || C.text1, isTextBox: true, margin: 0 });
  if (o.body) s.addText(o.body, { x: o.x + 0.25, y: o.y + (o.tag ? 0.95 : 0.68), w: o.w - 0.5,
    h: o.h - (o.tag ? 1.15 : 0.9), fontSize: o.bodySize || 13, color: o.bodyColor || C.accent6,
    isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.25 });
};

const shot = (s, file) => s.addImage({ path: IMG(file), x: 0.6, y: 1.6, w: 7.8, h: 5.2,
  shadow: { type: "outer", angle: 90, blur: 10, offset: 2, color: "9AA6B8", opacity: 0.45 } });

const notes = (s, x, y, items) => {
  let cy = y;
  items.forEach((it) => {
    s.addShape(pres.ShapeType.ellipse, { x, y: cy + 0.05, w: 0.26, h: 0.26,
      fill: { color: it.color || C.accent1 }, line: { color: it.color || C.accent1, width: 0 } });
    s.addText(it.n, { x, y: cy + 0.05, w: 0.26, h: 0.26, fontSize: 11, bold: true,
      color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText([{ text: it.head + "\n", options: { bold: true, fontSize: 13, color: C.text1 } },
               { text: it.body, options: { fontSize: 12, color: C.accent6 } }],
      { x: x + 0.38, y: cy, w: 3.7, h: it.h || 0.95, isTextBox: true, margin: 0,
        valign: "top", lineSpacingMultiple: 1.2 });
    cy += it.h || 0.95;
  });
};

/* ---------- 1. ปก ---------- */
pres.addSection({ title: "เริ่มต้น" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "เริ่มต้น" });
s.addText("คู่มือการใช้งาน\nระบบรายงานจัดซื้อ", { placeholder: "title" });
s.addText("ดูได้ว่าสั่งซื้อไปเท่าไหร่ ของเข้ามาแล้วเท่าไหร่ และยังค้างอยู่เท่าไหร่",
  { placeholder: "body" });
s.addText("สำหรับฝ่ายจัดซื้อ", { x: 0.9, y: 1.9, w: 6, h: 0.4, fontSize: 14,
  color: C.accent2, bold: true, isTextBox: true, margin: 0 });
s.addNotes("คู่มือนี้ครอบคลุมการใช้งานทั้ง 4 หน้าของระบบ");

/* ---------- 2. ระบบนี้มีไว้ทำอะไร ---------- */
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "เริ่มต้น" });
s.addText("ระบบนี้มีไว้ทำอะไร", { placeholder: "title" });
card(s, { x: 0.6, y: 1.5, w: 5.9, h: 2.2, fill: "FDECEA", line: "F5C6C0",
  tag: "ปัญหาเดิม", tagColor: C.accent3, head: "จัดซื้อไม่เห็นว่าของเข้ามาหรือยัง",
  body: "เปิดใบสั่งซื้อแล้วของไปเข้าที่สต็อก เอกสารรับเข้าวิ่งตรงไปบัญชี\nจัดซื้อจึงไม่รู้ว่าของมาถึงเมื่อไหร่ มาครบไหม และยังค้างเท่าไหร่" });
card(s, { x: 6.8, y: 1.5, w: 5.9, h: 2.2, fill: "E7F4EC", line: "BEE0CC",
  tag: "ระบบนี้ช่วย", tagColor: C.accent4, head: "เห็นครบในหน้าจอเดียว",
  body: "ดึงข้อมูลจากระบบ ERP มาจับคู่ใบสั่งซื้อกับใบรับเข้าให้อัตโนมัติ\nเลือกช่วงเวลาเองได้ และดาวน์โหลดเป็น Excel ไปใช้ต่อได้" });
s.addText("คำถามที่ระบบตอบได้", { x: 0.6, y: 4.0, w: 12.1, h: 0.4, fontSize: 17, bold: true,
  color: C.text1, isTextBox: true, margin: 0 });
[["วันนี้ของเข้ามาอะไรบ้าง", "จาก PO ใบไหน มูลค่าเท่าไหร่", 0.6],
 ["เดือนนี้สั่งไปกี่บาท", "และรับเข้ามาแล้วกี่บาท", 4.65],
 ["ตอนนี้ค้างรับเท่าไหร่", "ใบไหนเลยกำหนดส่งแล้วบ้าง", 8.7]
].forEach(([h, b, x]) => card(s, { x, y: 4.5, w: 3.95, h: 1.25, head: h, headSize: 14, body: b }));
s.addNotes("อธิบายภาพรวมว่าทำไมต้องมีระบบนี้");

/* ---------- 3. เข้าใช้งานยังไง ---------- */
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "เริ่มต้น" });
s.addText("เข้าใช้งานยังไง", { placeholder: "title" });
card(s, { x: 0.6, y: 1.5, w: 12.1, h: 1.15, fill: C.accent1, line: C.accent1,
  head: "http://192.168.2.75:8080", headSize: 24, headColor: C.background1,
  body: "เปิดจากเบราว์เซอร์ในเครื่องที่อยู่ในวงแลนบริษัท  ไม่ต้องติดตั้งโปรแกรมอะไร",
  bodyColor: "CFDCF2", bodySize: 13 });
s.addText("ระบบมี 4 หน้า สลับด้วยแท็บด้านบน", { x: 0.6, y: 2.95, w: 12.1, h: 0.4,
  fontSize: 17, bold: true, color: C.text1, isTextBox: true, margin: 0 });
[["1", "ภาพรวม", "ตัวเลขสรุปและกราฟ 12 เดือน  เป็นหน้าแรกที่เปิดขึ้นมา", 0.6],
 ["2", "สั่งซื้อ (PO)", "ใบสั่งซื้อตามช่วงเวลา คลิกดูได้ว่าของมาแล้วหรือยัง", 3.65],
 ["3", "ใบรับเข้า", "ของที่เข้ามาจริงในแต่ละวัน พร้อมรายการสินค้า", 6.7],
 ["4", "ค้างรับ", "ของที่สั่งแล้วยังไม่ได้รับ เรียงตามกำหนดส่ง", 9.75]
].forEach(([n, h, b, x]) => {
  card(s, { x, y: 3.45, w: 2.95, h: 2.0, head: "", body: "" });
  s.addShape(pres.ShapeType.ellipse, { x: x + 0.25, y: 3.68, w: 0.42, h: 0.42,
    fill: { color: C.accent1 }, line: { color: C.accent1, width: 0 } });
  s.addText(n, { x: x + 0.25, y: 3.68, w: 0.42, h: 0.42, fontSize: 15, bold: true,
    color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(h, { x: x + 0.25, y: 4.22, w: 2.45, h: 0.35, fontSize: 16, bold: true,
    color: C.text1, isTextBox: true, margin: 0 });
  s.addText(b, { x: x + 0.25, y: 4.6, w: 2.45, h: 0.75, fontSize: 12, color: C.accent6,
    isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.2 });
});
card(s, { x: 0.6, y: 5.7, w: 12.1, h: 1.0, fill: "FDF3E2", line: "F0DCB8",
  head: "ข้อมูลไม่ได้อัปเดตเอง", headSize: 14, headColor: "8A5008",
  body: "กดปุ่ม \"อัปเดตข้อมูลจาก ERP\" มุมขวาบน ใช้เวลาประมาณ 20 วินาที  ถ้าไม่กด ตัวเลขจะเป็นของรอบที่อัปเดตล่าสุด",
  bodySize: 12, bodyColor: "8A5008" });

/* ---------- 4. แถบควบคุมด้านบน ---------- */
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "เริ่มต้น" });
s.addText("แถบควบคุมด้านบน  ใช้ได้ทุกหน้า", { placeholder: "title" });
[["ตั้งแต่ / ถึง", "เลือกช่วงวันที่เอง", "หน้าภาพรวม สั่งซื้อ และใบรับเข้าจะกรองตามช่วงนี้", C.accent1],
 ["ปุ่มลัด", "7 วัน · 30 วัน · เดือนนี้ · เดือนที่แล้ว · ปีนี้", "กดทีเดียวได้ช่วงที่ใช้บ่อย ไม่ต้องเลือกวันที่เอง", C.accent1],
 ["ผู้ขาย / ผู้สั่งซื้อ", "กรองเฉพาะรายที่สนใจ", "เช่น ดูเฉพาะของที่ตัวเองเป็นคนสั่ง", C.accent2],
 ["ค้นหา", "พิมพ์รหัสสินค้า ชื่อสินค้า หรือเลขที่ PO", "ค้นได้บางส่วนของคำ ไม่ต้องพิมพ์เต็ม", C.accent2],
 ["ดาวน์โหลด Excel", "ได้ไฟล์ตามหน้าและตัวกรองที่เลือกอยู่", "เปิดด้วย Excel ได้เลย มีหัวตารางตรึงและตัวกรองให้พร้อม", C.accent4]
].forEach(([tag, head, body, col], i) => {
  const y = 1.5 + i * 1.07;
  card(s, { x: 0.6, y, w: 12.1, h: 0.95 });
  s.addShape(pres.ShapeType.roundRect, { x: 0.85, y: y + 0.26, w: 2.3, h: 0.42, rectRadius: 0.2,
    fill: { color: col }, line: { color: col, width: 0 } });
  s.addText(tag, { x: 0.85, y: y + 0.26, w: 2.3, h: 0.42, fontSize: 12, bold: true,
    color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(head, { x: 3.35, y: y + 0.14, w: 9.1, h: 0.35, fontSize: 15, bold: true,
    color: C.text1, isTextBox: true, margin: 0 });
  s.addText(body, { x: 3.35, y: y + 0.5, w: 9.1, h: 0.33, fontSize: 12, color: C.accent6,
    isTextBox: true, margin: 0 });
});
s.addNotes("ย้ำว่าช่วงวันที่ไม่มีผลกับหน้าค้างรับ เพราะยอดค้างคิด ณ ปัจจุบันเสมอ");

/* ---------- 5. หน้าภาพรวม ---------- */
pres.addSection({ title: "ทีละหน้า" });
s = pres.addSlide({ masterName: "SHOT", sectionTitle: "ทีละหน้า" });
s.addText("หน้าภาพรวม", { placeholder: "title" });
s.addText("ตัวเลขสรุปของช่วงที่เลือก และกราฟเทียบยอดสั่งกับยอดรับย้อนหลัง 12 เดือน",
  { placeholder: "body" });
shot(s, "01-overview.jpg");
notes(s, 8.7, 1.7, [
  { n: "1", head: "การ์ดตัวเลข 6 ใบ", body: "สรุปยอดของช่วงที่เลือก กดเข้าไปดูตารางได้", h: 1.0 },
  { n: "2", head: "กราฟ 12 เดือน", body: "แท่งเข้ม = ยอดสั่งซื้อ  แท่งอ่อน = ยอดรับเข้า\nเดือนล่าสุดอยู่ซ้ายสุด", h: 1.35 },
  { n: "3", head: "คลิกแท่งกราฟได้", body: "คลิกแล้วเด้งไปดูรายการของเดือนนั้นทันที", h: 1.0 },
  { n: "4", head: "ตรวจคุณภาพข้อมูล", body: "แจ้งเตือนถ้าเจอข้อมูลผิดปกติในระบบ ERP", h: 1.0 },
]);

/* ---------- 6. ความหมายของการ์ด ---------- */
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "ทีละหน้า" });
s.addText("การ์ดตัวเลข 6 ใบ  หมายถึงอะไร", { placeholder: "title" });
[["มูลค่าสั่งซื้อในช่วง", "ยอดที่เปิดใบสั่งซื้อในช่วงที่เลือก", "คลิก \u2192 หน้าสั่งซื้อ", C.accent1],
 ["มูลค่ารับเข้าในช่วง", "ของที่เข้ามาจริงในช่วงนั้น อาจมาจาก PO เดือนก่อนก็ได้", "คลิก \u2192 หน้าใบรับเข้า", C.accent1],
 ["ส่งคืนในช่วง", "ของที่ส่งคืนผู้ขาย แสดงเป็นจำนวนติดลบ", "คลิก \u2192 หน้าใบรับเข้า", C.accent5],
 ["ค้างรับทั้งหมด", "ของที่สั่งแล้วยังไม่ได้รับ คิด ณ ปัจจุบัน ไม่ขึ้นกับช่วงวันที่", "คลิก \u2192 หน้าค้างรับ", C.accent5],
 ["ค้างเกินกำหนด", "ส่วนของยอดค้างที่เลยวันกำหนดส่งมาแล้ว", "คลิก \u2192 ค้างรับ + กรองเฉพาะที่เกิน", C.accent3],
 ["ส่งตรงเวลา", "สัดส่วนใบรับที่มาถึงไม่เกินกำหนดส่ง", "ไม่สามารถคลิกได้", C.accent4]
].forEach(([h, b, link, col], i) => {
  const x = 0.6 + (i % 3) * 4.05, y = 1.5 + Math.floor(i / 3) * 2.6;
  card(s, { x, y, w: 3.85, h: 2.35, head: h, headSize: 15, headColor: col, body: b });
  s.addText(link, { x: x + 0.25, y: y + 1.85, w: 3.35, h: 0.32, fontSize: 11, bold: true,
    color: col, isTextBox: true, margin: 0 });
});

/* ---------- 7. หน้าสั่งซื้อ (PO) ---------- */
s = pres.addSlide({ masterName: "SHOT", sectionTitle: "ทีละหน้า" });
s.addText("หน้าสั่งซื้อ (PO)", { placeholder: "title" });
s.addText("ใบสั่งซื้อตามช่วงเวลา  คลิกที่เลขที่ PO เพื่อดูว่าของมาแล้วหรือยัง",
  { placeholder: "body" });
shot(s, "02-po.jpg");
notes(s, 8.7, 1.7, [
  { n: "1", head: "หนึ่งแถว = หนึ่งใบสั่งซื้อ", body: "คอลัมน์ รายการ บอกว่าใบนั้นมีกี่สินค้า", h: 1.0 },
  { n: "2", head: "คลิกเลขที่ PO", body: "กางลงมาเห็น 2 ตาราง คือรายการในใบสั่งซื้อ และใบรับเข้าที่อ้างถึง PO นี้", h: 1.5 },
  { n: "3", head: "เรียงตาม", body: "ตั้งต้นที่รับเข้าล่าสุด จะได้รู้ว่าช่วงนี้ของเข้าของใบไหนไปแล้ว", h: 1.3 },
  { n: "4", head: "แถวสีแดง", body: "เลยกำหนดส่งแล้วแต่ยังรับไม่ครบ", color: C.accent3, h: 0.9 },
]);
s.addNotes("จุดขายของหน้านี้คือ drilldown ที่เห็นการจับคู่ PO กับใบรับเข้า");

/* ---------- 8. หน้าใบรับเข้า ---------- */
s = pres.addSlide({ masterName: "SHOT", sectionTitle: "ทีละหน้า" });
s.addText("หน้าใบรับเข้า", { placeholder: "title" });
s.addText("ของที่เข้ามาจริงในช่วงที่เลือก  คลิกที่เลขที่ใบรับเพื่อดูรายการสินค้า",
  { placeholder: "body" });
shot(s, "03-receipts.jpg");
notes(s, 8.7, 1.7, [
  { n: "1", head: "หนึ่งแถว = หนึ่งใบรับ", body: "คอลัมน์ รายการ บอกว่าใบนั้นรับกี่สินค้า", h: 1.0 },
  { n: "2", head: "ประเภท", body: "รับเข้าซื้อ คือของเข้า\nส่งคืนผู้ขาย คือของที่คืนไป จำนวนจะติดลบ", h: 1.4 },
  { n: "3", head: "ช้า (วัน)", body: "ของมาช้ากว่ากำหนดกี่วัน  ค่าติดลบ = มาก่อนกำหนด", h: 1.2 },
  { n: "4", head: "เอกสารผู้ขาย", body: "เลขที่ใบส่งของของผู้ขาย ใช้กระทบยอดกับบิลได้", h: 1.0 },
]);

/* ---------- 9. หน้าค้างรับ ---------- */
s = pres.addSlide({ masterName: "SHOT", sectionTitle: "ทีละหน้า" });
s.addText("หน้าค้างรับ", { placeholder: "title" });
s.addText("ของที่สั่งแล้วยังไม่ได้รับ  เรียงตามกำหนดส่ง ใบที่ต้องตามก่อนอยู่บนสุด",
  { placeholder: "body" });
shot(s, "04-open.jpg");
notes(s, 8.7, 1.7, [
  { n: "1", head: "ไม่ขึ้นกับช่วงวันที่", body: "ยอดค้างคิด ณ ปัจจุบันเสมอ เปลี่ยนวันที่ด้านบนแล้วตัวเลขไม่เปลี่ยน", h: 1.5 },
  { n: "2", head: "แถวสีแดง", body: "เลยกำหนดส่งแล้ว ดูคอลัมน์ เกินกำหนด(วัน) ว่าช้ามากี่วัน", color: C.accent3, h: 1.3 },
  { n: "3", head: "เฉพาะที่เกินกำหนด", body: "ติ๊กช่องนี้เพื่อดูเฉพาะใบที่ต้องรีบตาม", h: 1.1 },
  { n: "4", head: "คลิกเลขที่ PO", body: "ดูรายการและใบรับเข้าที่ผ่านมา ก่อนโทรตามผู้ขาย", h: 1.1 },
]);

/* ---------- 10. เข้าใจตัวเลขให้ถูก ---------- */
pres.addSection({ title: "เข้าใจตัวเลข" });
s = pres.addSlide({ masterName: "SECTION_DARK", sectionTitle: "เข้าใจตัวเลข" });
s.addText("เข้าใจตัวเลขให้ถูก", { placeholder: "title" });
s.addText("4 เรื่องที่คนมักเข้าใจผิด และทำให้อ่านรายงานพลาด", { placeholder: "body" });

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "เข้าใจตัวเลข" });
s.addText("4 เรื่องที่ต้องแยกให้ออก", { placeholder: "title" });
[["เกินกำหนด (วัน)", "ของยังไม่มา", "นับจากวันกำหนดส่งถึงวันนี้ ตัวเลขจะเพิ่มขึ้นทุกวันจนกว่าของจะมา", C.accent3],
 ["ช้า (วัน)", "ของมาแล้ว", "มาช้ากว่ากำหนดกี่วัน ค่าติดลบแปลว่ามาก่อนกำหนด เป็นค่าที่หยุดนิ่งแล้ว", C.accent1],
 ["ปิด", "จบงานแล้ว", "จัดซื้อกดปิดในระบบ ERP หรือรับครบแล้ว  ใบที่ปิดจะไม่อยู่ในยอดค้างรับ", C.accent4],
 ["ค้างรับ", "ยังต้องตาม", "ยังไม่ปิดและยังได้ของไม่ครบ  นี่คือตัวเลขที่ต้องลงมือทำอะไรสักอย่าง", C.accent5]
].forEach(([h, tag, b, col], i) => {
  const x = 0.6 + (i % 2) * 6.2, y = 1.5 + Math.floor(i / 2) * 2.55;
  card(s, { x, y, w: 5.9, h: 2.3, tag, tagColor: col, head: h, headSize: 19, headColor: col, body: b });
});
s.addNotes("เน้นว่า เกินกำหนด กับ ช้า เป็นคนละเรื่องกัน");

/* ---------- 11. ข้อจำกัดที่ควรรู้ ---------- */
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "เข้าใจตัวเลข" });
s.addText("ข้อจำกัดที่ควรรู้ก่อนใช้", { placeholder: "title" });
[["ข้อมูลย้อนหลังได้ถึงปี 2024 เท่านั้น",
  "ข้อมูลปี 2021 ถึง 2023 สูญหายจากไวรัสเรียกค่าไถ่ กู้คืนไม่ได้ กราฟ 12 เดือนและรายงานทุกตัวจึงเริ่มนับจากปี 2024"],
 ["ตัวเลขไม่ได้สดตลอดเวลา",
  "ระบบคัดลอกข้อมูลจาก ERP มาเก็บไว้ ถ้าเพิ่งมีการบันทึกรับของเมื่อสักครู่ ต้องกดปุ่มอัปเดตก่อนจึงจะเห็น"],
 ["ยังไม่มีระบบล็อกอิน",
  "ใครก็ตามที่เปิด URL นี้ได้จะเห็นข้อมูลจัดซื้อทั้งหมด รวมถึงราคาซื้อและรายชื่อผู้ขาย ใช้ภายในวงแลนบริษัทเท่านั้น"],
 ["รับเกินจำนวนที่สั่งเป็นเรื่องปกติ",
  "งานผ้าและม้วนตัดไม่ลงตัว ระบบจึงแสดงสถานะรับเกินได้โดยไม่ถือเป็นข้อผิดพลาด"]
].forEach(([h, b], i) => {
  const y = 1.5 + i * 1.32;
  card(s, { x: 0.6, y, w: 12.1, h: 1.2, fill: "FDF3E2", line: "F0DCB8" });
  s.addShape(pres.ShapeType.ellipse, { x: 0.9, y: y + 0.42, w: 0.36, h: 0.36,
    fill: { color: "B4690E" }, line: { color: "B4690E", width: 0 } });
  s.addText("!", { x: 0.9, y: y + 0.42, w: 0.36, h: 0.36, fontSize: 16, bold: true,
    color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
  s.addText(h, { x: 1.45, y: y + 0.18, w: 10.9, h: 0.38, fontSize: 16, bold: true,
    color: "7A4606", isTextBox: true, margin: 0 });
  s.addText(b, { x: 1.45, y: y + 0.58, w: 10.9, h: 0.5, fontSize: 12.5, color: "8A5008",
    isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.15 });
});

/* ---------- 12. สรุป ---------- */
s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "เข้าใจตัวเลข" });
s.addText("เริ่มใช้ได้เลย", { placeholder: "title" });
s.addText("เปิด http://192.168.2.75:8080 จากเบราว์เซอร์ในวงแลนบริษัท", { placeholder: "body" });
[["ทุกเช้า", "เปิดหน้าใบรับเข้า ดูว่าเมื่อวานของอะไรมาบ้าง", 0.9],
 ["ทุกสัปดาห์", "เปิดหน้าค้างรับ ติ๊กเฉพาะที่เกินกำหนด แล้วไล่ตาม", 5.05],
 ["สิ้นเดือน", "หน้าภาพรวม ดูยอดสั่งเทียบยอดรับ แล้วโหลด Excel", 9.2]
].forEach(([h, b, x]) => {
  s.addShape(pres.ShapeType.roundRect, { x, y: 5.5, w: 3.9, h: 1.3, rectRadius: 0.08,
    fill: { color: "22365C" }, line: { color: "35507F", width: 1 } });
  s.addText(h, { x: x + 0.25, y: 5.68, w: 3.4, h: 0.32, fontSize: 14, bold: true,
    color: C.accent2, isTextBox: true, margin: 0 });
  s.addText(b, { x: x + 0.25, y: 6.04, w: 3.4, h: 0.62, fontSize: 12.5, color: "C9D6EF",
    isTextBox: true, margin: 0, valign: "top", lineSpacingMultiple: 1.2 });
});
s.addText("มีปัญหาหรืออยากให้เพิ่มอะไร แจ้งได้ที่ฝ่าย IT", { x: 0.9, y: 4.75, w: 11.5, h: 0.35,
  fontSize: 13, color: C.accent2, isTextBox: true, margin: 0 });

/* ---------- เขียนไฟล์ ---------- */
const { applyTheme } = require(path.join(
  "C:", "Users", "gumpanart", "AppData", "Roaming", "Claude",
  "local-agent-mode-sessions", "skills-plugin",
  "7db9f084-ee25-4d7d-b431-0a3c32b8df03", "8c48a7f8-4ebf-4e05-b7c0-e6708ad702e4",
  "skills", "pptx", "scripts", "apply_theme.js"));

/** เขียนฟอนต์ complex script ลงธีม
 *  pptxgenjs ตั้งได้แค่ <a:latin> ส่วนอักษรไทยใช้ช่อง <a:cs> คนละช่องกัน
 *  ถ้าไม่ใส่ PowerPoint จะตกไปใช้ฟอนต์ไทยเริ่มต้น ซึ่งคนละหน้าตากับที่ออกแบบไว้
 */
async function setThaiFont(file, face) {
  const JSZip = require("jszip");
  const fs = require("fs");
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const name = Object.keys(zip.files).find((f) => f.startsWith("ppt/theme/") && f.endsWith(".xml"));
  let xml = await zip.file(name).async("string");
  const before = xml;
  xml = xml.split('<a:cs typeface=""/>').join(`<a:cs typeface="${face}"/>`);
  if (xml === before) throw new Error("ไม่พบช่อง cs ที่ว่างในธีม");
  zip.file(name, xml);
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer" }));
}

const OUT = process.env.OUT_FILE || path.join(__dirname, "คู่มือการใช้งาน-ระบบรายงานจัดซื้อ.pptx");
(async () => {
  await pres.writeFile({ fileName: OUT });
  if (!process.env.SKIP_THEME) await applyTheme(OUT, THEME);
  await setThaiFont(OUT, THEME.bodyFontFace);
  console.log("สร้างไฟล์แล้ว:", OUT);
})();
