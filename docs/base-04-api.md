# BASE-04 — Party detail JSON API

ใช้ Django JSON views และ `JsonResponse` ตาม framework decision ของทีม ไม่มี DRF, serializer dependency หรือโมเดลชุดใหม่ โค้ดอ่านโมเดลและ migrations ของ BASE-02 ใน `backend/` โดยตรง

## ขอบเขตที่เพิ่ม

- `backend/core/api.py`: `json_error` และ `require_authenticated_api` สำหรับ JSON API โดย guard ส่งต่อไปใช้ `accounts.decorators.require_university_user` ของ US1-B
- `backend/parties/services.py`: `count_active_members(party)` และ `get_party_state(party, now=None, *, member_count=None)` ให้ฟีเจอร์ Party ใช้ร่วมกัน ค่า `member_count` ที่ส่งเข้าต้องเป็นจำนวน active memberships จากฐานข้อมูล ไม่รับจาก client
- `backend/parties/views.py` / `urls.py`: API-02 อ่านรายละเอียด Party และเชื่อมผ่าน `backend/config/urls.py`
- tests ใช้ Django test database และสร้างข้อมูลจริงผ่าน ORM; ไม่มี mock-success endpoint หรือ seed บัญชีมหาวิทยาลัย

## Endpoint และ response

### รายการปาร์ตี้และค้นหา

`GET /api/v1/parties` ยังคงคืนรายการปาร์ตี้ที่เปิดรับและมีที่ว่างตามเดิม เมื่อไม่ส่งพารามิเตอร์แบ่งหน้า จะคืนสูงสุด 50 รายการในรูป `{"data": [...]}` เพื่อรองรับผู้เรียกเดิม

หน้า Search ส่งตัวกรองไป API ก่อนนับและแบ่งหน้า:

```text
GET /api/v1/parties?q=แบดมินตัน&sport_id=1&venue_id=2&date=2026-10-20&time_from=17:00&time_to=20:00&spots=2&sort=soonest&page=1&page_size=12
```

รองรับคำค้นในชื่อ/คำอธิบายปาร์ตี้ ชื่อผู้จัด ชื่อกีฬา ชื่อสนาม และที่ตั้งสนาม; ตัวกรองกีฬา สนาม วันที่ เวลาเริ่ม และจำนวนที่ว่างใช้ร่วมกันแบบ AND ค่า `sort` รองรับ `soonest` และ `latest` โดย `page` เริ่มที่ 1 และ `page_size` มีค่าสูงสุด 100 เมื่อส่ง `page` หรือ `page_size` response จะมี `page`, `page_size` และ `total` ซึ่งนับหลังใช้ตัวกรองและก่อนตัดหน้า รายการในแต่ละหน้าจึงไม่ทำให้ผลที่อยู่หลัง 50 รายการหายไป

พารามิเตอร์ที่ไม่ถูกต้องตอบ HTTP 400 `INVALID_INPUT` พร้อม `fields` ที่ระบุชื่อพารามิเตอร์ รายการยังคงจำกัดเฉพาะปาร์ตี้ที่ยังไม่เริ่ม ไม่ถูกยกเลิก และยังไม่เต็ม

`GET /api/v1/parties/{party_id}` ใช้ ID จำนวนเต็ม ไม่มี slash ท้าย ต้องมี session มหาวิทยาลัยที่ผ่าน guard ของ US1-B บัญชี local/Admin อย่างเดียวไม่เพียงพอ

สำเร็จตอบ HTTP 200:

```json
{
  "data": {
    "id": 12,
    "title": "Badminton after class",
    "description": "เล่นแบดมินตัน 2 ชั่วโมง",
    "host": {"id": 7, "display_name": "Gear"},
    "sport_id": 1,
    "venue_id": 2,
    "starts_at": "2026-10-20T17:00:00+07:00",
    "ends_at": "2026-10-20T19:00:00+07:00",
    "capacity": 4,
    "member_count": 1,
    "remaining_slots": 3,
    "state": "Open",
    "is_host": false,
    "is_member": false
  }
}
```

ตัวเลขและเวลาในตัวอย่างเป็นเพียงคำอธิบาย contract; endpoint อ่านฐานข้อมูลจริงเสมอ

- นับสมาชิกจาก `PartyMembership.left_at IS NULL` รวม Host เมื่อมี active membership; ไม่เพิ่ม Host เข้า count เองและไม่นับ JoinRequest
- `remaining_slots = capacity - member_count` การป้องกันสมาชิกเกิน capacity เป็นหน้าที่ของบริการเขียนข้อมูล
- สถานะเรียก service กลางตามลำดับ Cancelled → Completed → InProgress → Full → Open; ที่ `starts_at` ถือว่าเริ่ม และที่ `ends_at` ถือว่าจบแล้ว ใช้ count เดียวกับ response
- `is_host` / `is_member` ใช้ `request.user` เท่านั้น query/body ไม่เปลี่ยนตัวผู้กระทำ
- วันเวลาส่งแบบ ISO 8601 พร้อม offset ตาม timezone ของแอป (`Asia/Bangkok`)
- ส่งเฉพาะฟิลด์ในตัวอย่าง ไม่ส่ง username, email, password hash, provider identity, token หรือ session
- ถ้า Host ไม่มี UserProfile ใช้ข้อความกลาง “ผู้จัดกิจกรรม” เพื่อรองรับบัญชี local/ข้อมูลเดิมโดยไม่เปิดเผย login identifier; ไม่สร้าง profile ให้ระหว่าง GET
- response มี `Cache-Control` ป้องกันการเก็บผลที่ขึ้นอยู่กับผู้ใช้ไว้ใน cache

