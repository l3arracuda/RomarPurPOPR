"""จุดเริ่มของเว็บแอป — python -m app

สำคัญ: ต้อง import etl.config ก่อนอ่าน os.getenv เพราะโมดูลนั้นเป็นตัวโหลด .env
ถ้าไม่ import ค่า APP_HOST และ APP_PORT ใน .env จะไม่มีผล แล้วแอปจะกลับไปใช้
ค่าเริ่มต้น 127.0.0.1 ซึ่งเครื่องอื่นในวงแลนเข้าไม่ได้
"""
import os

import uvicorn

from etl import config  # noqa: F401  โหลด .env ตั้งแต่ตอน import

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8080"))
    if host == "0.0.0.0":  # noqa: S104
        print(f"เปิดให้เครื่องอื่นในวงแลนเข้าได้ที่พอร์ต {port}")
        print("หมายเหตุ: แอปนี้ยังไม่มีระบบล็อกอิน ใครเปิด URL ได้ก็เห็นข้อมูลทั้งหมด")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
