# Frontend

ใช้ Django Templates ที่ `templates/` และ assets ที่ `static/` ผ่านแอปพอร์ต 8000 ตาม [คู่มือ development](../docs/development.md) ทีม Frontend แก้ HTML/CSS ในเครื่องแล้วดูผลได้โดยไม่ต้องรัน Node server

- สืบทอด `templates/base.html` เพื่อใช้ layout และ stylesheet ร่วมกัน
- หน้า `templates/search.html` ใช้ API รายการปาร์ตี้ กีฬา และสนามเพื่อค้นหา/กรองผลลัพธ์
- ใช้ `{% load static %}` และ `{% static 'css/site.css' %}` อ้างอิง asset
- เมื่อ API พร้อมให้เชื่อมผ่าน origin เดียวกันตาม contract ของ Story และแนบ CSRF เมื่อส่งคำขอเปลี่ยนข้อมูล
- โฟลเดอร์ pages/components/styles/public/utils เดิมเป็น placeholder; runtime โหลดจาก templates/static ตาม settings

เริ่มด้วย `make up` จาก root แล้วเปิด <http://localhost:8000/> รัน `make smoke` เพื่อตรวจทั้ง template และ static CSS