## Error contract

```json
{"error": {"code": "NOT_FOUND", "message": "ไม่พบกิจกรรมที่ต้องการ"}}
```

| HTTP | code | กรณี |
| --- | --- | --- |
| 401 | AUTH_REQUIRED | ไม่มีผู้ใช้ที่ผ่าน authentication จาก session |
| 403 | ACCOUNT_INACTIVE | guard ได้รับ authenticated user ที่ `is_active=False` |
| 403 | FORBIDDEN | ไม่มี identity marker ที่ถูกต้องใน session หรือ identity ไม่ผ่านนโยบายของ US1-B |
| 404 | NOT_FOUND | ผู้ใช้ผ่าน guard แต่ไม่พบ Party ID |
| 405 | METHOD_NOT_ALLOWED | ผู้ใช้ผ่าน guard แต่ใช้ method อื่น; ส่ง `Allow: GET` |

`json_error` รองรับ `fields` เมื่อจำเป็นต้องส่งข้อผิดพลาดรายฟิลด์ด้วย URL ที่ไม่ตรง routing เช่น ID ที่ไม่ใช่จำนวนเต็มยังเป็น Django routing 404 ปกติ

CSRF middleware เดิมยังทำงาน ไม่มี `csrf_exempt` คำขอ unsafe ที่ไม่ผ่าน CSRF อาจถูกปฏิเสธก่อนเข้า view; US3-B เพิ่ม failure handler ให้ `/api/v1/` ตอบ JSON `403 CSRF_FAILED` แล้ว ส่วนหน้า HTML/admin ใช้ response ของ Django ตามเดิม ดู [US3-B API](us3-b-api.md)

## การเชื่อม US1-B และขอบเขตที่เหลือ

ตั้งแต่รอบ integration วันที่ 19 ตุลาคม 2026 `require_authenticated_api` ใช้ guard ของ US1-B โดยตรง จึงใช้กฎเดียวกับ `/api/v1/me` และ Venue APIs โดยไม่ทำ login หรือ eligibility policy อีกชุด ไม่มี import วนกลับจาก accounts.decorators เข้า core.api

Guard ตรวจ authenticated/active user และ `university_identity_id` ใน session ฝั่งเซิร์ฟเวอร์ ต้องเป็นเลขจำนวนเต็มบวกที่อ้าง identity ของ user เดียวกัน, provider `tu`, และมี `student_verified_at` กับ `eligibility_checked_at` ครบ เมื่อผ่านเพิ่ม `request.university_identity` ให้ view การส่ง user_id/student_verified/identity ID ผ่าน query หรือ body ไม่ให้สิทธิ์เพิ่ม

API ที่ใช้ผ่าน BASE-04 ได้แก่ Party detail, ส่ง/อ่าน JoinRequest และ public profile เมื่อไม่ผ่าน guard จะปฏิเสธก่อนค้นหา resource หรือเขียนข้อมูล ส่วน Host/Member/state/capacity ยังตรวจใน view/service ตามเดิม หน้าแรก health endpoints และ Django admin ใช้นโยบายเดิมของตน

นโยบาย US1 ปัจจุบันใช้ผลจาก login ล่าสุดและ session อายุ 24 ชั่วโมง ไม่เรียก TU ตรวจสิทธิ์ใหม่ทุก request และไม่ต่ออายุเพียงเพราะเรียก API การลบ identity/ล้างหลักฐานในฐานข้อมูลทำให้คำขอถัดไปถูกปฏิเสธ แต่สถานะที่เปลี่ยนเฉพาะฝั่ง TU ยังต้องรอนโยบาย recheck ของทีม ดู [US1 report](US1-backend-report.md)

Django ModelBackend ปัจจุบันไม่คืน inactive user จาก session: เมื่อปิดบัญชี session เดิมจะถูกมองเป็น anonymous และ API ตอบ 401 ส่วน 403 ทดสอบตรง guard เมื่อ `request.user` เป็น inactive user จริง ไม่เปลี่ยน authentication backend เพียงเพื่อบังคับ status code; ให้ทีม US1 ตกลงพฤติกรรมนี้ใน policy กลาง

งานนี้ใช้ Login/Logout และ `/api/v1/me` ที่ US1-B มีแล้ว ไม่เพิ่ม endpoint หรือเปลี่ยน schema/env/dependency ส่วนหน้า HTML `/parties/{id}` (BASE-04-02 ของวี/เนท) และการตรวจผ่านหน้าเว็บยังเป็นงานแยก การส่ง/อ่านคำขอและโปรไฟล์ใช้ API เดิมของ US3-B/US8-B

