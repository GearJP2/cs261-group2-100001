# UniSport Buddy — As-built diagrams

จัดทำย้อนหลังวันที่ **14 พฤศจิกายน 2026** โดยผู้ช่วยร่วมกับ **GearJP2** จาก main commit `e0edf10` (รวม PR #139) เพื่อประกอบการอธิบายระบบที่พัฒนาแล้ว ไม่อ้างว่าออกแบบก่อน implementation และไม่ใช่หลักฐาน human UAT

> หน้ารวมนี้ต้อง merge หลัง PR ของ issues #140–#146 เพื่อให้ลิงก์ทุกหมวดเปิดได้บน main

## ชุดเอกสาร

| Issue | Diagram | เนื้อหา |
|---|---|---|
| #140 | [Context](context/README.md) | ขอบเขตและ TU API |
| #141 | [Use Case](use-case/README.md) | บทบาทและ US ของ Sprint 1–2 |
| #142 | [ERD](erd/README.md) | Domain schema 3 มุมมอง พร้อม constraints |
| #143 | [State](state/README.md) | Party, JoinRequest, Membership |
| #144 | [Architecture](architecture/README.md) | Browser, Django components, ORM, database |
| #145 | [Activity](activity/README.md) | Join/approve/leave และ No-show |
| #146 | [Deployment](deployment/README.md) | Compose dev และ GitHub Actions CI |
| #147 | [Sequence audit](sequence-audit/README.md) | Sprint 1 เพิ่มเติม และ [Sprint 2 เดิมที่ปรับแล้ว](../sprint-2-sequences/README.md) |

แต่ละภาพมีไฟล์ `.mmd` แก้ไขได้และ `.svg` เปิดดู/นำเข้าเอกสารได้ ภาษาอังกฤษในภาพใช้ชื่อให้ตรงกับโค้ด มีคำอธิบายไทยใน README ของแต่ละหมวด

## สถานะที่ต้องอ่านร่วมกับภาพ

- US1/3/7/8/9: มี backend และหน้าเว็บพื้นฐาน; การตรวจเอกสารครั้งนี้ไม่ได้เรียก TU จริง
- US2: GET `/api/v1/parties` มีรายการ Open สูงสุด 50 รายการแล้ว แต่ยังไม่มี full search/filter ตาม US2; sequence Search ยังเป็น proposed flow
- US4: `leave_party` และ database tests เข้า main แล้ว; `/parties/{id}/leave` ยังไม่มี route และ UI integration ยังรอ Task70/งาน frontend
- US6: members API มีจริง จำกัด Host หรือสมาชิก active; Host แสดงในรายชื่อเฉพาะเมื่อมี active membership จริง
- US10: pending-list และ approve/reject API มีแล้ว; sequence ระบุส่วน UI ปัจจุบันและเป้าหมายเพิ่มเติมแยกกัน
- US14: submit/read review และ schema เข้า main แล้ว; No-show ใช้ [policy ที่ Gear ยืนยัน](../us14-no-show-approved-policy.md) แต่ `NO_SHOW_ENABLED=false` โดยค่าเริ่มต้น UI รีวิว/รายงานยังไม่ได้ส่งมอบใน baseline นี้
- Deployment: เอกสารเป็น dev/CI; ไม่อ้างว่ามี production deployment

## หลักฐานอ้างอิงและการตรวจ

ตรวจ `backend/{accounts,venues,parties,conduct}/models.py`, migrations, routes, views, services, policy, Dockerfile/Compose และ workflow จริง; ERD ดึง field/relationship/constraint จาก Django metadata โดยไม่อ่านข้อมูลผู้ใช้

ผลต่างจากเอกสารเก่าและข้อสรุปอยู่ใน [sequence audit](sequence-audit/audit.md). หากโค้ดใหม่เปลี่ยนพฤติกรรม ให้ปรับภาพที่เกี่ยวข้องและบันทึก baseline ใหม่พร้อม PR ไม่ใช้ภาพแทน test

## วิธี render ซ้ำ

ใช้ Mermaid CLI จากเครื่องมือภายนอก repo (ไม่เพิ่ม runtime dependency) เช่น `mmdc -i docs/diagrams/context/system.mmd -o docs/diagrams/context/system.svg -c docs/diagrams/mermaid-config.json` และทำแบบเดียวกันกับ `.mmd` อื่น ๆ รวม `docs/sprint-2-sequences/`. CLI ต้องมี Chromium ที่ใช้งานได้ เครื่อง sandbox อาจต้องกำหนด Puppeteer config ตามสภาพแวดล้อมของตน

ตรวจรับ: source render ได้ทุกภาพ, SVG เปิดได้, Markdown links ไม่ขาด และเทียบ guard/state/fields กับ baseline แล้ว; ยังรอ Gear/ทีม review ผ่าน PR ก่อนปิด issues

[ผลตรวจเอกสารและข้อจำกัด](validation.md)
