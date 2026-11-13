# Backend

ใช้ Django apps ใน `accounts/`, `core/`, `venues/` และ `parties/` พร้อม config กลางใน `config/` รันและทดสอบผ่าน Docker ตาม [คู่มือ development](../docs/development.md)

```bash
make up
make verify
```

รันจาก root repository; Python dependencies อยู่ใน requirements.in และ requirements.txt ที่ล็อกเวอร์ชัน/hashes ใช้ `settings.AUTH_USER_MODEL` สำหรับ FK และ `get_user_model()` แทน import built-in User โดยตรง

สร้าง app ใหม่และเพิ่ม INSTALLED_APPS เมื่อเริ่ม domain ถัดไป โดยประสานเจ้าของ schema ก่อน โฟลเดอร์ controllers/routes/services/models/utils เดิมเป็น placeholder; Django ใช้ไฟล์ภายใน app ที่ลงทะเบียนเท่านั้น

## BASE-04 — JSON API รายละเอียด Party

ใช้ Django views และ `JsonResponse` โดยไม่เพิ่ม Django REST Framework หรือ root-level `apps/` ดู contract, ขอบเขต session guard และวิธีตรวจใน [BASE-04 API](../docs/base-04-api.md)

`core.api.require_authenticated_api` ส่งต่อไปใช้ guard มหาวิทยาลัยของ US1-B แล้ว บัญชี local/Admin อย่างเดียวเข้า API ธุรกิจไม่ได้ ชุด `core.test_auth_integration` ตรวจ login/logout ร่วมกับ Party/JoinRequest/Profile โดยจำลองเฉพาะคำตอบ TU ภายนอก

## US3-B — ส่งและอ่านคำขอเข้าร่วม Party

เพิ่ม API ส่ง Pending และอ่านคำขอของผู้ใช้จาก session โดยใช้ Party lock และ unique constraint เดิม รองรับการขอใหม่หลัง Rejected/ถอนตัวตาม schema contract ล่าสุด ดู [US3-B API](../docs/us3-b-api.md) สำหรับ request/response, CSRF, error codes และขอบเขต integration

ผลทดสอบและตารางเทียบเงื่อนไข US3-T-01/02 อยู่ใน [US3-T test report](../docs/us3-t-test-report.md) รวมข้อจำกัดก่อนปิด integration

## US8-B — Public profile API

อ่านโปรไฟล์ตาม User ID ผ่าน `GET /api/v1/users/{user_id}/profile` ใช้ session guard ร่วม และคืนเฉพาะชื่อแสดงผล กีฬาที่สนใจ และเครดิตที่เก็บอยู่ ดู [US8-B API](../docs/us8-b-api.md) สำหรับ contract, พฤติกรรมเมื่อไม่มีโปรไฟล์ และงานที่ยังรอ US8-F/การตรวจ TU จริง

## US9-B2 — Venue API และ schedule validation

อ่านกีฬา สนาม active ตามกีฬา และเวลาเปิดผ่าน API-03–05; ฝั่งสร้าง/แก้ Party import
`venues.services.validate_party_schedule` ใช้ตรงได้ ดู [contract และ errors](../docs/us9-b2-api.md)

## US7-B — สร้าง แก้ไข และยกเลิก Party

เปิด POST `/api/v1/parties`, PATCH `/api/v1/parties/{id}` และ POST `/api/v1/parties/{id}/cancel`
ใช้ university session guard จาก US1 และ CSRF middleware; Edit/Cancel ตรวจ Host ภายใต้ Party lock
ดู [US7 Backend API](../docs/us7-b-api.md) สำหรับ contract, transaction และ tests

## US4-B — ถอนตัวจาก Party

เปิด `POST /api/v1/parties/{id}/leave` รับ body ว่างหรือ JSON `{}` ผ่าน university session/CSRF เดิม
ใช้ service soft leave ของ Task69 และ Party-first lock; ถอนซ้ำไม่คืนที่ว่างเพิ่ม Host ต้องใช้ cancel แทน
ดู [API contract](../docs/us4-leave-party-api-contract.md) และ [ผลตรวจ Task70](../docs/us4-b-01-test-report.md)