Frontend ควรใช้ status/code ตัดสินผล ไม่ผูกกับข้อความไทย: AUTH_REQUIRED ใช้ข้อความจาก US1 คือ “กรุณาเข้าสู่ระบบ” และ ACCOUNT_INACTIVE ใช้ “บัญชีนี้ถูกระงับการใช้งาน” แทนข้อความเดิมของ BASE-04

## ตรวจงาน

รันจาก root repository:

```bash
make verify
make up
make smoke
```

Tests ใหม่ตรวจ JSON helper, guard anonymous/inactive/active, URL จริงผ่าน session, response allowlist, การปลอม user_id/host_id, membership ปัจจุบัน/ถอนตัว/Pending/Rejected, Party ไม่พบ, Host ไม่มี profile, method ที่ไม่อนุญาต, session ที่ยกเลิก/บัญชีถูกปิด, จำนวนที่ว่าง และลำดับสถานะรวมขอบเขตเวลา โดยไม่ถือว่า tests ของ local session เป็นการเชื่อมมหาวิทยาลัยสำเร็จ

Regression tests ของ API ใช้ `accounts.test_support.force_university_login` เพื่อสร้าง identity/session fixture เฉพาะฐานทดสอบ ไม่ใช่ช่องทาง login ของแอป และไม่แก้หลักฐานของ identity ที่มีอยู่ให้ผ่านใหม่ ส่วน `core.test_auth_integration` เรียก login/logout endpoint จริงผ่าน Django client โดย mock เฉพาะการเรียก TU ภายนอก และเปิด CSRF checks

```bash
docker compose run --rm -T backend python backend/manage.py test core.test_auth_integration --noinput --verbosity 2
```

ชุด integration ตรวจ `/me` และ API ของพีทั้ง 4 endpoints: login แล้วใช้งานได้, local/Admin login ไม่พอ, marker ผิดรูปแบบ/ของคนอื่น, provider ผิด, หลักฐานถูกถอน/identity ถูกลบ, บัญชีถูกปิด, session หมดอายุ, logout แล้ว replay cookie, CSRF และ provider ปฏิเสธ login โดยยืนยันว่าคำขอที่ถูกปฏิเสธไม่เปลี่ยน JoinRequest/Membership

## ผลตรวจ local วันที่ 14 ตุลาคม 2026

- `make verify` ผ่าน: Django system checks, ไม่มี model change ที่ขาด migration, Ruff lint/format และ tests 40 กรณีบน PostgreSQL (เพิ่มใหม่ 12 กรณี)
- `make up` ผ่าน: backend/database healthy และใช้ migrations เดิมของ BASE-02
- `make smoke` ผ่าน: หน้าแรก, static CSS, liveness และ database readiness
- เรียก `GET /api/v1/parties/1` ผ่าน HTTP จริงโดยไม่มี session ได้ 401 พร้อม JSON `AUTH_REQUIRED`
- ผลเหล่านี้เป็น local checks ไม่ใช่ผล GitHub Actions หรือ UAT ของระบบมหาวิทยาลัย

## ผลตรวจ integration วันที่ 19 ตุลาคม 2026

- Branch `feat/base-04-auth-integration` เริ่มจาก main `cb48b3d` ซึ่งมี US1-B และ US9-B2 แล้ว
- `core.test_auth_integration` ผ่าน 12 tests ใช้ login/logout endpoint ของ US1 และ session จริงในฐานทดสอบ โดย mock เฉพาะคำตอบจาก TU; มี core guard regression เพิ่มอีก 1 กรณีสำหรับ local login ที่ไม่มี identity marker
- `make verify` ผ่าน: Django checks, migration drift check, Ruff lint/format และ 170 tests ทั้งหมดบน PostgreSQL ไม่มี skip รวม JoinRequest concurrency 6 tests
- `make up` และ `make smoke` ผ่าน: HTTP, PostgreSQL readiness, Django template และ static CSS
- แก้ชื่อ route ใน profile acceptance tests 3 จุดเป็น `accounts:user-public-profile` เช่นเดียวกับการแก้ใน PR #47 เพื่อให้ตรวจรวมผ่านบน main ปัจจุบัน
- ไม่มี migration, environment variable หรือ package dependency ใหม่ หากจะทดสอบ TU จริงใช้ configuration ของ US1 ที่มีอยู่แล้ว ไม่ใส่ credentials ใน fixtures
- หลังรวมการเปลี่ยนแปลง US3-T ของ PR #47 เข้ากับ branch นี้ ทุก fixture ที่ต้องเข้าถึง Business API ใช้ `force_university_login`; เคสที่ตั้งใจตรวจ local-only session ยังคงใช้ `force_login` เพื่อยืนยันว่าได้ `403 FORBIDDEN` ผลตรวจรวมของ commit หลังรวมให้ดูจาก CI ของ PR
- ผลนี้พร้อมส่ง review สำหรับ Backend integration แต่ไม่ใช่ CI, การตรวจ TU จริง, UI acceptance หรือการปิด BASE-04-02/US3-T ทั้ง parent
