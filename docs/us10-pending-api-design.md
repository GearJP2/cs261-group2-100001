# S2-US10-D-01 — Pending request API contract

สถานะ: **ข้อเสนอพร้อมส่ง review ยังไม่ใช่มติที่ทีมอนุมัติแล้ว**
จัดทำวันที่ 30 ตุลาคม 2026 จากโค้ดบน `main` commit `f0a8e59`

- Design: [Task47 / Issue #62](https://github.com/GearJP2/cs261-group2-100001/issues/62) — พีเป็นคนหลัก กอล์ฟเป็นคู่ช่วย
- Implementation ที่รับต่อ: [Task50 / Issue #65](https://github.com/GearJP2/cs261-group2-100001/issues/65)
- ภาพรวม: [US10 / Issue #55](https://github.com/GearJP2/cs261-group2-100001/issues/55), [Trello Task47](https://trello.com/c/CbIcab6g)
- Design ที่เกี่ยวข้อง: [Sequence diagram](sprint-2-sequences/us10.mmd), [คำอธิบายและ AC mapping](sprint-2-sequences/README.md), [Task48 / Issue #63](https://github.com/GearJP2/cs261-group2-100001/issues/63)

## 1. ขอบเขตและหลักฐานจากโค้ด

ออกแบบการอ่านรายการคำขอ Pending บนหน้า Party Detail ให้เฉพาะ Host ของ Party นั้น พร้อมสิทธิ์ ข้อมูลตอบกลับ ข้อผิดพลาด และการส่งต่อให้ Frontend/Backend
ครอบคลุม AC1 เฉพาะส่วนข้อมูลก่อนตัดสิน, AC3 เรื่องสิทธิ์ และ AC4 เรื่องการแยกสิทธิ์อ่านจากสิทธิ์อนุมัติ ไม่รับรอง AC ของ US10 ทั้ง Story ว่าเสร็จ

การอนุมัติ/ปฏิเสธเป็น US10-B-02/B-03; การล็อกเพื่อเปลี่ยนสมาชิกและ constraints เป็นงานร่วมกับเจ้าของ Database ไม่เพิ่ม schema, migration, environment variable หรือ dependency ในงาน Design นี้

| สิ่งที่ตรวจ | พฤติกรรมที่พบ ณ baseline | Source |
| --- | --- | --- |
| Route | GET ที่ `/join-requests/pending`; `/join-requests` ใช้ POST ส่งคำขอเดิมของ US3 | [parties/urls.py](../backend/parties/urls.py) |
| View `join_requests` | ตรวจ method → หา Party → ตรวจ Host → กรอง Pending; อ่าน `user__profile` ร่วมกัน | [parties/views.py](../backend/parties/views.py) |
| สิทธิ์ | `require_university_user` ตรวจ session/identity ก่อนเข้า view; ไม่เรียก TU API ใหม่ใน GET นี้ | [accounts/decorators.py](../backend/accounts/decorators.py) |
| ข้อมูล | คืน `id`, `display_name`, `created_at`; ไม่มี profile ใช้ชื่อ `ผู้ใช้`; เรียง `created_at` จากเก่าไปใหม่ | [parties/views.py](../backend/parties/views.py) |
| Party state | ไม่มี state gate ใน GET; Host อ่าน Pending ได้แม้เต็ม/เริ่ม/จบ/ยกเลิกแล้ว | [parties/views.py](../backend/parties/views.py) |
| Frontend | `initPartyDetail` เรียก `/pending` เมื่อ `party.is_host`; ใช้รหัสคำขอเรียก `/decision`; helper คืน `payload.data` | [app.js](../frontend/static/js/app.js) |
| เทสต์เดิม | `test_host_can_list_and_approve_pending_request` ตรวจ 200 และรหัสรายการแรก แล้วทดสอบ approve ต่อ ยังไม่ใช่หลักฐานครบทุกเคสอ่านรายการ | [test_join_requests.py](../backend/parties/test_join_requests.py) |

ข้อค้นพบข้างต้นมาจากการอ่าน source ไม่ใช่ผลรัน API/Browser ในงานนี้

## 2. ข้อเสนอและจุดที่ต้องยืนยัน

| ID | ข้อเสนอสำหรับ review | เหตุผล / ผลต่อ implementation |
| --- | --- | --- |
| D01 | ใช้ `GET /api/v1/parties/{party_id}/join-requests/pending` เดิม | ตรงกับ caller และ diagram ปัจจุบัน; ไม่เพิ่ม alias หรือเปลี่ยน route ในงาน Design |
| D02 | คืนเฉพาะสาม field เดิมและ fallback `ผู้ใช้` เมื่อไม่มี profile | Frontend มีข้อมูลพอสำหรับแสดงผู้ขอและเลือกคำขอ; ไม่ขยายข้อมูลส่วนตัว |
| D03 | Host อ่าน Pending ได้ทุก Party state | รักษาพฤติกรรมเดิมและแสดงรายการค้างได้; อ่านได้ไม่ได้แปลว่าอนุมัติได้ |
| D04 | เรียง `created_at` ASC แล้ว `id` ASC เมื่อเวลาตรงกัน | เพิ่มความแน่นอนของลำดับ; baseline ยังไม่มี tie-break ด้วย `id` ต้องเติมใน Task50 หากรับข้อเสนอนี้ |
| D05 | อ่านทุกรายการ Pending ไม่มี pagination หรือ query filter ในขอบเขตนี้ | รักษา contract เดิม; ถ้าจำเป็นต้องแบ่งหน้า ให้ทีมกำหนด contract แยกก่อน |

**ข้อขัดแย้ง D01:** Issue #55 ระบุ GET `/join-requests` แต่ baseline ใช้ `/join-requests/pending` เอกสารนี้เสนอเก็บของเดิม ไม่ได้ประกาศแก้ข้อกำหนดแทนทีม
ถ้าทีมเลือกตาม #55 ให้ Task50 เพิ่ม GET dispatch ร่วมกับ POST ของ US3 โดยรักษา POST เดิม และปรับ callers/tests/เอกสาร/diagram ให้ตรงกัน; ต้องระบุนโยบายรองรับ `/pending` เดิมก่อนเปลี่ยน
การเลือก endpoint `/approve`, `/reject` หรือ `/decision` เป็นข้อสรุปของ Task48/B-02/B-03 ไม่ตัดสินแทนในเอกสารนี้

## 3. Request และสิทธิ์

```http
GET /api/v1/parties/12/join-requests/pending
Accept: application/json
```

ตัวเลขเป็นตัวอย่าง ไม่มี slash ท้าย ใช้ session cookie ของผู้ล็อกอินผ่านระบบเดิม; ใน browser ใช้ `credentials: "same-origin"` ไม่ส่ง password, TU key, `host_id` หรือ `user_id` เพื่อระบุตัวผู้เรียก
GET นี้ไม่ต้องมี body หรือ `X-CSRFToken` และไม่รับประกันว่าจะออก CSRF cookie ให้ การ POST ตัดสินคำขอยังต้องใช้ CSRF flow เดิมแยกต่างหาก

สิทธิ์อ่านผ่านเมื่อครบทุกข้อ:

1. session ระบุผู้ใช้ที่ authenticated และ active
2. `university_identity_id` ใน server session อ้าง identity ของผู้ใช้คนเดียวกัน, provider `tu`, มี `student_verified_at` และ `eligibility_checked_at`
3. พบ Party ตาม path และ `party.host_id == request.user.pk`

ใช้ Host จาก Party โดยตรง ไม่อนุมานจาก membership; ผู้สมัคร สมาชิกทั่วไป ผู้ถอนตัว และ Host ของ Party อื่นไม่มีสิทธิ์อ่าน
Query เช่น `?user_id=...&host_id=...&party_id=...&status=Approved` ต้องไม่เปลี่ยน actor, Party หรือ Pending filter ปัจจุบัน view ไม่อ่าน query เหล่านี้; ข้อเสนอนี้คงพฤติกรรม ignore ไม่เพิ่ม 400 validation โดยไม่มีข้อตกลง

| State ของ Party | GET โดย Host ที่ผ่าน guard (ข้อเสนอ D03) | ผลต่อการตัดสิน |
| --- | --- | --- |
| Open | 200 พร้อม Pending หรือรายการว่าง | ตรวจใหม่ใน decision API |
| Full | 200 พร้อม Pending หรือรายการว่าง | การอ่านไม่จองหรือคืนที่ว่าง |
| InProgress / Completed | 200 พร้อม Pending หรือรายการว่าง | ไม่ใช้ GET เป็นหลักฐานว่าอนุมัติได้ |
| Cancelled | 200 พร้อม Pending หรือรายการว่าง | คงคำขอค้างตามข้อมูลจริง ไม่เปลี่ยนเป็น Rejected |

## 4. Success response และข้อมูลที่อนุญาต

HTTP 200, `Content-Type: application/json`; response เฉพาะผู้ใช้ต้องมี `Cache-Control` ที่ห้ามเก็บ (`no-store`) ตาม `never_cache` เดิม

```json
{
  "data": [
    {
      "id": 45,
      "display_name": "ผู้ขอเข้าร่วม",
      "created_at": "2026-10-30T16:00:00+07:00"
    }
  ]
}
```

| Field | ชนิด | ความหมาย |
| --- | --- | --- |
| `id` | integer | `JoinRequest.pk` ไม่ใช่ `User.pk`; Frontend ใช้เลือกคำขอเมื่อตัดสิน |
| `display_name` | string | ชื่อจาก UserProfile; ไม่มี profile ใช้ `ผู้ใช้` ไม่ใช้ username/email แทน |
| `created_at` | string | ISO 8601 พร้อม offset; baseline ใช้ `timezone.localtime` กับ `Asia/Bangkok` |

รายการต้องมาจาก `JoinRequest` ที่ `party_id` ตรง path และ `status=Pending` เท่านั้น ไม่ใช้ PartyMembership เป็นรายการคำขอ
ไม่ส่ง `user_id`, email, student ID, username, password/hash, provider identity, token หรือ object User ทั้งก้อน; ไม่เพิ่ม field อื่นโดยไม่อัปเดต allowlist
ชื่อที่มาจากข้อมูลผู้ใช้ต้อง render เป็นข้อความ เช่น `textContent` ไม่ตีความเป็น HTML

ไม่มี Pending ให้ตอบ 200 ด้วย array ว่าง ไม่ใช่ null/404:

```json
{"data": []}
```

การเปิดคำขอเดิมใหม่ตาม US3 เปลี่ยน `created_at` ของแถวเดิมได้ จึงอาจทำให้ลำดับเปลี่ยนหลัง refresh
ผล GET เป็นข้อมูลขณะอ่าน ไม่รับประกันว่าคำขอยัง Pending เมื่อกดปุ่มภายหลัง; decision API ต้องตรวจสถานะ/สิทธิ์/ที่ว่างใหม่เสมอ
GET ไม่แก้ JoinRequest, PartyMembership, Party.capacity หรือจำนวนที่ว่าง และไม่ต้องใช้ row lock แบบการอนุมัติ

## 5. Errors และลำดับการตรวจ

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "เฉพาะผู้จัดกิจกรรมเท่านั้นที่ดูคำขอได้"
  }
}
```

Frontend ใช้ status/code แยกพฤติกรรม และแสดง message เป็นข้อความ ไม่ผูก logic กับประโยคภาษาไทยแบบตายตัว

| HTTP | code | เงื่อนไข |
| --- | --- | --- |
| 401 | AUTH_REQUIRED | ไม่มี session, หมดอายุ หรือ logout แล้ว |
| 403 | ACCOUNT_INACTIVE | guard ได้รับ authenticated user ที่ inactive; ดูหมายเหตุ backend ด้านล่าง |
| 403 | FORBIDDEN | ไม่ผ่าน university identity guard หรือผ่านแล้วแต่ไม่ใช่ Host |
| 404 | NOT_FOUND | ผู้เรียกผ่าน guard แล้ว แต่ไม่พบ Party ตาม numeric ID |
| 405 | METHOD_NOT_ALLOWED | ผ่าน guard แล้วใช้ method อื่น; มี `Allow: GET` |

ลำดับใน view ปัจจุบันคือ university guard → method → Party existence → Host → query
จึงได้ 401 ก่อนตรวจ Party สำหรับ anonymous; ผู้ผ่าน guard ที่ใช้ ID ไม่มีจริงได้ 404 ไม่ใช่ 403 และไม่เปลี่ยนเป็นนโยบายซ่อน existence ในงานนี้
ModelBackend ปัจจุบันอาจ resolve session ของบัญชีที่ถูกปิดเป็น anonymous จึงได้ 401; แยกจากการทดสอบ guard โดยส่ง inactive user โดยตรงที่ได้ 403

POST/PUT/PATCH/DELETE ที่ไม่ผ่าน CSRF อาจถูก middleware ตอบ 403 `CSRF_FAILED` ก่อน view; การตรวจ 405 ด้วย unsafe method ต้องแนบ CSRF ที่ถูกต้อง
GET/HEAD/OPTIONS ไม่ต้องใช้ CSRF token แต่ endpoint นี้รองรับเฉพาะ GET (HEAD/OPTIONS ผ่าน guard แล้วได้ 405)
Path ที่ไม่ตรง `<int:party_id>` เช่น `abc` หรือ `-1` ใช้ routing 404 ของ Django ซึ่งไม่รับรอง JSON envelope นี้; numeric ID ที่ไม่มีจริง เช่น 0 เข้าสู่ view ได้แล้วตอบ JSON 404 เมื่อผ่าน guard
Network failure/5xx เป็น error/retry ไม่แปลงเป็น 200 หรือรายการว่าง และไม่รับประกัน JSON สำหรับ server error ที่ไม่ได้จัดการ

## 6. ส่งต่อ Frontend และ review

[เคสตรวจรับ Task50](us10-pending-api-test-cases.md) ระบุ fixtures, steps, expected และ AC mapping พร้อมสถานะ Not run ทุกเคส ใช้ประกอบ review ก่อนนำไป implement

Frontend ทำส่วน Pending ใน Party Detail เฉพาะเมื่อ detail ระบุ `is_host`; Backend ต้องตรวจซ้ำทุกครั้ง การซ่อน UI ไม่แทนการตรวจสิทธิ์
ขณะโหลดให้แสดง loading; สำเร็จว่างแสดง `ยังไม่มีคำขอเข้าร่วม`; สำเร็จมีข้อมูลแสดงชื่อ และใช้ `id` ของคำขอผูกกับปุ่มตัดสิน
401 ให้เข้าสู่ login flow, 403 แสดงไม่มีสิทธิ์และล้างรายการเก่า, 404 แสดงไม่พบกิจกรรม, network/5xx แสดง retry และไม่คงข้อมูลของ Party ก่อนหน้าราวกับเป็นผลปัจจุบัน
การปิดปุ่มและ refresh หลัง approve/reject อยู่ Task48/US10-F; เอกสารนี้กำหนดข้อมูลที่อ่านให้ใช้ร่วมกัน

ก่อนส่ง Task50 ให้ตรวจรับ D01–D05 และบันทึกผลใน PR/Issue #62 โดยระบุชื่อผู้ตรวจ วันที่ และลิงก์ข้อสรุปจริง:

- [ ] พีและกอล์ฟตรวจสิทธิ์/ข้อมูล/errors และส่วนที่ reuse จาก implementation
- [ ] ผู้ทำ Frontend ตรวจ URL, response และ loading/empty/error ที่นำไปใช้
- [ ] บันทึกมติ D01–D05 รวมการแก้ข้อขัดแย้งกับ #55 และข้อสรุป Planning ที่เกี่ยวข้อง
- [ ] ส่งต่อรายการช่องว่างและ test cases ให้ Task50 โดยไม่ปิด #65 หรือ #55 แทนงาน implementation

Checklist ยังไม่ติ๊กเพราะยังไม่มีผล review ของเอกสารฉบับนี้ การสร้างเอกสารหรือ commit ไม่ใช่การอนุมัติ contract แทนทีม

## 7. ผลตรวจเอกสารและข้อจำกัดของการส่งมอบ

ตรวจ local วันที่ 30 ตุลาคม 2026: ตัวอย่าง JSON ทั้ง 3 ชุด parse ได้, ลิงก์ไฟล์ภายในเอกสาร contract/test cases อ้างไฟล์ที่มีจริง, code fences ครบคู่ และมี API case IDs ไม่ซ้ำ 18 เคสที่ยังระบุ Not run; ตรวจ whitespace ด้วย `git diff --check`
ตรวจเทียบ route, field allowlist, guard, เวลา, fallback และ caller กับ source ตามตารางข้อ 1 โดยไม่แก้ production code หรือ schema

ไม่ได้รัน `make verify`/`make smoke`, API runtime, browser UAT หรือ TU จริง เพราะรอบนี้แก้เฉพาะเอกสาร จึงไม่อ้างว่า implementation หรือ tests ตามเคสใหม่ผ่านแล้ว
สิ่งที่รอคือมติ D01–D05 และ review ของกอล์ฟ/Frontend; เมื่อได้มติให้บันทึกหลักฐานและอัปเดตเอกสารก่อนใช้ปิด Design/ส่งต่อ Task50
