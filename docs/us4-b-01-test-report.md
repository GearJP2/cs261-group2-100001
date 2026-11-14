# US4 Backend — Task70 API และผลตรวจรับ

งาน `S2-US4-B-01` / [Issue #85](https://github.com/GearJP2/cs261-group2-100001/issues/85)
ตรวจ local วันที่ 14 พฤศจิกายน 2026; ผู้ตรวจที่รอ: Austin (@Siestashi)
อ้างอิง [policy](us4-leave-party-policy.md), [API contract](us4-leave-party-api-contract.md) และ [แบบ test cases](us4-leave-party-test-cases.md)

## สิ่งที่เปลี่ยน

เปิด `POST /api/v1/parties/{party_id}/leave` ชื่อ route `party-leave` ไม่มี slash ท้าย โดย view `leave_party_api` เรียก `leave_party` ของ Task69 ที่มีอยู่แล้ว ไม่เปลี่ยน schema หรือกฎ service
ใช้ university session guard และ CSRF middleware เดิม รับ body ว่างหรือ JSON `{}` เท่านั้น ไม่รับ actor จาก client
สำเร็จ 200 ด้วย `data: {party_id, is_member: false, left_at}`; เรียกซ้ำขณะถอนแล้วคืนเวลาเดิม มี no-store และ error envelope ตาม contract
ไม่มี UI ถอนตัวในชิ้นงานนี้

## Automated tests ที่รันจริง

| ส่วน | คำสั่ง / หลักฐานใน source | ผล |
| --- | --- | --- |
| HTTP + service/DB เดิม | `docker compose exec -T backend python backend/manage.py test parties.test_leave_api parties.test_leave --noinput --verbosity 0` | ผ่าน 20 tests |
| Regression ของ API เดิม | `docker compose exec -T backend python backend/manage.py test parties.test_management_api parties.test_cancellation_api parties.test_join_requests --noinput --verbosity 0` | ผ่าน 53 tests |
| Checks ทั้งโปรเจกต์ | `make verify` | ผ่าน checks/lint/format และ 580 tests (skip 1); ดูเหตุผล skip ด้านล่าง |
| Runtime smoke | `make smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS |
| Whitespace | `git diff --check` | ผ่าน |

เคสที่ skip คือ UT-US14-API-06 เพราะ policy ยังไม่ยืนยันใน #100/#105 เป็นงาน US14 ที่ไม่เกี่ยวกับ leave API

`backend/parties/test_leave_api.py` ใช้ Django Client เปิด `enforce_csrf_checks=True` ยิงผ่าน URL/middleware จริง โดย university session เป็น local test fixture ไม่เรียก TU provider:

- success/retry คืนข้อมูลเดิม คง membership row และ joined_at; Detail แสดง count/slots/state หลังถอน; members API ปฏิเสธผู้ถอนแล้ว
- body ว่างผ่าน; malformed JSON, array/null/boolean, UTF-8 ผิด, body ที่มี user_id/membership_id/left_at และ content-type ผิดได้ 400 โดย membership ไม่เปลี่ยน
- Host, nonmember, Party ไม่มีจริง, เริ่มตรง boundary และยกเลิก ได้ status/error code ตาม contract
- anonymous และ session ที่ไม่ผ่าน university identity ถูกปฏิเสธ
- CSRF หาย/ผิดและ Origin ไม่เชื่อถือถูกปฏิเสธ; method อื่นได้ 405 และ Allow POST

`backend/parties/test_leave.py` ของ Task69 ตรวจ transaction/rollback, Open/Full, Pending/Rejected, การกลับเข้าร่วมใหม่, ลำดับ Host/nonmember/cancelled/time และ PostgreSQL connection แยกสำหรับถอนพร้อมกัน/แข่ง approve/รอ lock จนถึงเวลาเริ่ม ใช้ผลรันเดิมนี้ร่วม ไม่สร้าง tests ซ้ำเพื่ออ้างผลงานใหม่

## Traceability และข้อจำกัด

ใช้ working AC mapping จาก [sequence checklist](sprint-2-sequences/README.md#us4--ถอนตัว): AC1 soft leave/count, AC3 retry/locking, AC4 session actor, AC5 Host/state/time การยืนยันเลขกับ Story ต้นทางยังเป็นหลักฐาน review ของทีม
smoke เป็นการตรวจเว็บทั่วไป ไม่ใช่ manual leave API, browser UAT หรือ TU login จริง; tests นี้ไม่แทนงาน manual API #89 และไม่ได้รันทุก UI case ในแบบทดสอบ Design
ยังไม่อ้างผล GitHub CI, peer review หรือสถานะ dependency จาก local tests การนำผลออก PR ต้องแนบ CI และลิงก์ review จริง

- [ ] Austin review implementation เทียบ policy/contract และผลทดสอบ
- [ ] แนบหลักฐานยืนยัน Design #82 และ S2-PLAN-01 ที่ทีมแจ้งว่าผ่านแล้ว
- [ ] แนบ PR/CI และส่งต่อ manual API #89
