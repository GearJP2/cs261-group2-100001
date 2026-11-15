# Sprint 2 — AC coverage matrix

Issue #118 / Task45 · baseline `b6b4dc3` · 2026-11-15

PLAN IDs เป็น crosswalk ของ Task44 ไม่ใช่การเปลี่ยนเลข AC ต้นทางหรือรับรองมติแทนทีม. ทุก TC ใน inventory เป็น Not run สำหรับรอบนี้; ลิงก์ source เป็นแหล่งออกแบบ/หลักฐานเดิม ไม่ใช่ผลรันใหม่

| PLAN AC | จุดตรวจ | TC IDs | วิธีตรวจ |
|---|---|---|---|
| PLAN-US10-01 | Scenarioอนุมัติ | QA-US10-API-01 | API |
| PLAN-US10-02 | Scenarioอนุมัติ | QA-US10-API-02, QA-US10-DB-01, QA-US10-DB-02 | API, DB |
| PLAN-US10-03 | Scenarioปฏิเสธ | QA-US10-API-03, QA-US10-API-04 | API |
| PLAN-US10-04 | เพิ่มขอบเขตตรวจ | QA-US10-API-05, QA-US10-API-06, QA-US10-API-07, QA-US10-DB-03, QA-US10-API-08 | API, DB |
| PLAN-US10-05 | UIหลังตัดสิน | QA-US10-UI-01, QA-US10-UI-02 | UI |
| PLAN-US6-01 | Scenarioแสดงสมาชิก | QA-US6-API-01 | API |
| PLAN-US6-02 | สิทธิ์/ข้อมูล | QA-US6-API-02, QA-US6-UI-02, QA-US6-API-04 | API, UI |
| PLAN-US6-03 | เรียงและcount | QA-US6-DB-01, QA-US6-API-03, QA-US6-UNIT-01 | API, DB, UNIT |
| PLAN-US6-04 | refresh | QA-US6-DB-02, QA-US6-UI-01 | DB, UI |
| PLAN-US4-01 | Scenarioถอนก่อนเริ่ม | QA-US4-API-01, QA-US4-API-02, QA-US4-API-12, QA-US4-API-13, QA-US4-API-14, QA-US4-API-15, QA-US4-API-16, QA-US4-API-17, QA-US4-API-18, QA-US4-API-19, QA-US4-API-20, QA-US4-API-21 | API |
| PLAN-US4-02 | Scenarioห้ามหลังเริ่ม | QA-US4-API-05, QA-US4-API-06, QA-US4-API-07, QA-US4-API-08, QA-US4-API-09, QA-US4-API-10, QA-US4-API-11 | API |
| PLAN-US4-03 | retry/race | QA-US4-API-03, QA-US4-DB-01, QA-US4-DB-02, QA-US4-DB-03, QA-US4-DB-04, QA-US4-DB-05, QA-US4-DB-06, QA-US4-DB-08 | API, DB |
| PLAN-US4-04 | กลับเข้าร่วม | QA-US4-API-04, QA-US4-DB-07 | API, DB |
| PLAN-US4-05 | UIยืนยัน | QA-US4-UI-01, QA-US4-UI-02, QA-US4-UI-03, QA-US4-UI-04, QA-US4-UI-05, QA-US4-UI-06, QA-US4-UI-07 | UI |
| PLAN-US2-01 | Scenarioค้นหาตามเงื่อนไข | QA-US2-API-01, QA-US2-API-02, QA-US2-API-03, QA-US2-API-04, QA-US2-API-05, QA-US2-API-13, QA-US2-API-14 | API |
| PLAN-US2-02 | วันเวลา | QA-US2-API-06, QA-US2-API-07, QA-US2-API-08, QA-US2-API-09 | API |
| PLAN-US2-03 | state | QA-US2-API-10, QA-US2-API-11, QA-US2-API-12 | API |
| PLAN-US2-04 | Scenarioไม่พบ | QA-US2-API-15, QA-US2-API-16 | API |
| PLAN-US2-05 | validation | QA-US2-API-17, QA-US2-API-18, QA-US2-API-19, QA-US2-API-20, QA-US2-API-21, QA-US2-API-22, QA-US2-UI-01, QA-US2-UI-02, QA-US2-UI-03, QA-US2-UI-04, QA-US2-API-23 | API, UI |
| PLAN-US14-01 | Scenarioดาวรีวิว | QA-US14-API-01, QA-US14-API-02, QA-US14-API-03, QA-US14-UNIT-02 | API, UNIT |
| PLAN-US14-02 | unique/cache | QA-US14-DB-01, QA-US14-DB-02, QA-US14-DB-03 | DB |
| PLAN-US14-03 | publicread | QA-US14-API-04, QA-US14-UI-01, QA-US14-API-08 | API, UI |
| PLAN-US14-04 | No-show | QA-US14-API-06, QA-US14-DB-04, QA-US14-UNIT-01 | API, DB, UNIT |
| PLAN-US14-05 | flag/privacy | QA-US14-API-05, QA-US14-UI-02, QA-US14-API-07 | API, UI |

[Inventory พร้อม steps/expected และ execution fields](sprint-2-cases.csv) · [Scope, fixtures, handoff และข้อจำกัด](README.md)
