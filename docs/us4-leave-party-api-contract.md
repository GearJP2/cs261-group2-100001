# US4 — Leave Party API / data contract

งาน: `S2-US4-D-01` / [Issue #82](https://github.com/GearJP2/cs261-group2-100001/issues/82)
คนหลัก: Golf (@Seamui) — ผู้ตรวจ: Austin (@Siestashi)
สถานะ: ข้อเสนอสำหรับ review ต่อจาก [กติกาถอนตัว](us4-leave-party-policy.md) ยังไม่มี leave endpoint ใน implementation และยังไม่ใช่มติที่ทีมยืนยันแล้ว

## 1. ส่วนที่ใช้ร่วมกับระบบเดิม

| ส่วน | Source ที่ตรวจเทียบ | การใช้ใน US4 |
| --- | --- | --- |
| Session / university identity | `backend/accounts/decorators.py` | ใช้ `require_authenticated_api` ที่ delegate ไป `require_university_user` เดิม |
| JSON error / CSRF | `backend/core/api.py` | ใช้ `json_error` และ Django CSRF middleware เดิม |
| Request body | `backend/parties/views.py` — create_join_request | ใช้แนว body ว่างหรือ JSON object ว่าง ไม่รับ actor จาก client |
| Membership / capacity | `backend/parties/models.py`, `services.py` | ใช้ membership แถวเดิม, `left_at`, unique `(party, user)`, active count และ Party-first lock |
| อ่านผลล่าสุด | `backend/parties/urls.py`, `views.py` | ใช้ Party Detail และ members API ที่มีอยู่ โดยคงกฎสิทธิ์ของแต่ละ endpoint |

ไม่เพิ่มตาราง migration หรือ counter จำนวนที่ว่าง งานนี้กำหนด contract เท่านั้น ไม่เพิ่ม route/view/service

## 2. Request

`POST /api/v1/parties/{party_id}/leave` ไม่มี slash ท้าย

| ส่วน | Contract |
| --- | --- |
| `party_id` | integer ใน path อ้าง Party ที่ต้องการถอน |
| Authentication | Django session ของผู้ใช้ที่ผ่าน university identity guard เดิม |
| CSRF | cookie และ header `X-CSRFToken` ที่ถูกต้อง ใช้ `GET /api/v1/auth/csrf` กับ session เดียวกัน |
| Content-Type | `application/json` เมื่อมี body |
| Body | body ว่าง หรือ `{}` เท่านั้น |

ตัวอย่าง body:

```json
{}
```

ปฏิเสธ malformed JSON, JSON ที่ไม่ใช่ object เช่น `null`/array, object ที่มี field ใด ๆ และ body ที่ไม่ว่างแต่ Content-Type ไม่ใช่ application/json ด้วย 400 INVALID_INPUT
ไม่รับ `user_id`, `membership_id`, `host_id`, `left_at`, `status` หรือเวลาจาก client แม้เป็น ID ของตนเอง ผู้ถอนมาจาก `request.user` เท่านั้น

## 3. Success response

HTTP **200 OK** ทั้งการถอนครั้งแรกและการยืนยันผลเดิมหลังถอนแล้ว; `Content-Type: application/json` และ `Cache-Control` ต้องมี `no-store` ตาม `never_cache` เดิม

```json
{
  "data": {
    "party_id": 12,
    "is_member": false,
    "left_at": "2030-01-07T09:59:00+07:00"
  }
}
```

| Field | ชนิด | ความหมาย |
| --- | --- | --- |
| `party_id` | integer | ID ของ Party ตาม path |
| `is_member` | boolean | false หลังการถอนสำเร็จหรือยืนยันผลถอนเดิม |
| `left_at` | string | ISO 8601 พร้อม timezone offset ของเวลาถอนที่เก็บใน membership; ไม่เป็น null ใน success |

ใช้ `timezone.localtime(...).isoformat()` ตามรูปแบบ API เดิม ไม่ส่งข้อมูล User, identity, email, student ID หรือ membership ของคนอื่น
ครั้งแรกบันทึกเวลาที่ตรวจผ่านหลังได้ lock; เรียกซ้ำขณะยังถอนอยู่ต้องคืน `left_at` ค่าเดิมโดยไม่เขียนซ้ำ แม้ Party เริ่ม/จบ/ยกเลิกภายหลัง
ผลตอบกลับอธิบายการถอนที่สำเร็จ ณ transaction นั้น ไม่รับประกันว่าสมาชิกหรือ Party จะไม่เปลี่ยนภายหลัง

## 4. Error response และลำดับการตรวจ

ใช้ envelope เดิม:

```json
{
  "error": {
    "code": "HOST_CANNOT_LEAVE",
    "message": "ผู้จัดกิจกรรมต้องใช้การยกเลิกกิจกรรมแทนการถอนตัว"
  }
}
```

| HTTP | code | เงื่อนไข / message ที่เสนอ |
| --- | --- | --- |
| 400 | INVALID_INPUT | body ไม่ตรง contract — รับเฉพาะ JSON object ว่าง |
| 401 | AUTH_REQUIRED | ไม่มี session หรือ session หมดอายุ — กรุณาเข้าสู่ระบบ |
| 403 | ACCOUNT_INACTIVE | guard ได้รับ authenticated user ที่ inactive — บัญชีนี้ถูกระงับการใช้งาน |
| 403 | FORBIDDEN | ไม่ผ่าน university identity guard — กรุณายืนยันบัญชีมหาวิทยาลัย |
| 403 | CSRF_FAILED | CSRF ไม่ผ่าน ใช้ message ของ handler เดิม |
| 403 | HOST_CANNOT_LEAVE | actor เป็น Host แม้ Party ยกเลิกหรือเริ่มแล้ว |
| 403 | NOT_MEMBER | ไม่มี membership ของ actor — คุณไม่ได้เป็นสมาชิกของกิจกรรมนี้ |
| 404 | NOT_FOUND | numeric Party ID ไม่มีจริง — ไม่พบกิจกรรมที่ต้องการ |
| 405 | METHOD_NOT_ALLOWED | method อื่นนอกจาก POST — รองรับเฉพาะ POST; header `Allow: POST` |
| 409 | PARTY_CANCELLED | สมาชิกปัจจุบันถอนครั้งแรกใน Party ที่ยกเลิก — กิจกรรมนี้ถูกยกเลิกแล้ว |
| 409 | PARTY_STARTED | สมาชิกปัจจุบันถอนครั้งแรกเมื่อ `now >= starts_at` รวม Completed — ไม่สามารถถอนตัวเมื่อกิจกรรมเริ่มหรือจบแล้ว |

Frontend แยกพฤติกรรมจาก HTTP status/code ไม่ผูก logic กับประโยค message
CSRF middleware อาจตอบก่อน view; ใน view ใช้ guard → method → body → service
ใน service ใช้ Party existence → Host → membership existence → already-left → cancelled → เวลา → เขียน ตาม policy เดิม ดังนั้นผู้ถอนแล้วได้ 200 ก่อนตรวจสถานะกิจกรรม ส่วนผู้ไม่มี membership ได้ NOT_MEMBER ก่อนสถานะกิจกรรม

Django ModelBackend อาจ resolve session ของบัญชี inactive เป็น anonymous จึงได้ 401; แยกจาก guard ที่ได้รับ inactive authenticated user โดยตรงแล้วได้ 403 ACCOUNT_INACTIVE
GET/HEAD/OPTIONS ที่ผ่าน guard ได้ 405; การตรวจ unsafe method ต้องผ่าน CSRF ก่อนจึงถึง method check
path ที่ไม่ตรง integer route เช่น `abc` หรือ `-1` เป็น routing 404 และไม่รับรอง JSON envelope; integer ที่ไม่มีจริงเข้าถึง view แล้วคืน JSON 404 เมื่อผ่าน validation ก่อนหน้า
network failure หรือ unhandled 5xx ไม่ถือเป็นผลสำเร็จ และไม่รับประกัน JSON error envelope

## 5. Data mutation และ transaction

1. ภายใน `transaction.atomic` ล็อก Party ด้วย `select_for_update` ก่อน membership ของ actor เพื่อใช้ลำดับเดียวกับ approve/join/edit/cancel
2. ตรวจ business checks ตามข้อ 4; สำหรับสมาชิก active อ่าน `timezone.now()` หลังได้ lock แล้วใช้ timestamp เดียวตรวจ `now < starts_at` และเขียน `left_at` ที่ `now == starts_at` ให้ปฏิเสธ
3. ครั้งแรกเปลี่ยนเฉพาะ `PartyMembership.left_at` คงแถว/ID/party/user/joined_at เดิม ไม่แก้ Party.capacity, cancelled_at หรือ JoinRequest
4. already-left ไม่เขียนอะไรเพิ่ม; เมื่อเขียนล้มเหลว rollback ทั้ง transaction และไม่ส่ง success ส่ง success ได้เมื่อ commit ผ่านแล้ว
5. จำนวนสมาชิกใช้ `left_at IS NULL` รวม Host และ `remaining_slots = capacity - active_count` ผ่าน helpers เดิม ไม่เพิ่ม counter แยก การ approve/edit ที่รอ lock ต้องอ่าน count ใหม่ตามลำดับ commit

ถอนแล้วไม่อนุมัติ Pending อัตโนมัติ การกลับเข้าร่วมผ่าน US3 → US10 ตาม [schema contract หัวข้อ 4.1.1](base-02-schema-contract.md) เท่านั้น
ไม่มี idempotency key แยกรอบสมาชิก: หากถอนแล้วได้รับอนุมัติกลับเข้ามาจน `left_at` เป็น null การ POST ใหม่จะถอนรอบใหม่เมื่อผ่านกฎทั้งหมด จึงห้ามนำคำสั่งเก่ามา retry อัตโนมัติหลังกลับเข้าร่วมรอบใหม่

## 6. การใช้ข้อมูลหลังถอน

- หลัง 200 ให้ใช้ `GET /api/v1/parties/{party_id}` อ่าน `is_member`, `member_count`, `remaining_slots` และ `state` ใหม่ ไม่บวกที่ว่างเองใน client เพราะอาจมีการอนุมัติคนอื่นพร้อมกัน
- `GET /api/v1/parties/{party_id}/members` ปัจจุบันอนุญาตเฉพาะ Host/สมาชิกปัจจุบัน ผู้ถอนสำเร็จแล้วจึงได้ 403 FORBIDDEN เมื่อโหลดรายชื่อ ต้องล้างรายชื่อเดิมและแสดงว่าไม่มีสิทธิ์ ไม่ถือว่า leave ล้มเหลว และไม่ retry leave เพื่อแก้การอ่านรายชื่อ
- หาก leave สำเร็จแต่โหลด detail ล้มเหลว ให้คงผลถอนสำเร็จและให้ลองโหลดรายละเอียดใหม่
- หาก network ขาดก่อนทราบผล อาจ commit แล้ว ให้ตรวจสถานะ/ลองส่งซ้ำเฉพาะรอบสมาชิกเดิม อย่าแสดงว่าถอนสำเร็จจาก network error
- หาก 409 ให้โหลดรายละเอียดใหม่เพื่อแสดงสถานะปัจจุบัน; 401 เข้าสู่ login flow; 403/404 แสดงเหตุผลโดยไม่คงข้อมูลเก่าว่าเป็นผลล่าสุด

## 7. Review และ validation

- [ ] Austin ตรวจ request/response/error codes และลำดับ checks ให้ตรง policy
- [ ] ผู้ทำ Frontend รับทราบว่า members API จะปฏิเสธผู้ถอนแล้ว และข้อจำกัด retry ข้ามรอบสมาชิก
- [ ] ยืนยัน dependency S2-PLAN-01 และบันทึกชื่อ/วันที่/ลิงก์ review ก่อน implement ใน S2-US4-B-01

ตรวจครั้งนี้เฉพาะเอกสารเทียบ source, ตัวอย่าง JSON, ลิงก์ไฟล์ภายใน และ whitespace ไม่ได้รัน API, browser, PostgreSQL integration หรือ CI จึงไม่อ้างว่าระบบถอนตัวใช้งานได้แล้ว UI และ test cases ยังเป็นงานถัดไป
