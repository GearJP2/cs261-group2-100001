# S2-US10-D-01 — เคสตรวจรับ API รายการ Pending

สถานะ: **Test design / Not run** วันที่ 30 ตุลาคม 2026

อัปเดต 1 พฤศจิกายน 2026: implementation Task50 และผล automated checks ของ PEND-01–18 อยู่ใน [รายงาน US10-B-01](us10-b-01-test-report.md) ตาราง Not run ด้านล่างเก็บแผน Design เดิม; Manual UI ยังไม่ได้รัน
อ้างอิง [API contract ฉบับเสนอ review](us10-pending-api-design.md), [Issue #62](https://github.com/GearJP2/cs261-group2-100001/issues/62) และ implementation [Task50 / #65](https://github.com/GearJP2/cs261-group2-100001/issues/65)

เอกสารนี้เป็นสิ่งส่งมอบ Design ไม่ใช่ test report ที่ผ่านแล้ว เคสที่ขึ้นกับข้อเสนอ D01–D05 ต้องปรับตามมติทีมก่อนใช้ตรวจรับ Task50
ไม่ใช้การมีโค้ดเดิมหรือจำนวน tests เดิมแทนผลจริงของเคสด้านล่าง

## 1. วิธีทดสอบและการเชื่อม AC

- เคส API ให้ใช้ Django test client กับฐานข้อมูลทดสอบ PostgreSQL: เป็น **Backend integration tests** เพราะผ่าน routing, guard, view และ ORM ร่วมกัน
- เคส guard ที่สร้าง request/user โดยตรงให้ระบุวิธีแยกจาก session จริง ไม่ใช้ผลนั้นแทนพฤติกรรม ModelBackend
- การยิง HTTP จริงเป็นหลักฐาน Manual API ของงานทดสอบที่เกี่ยวข้อง; การตรวจ loading/empty/error บน browser เป็น Manual UI ไม่ได้ผ่านโดยอัตโนมัติเพราะ backend tests ผ่าน
- ไม่จำลอง concurrency ของ approve ในชุดอ่านนี้; race/rollback ของการตัดสินอยู่ US10-B-02/B-03 และ US10-T-DB

| ส่วนของ Story / diagram | Case IDs ในเอกสารนี้ | ขอบเขตที่ยืนยัน |
| --- | --- | --- |
| AC1: อ่าน Pending ก่อนตัดสิน / diagram GET → query → 200 | PEND-01 ถึง 03, 10 ถึง 12, 16 | รายการ, ลำดับ, ข้อมูล และผลอ่านหลังข้อมูลเปลี่ยน ไม่ยืนยัน approve transaction |
| AC3: university/Host guard / diagram 401/403/404 | PEND-04 ถึง 09, 13 ถึง 15 | ตัวตนจาก session และสิทธิ์เฉพาะ Party |
| AC4: Party state | PEND-17 | ยืนยันข้อเสนอว่าอ่านได้ทุก state ไม่ยืนยันว่าอนุมัติได้ทุก state |
| ข้อกำหนดอ่านอย่างเดียว | ทุกเคส + PEND-18 | ไม่สร้าง/เปลี่ยนคำขอ สมาชิก หรือความจุ |

Case IDs `PEND-*` เป็นรายละเอียดสำหรับ Task50 ไม่แทนหรือประกาศผ่าน checklist `UT-US10-*`/`IT-US10-*` ของทั้ง Story ใน Trello

## 2. ข้อมูลตั้งต้นที่เสนอ

สร้างใหม่ในฐานข้อมูลทดสอบที่แยกจากฐานพัฒนา ไม่รัน seed/reset กับข้อมูลใช้งานเพื่อเตรียมเคสเหล่านี้
ชื่อด้านล่างเป็น fixture aliases ไม่ใช่ user/Party/ID จริงของทีม; ใช้ PK ที่ฐานทดสอบสร้างให้

| Alias | การตั้งค่า |
| --- | --- |
| H1 / H2 | ผู้ใช้ active ที่ผ่าน university guard; เป็น Host ของ P1 / P2 ตามลำดับ |
| A1 / A2 / N1 | ผู้สมัครของ P1; N1 ไม่มี UserProfile ส่วน A1/A2 มีชื่อแสดงผล |
| M1 / R1 | M1 เป็น active member ของ P1 พร้อมคำขอ Approved; R1 มีคำขอ Rejected |
| P1 | Host H1, เวลาเริ่มในอนาคต, capacity 4, active memberships คือ H1 และ M1 จึงเหลือ 2 ที่ |
| P2 | Host H2 มี Pending ของตัวเองไว้ตรวจการปนข้อมูล |
| Q1 / Q2 / Q3 | คำขอ Pending ของ A1 / A2 / N1 ใน P1; กำหนดเวลา Q1 < Q2 < Q3 เพื่อทดสอบลำดับ |
| Q4 / Q5 | Approved ของ M1 / Rejected ของ R1 ใน P1; ตั้ง decided_at/by ให้ตรง constraint |
| Q6 | Pending ใน P2 |

สร้าง session/UniversityIdentity ด้วย test support เดิมหรือ app login ที่ mock เฉพาะ TU boundary แล้วระบุวิธีในผลรัน ไม่ใช้บัญชี TU จริงใน automated fixtures
ไม่ถือว่า `force_login` เพียงอย่างเดียวผ่าน university guard; ต้องมี identity ของ session user และข้อมูลยืนยันตาม contract

ทุกเคสเริ่มจาก fixtures ใหม่ เว้นแต่ขั้นตอนระบุเปลี่ยนข้อมูล ก่อนและหลัง request ให้เทียบ domain snapshot ของ Party, JoinRequest และ PartyMembership; request ที่ถูกปฏิเสธต้องไม่มี `data` ของผู้สมัครใน response

## 3. Test cases

ใช้ URL ที่ทีมยืนยันใน D01; ตัวอย่างด้านล่างหมายถึง `/api/v1/parties/{P1.id}/join-requests/pending` ตามข้อเสนอปัจจุบัน
Actual และผลทุกเคสยังเป็น **Not run** และยังไม่มีผู้ทดสอบ/หลักฐาน runtime

| ID | Precondition / ขั้นตอน | Expected | Actual / ผล |
| --- | --- | --- | --- |
| PEND-01 | session H1; GET P1 | 200 JSON; top-level มี `data` array; ได้ Q1/Q2/Q3 ตามลำดับ; ทุก item มีเฉพาะ `id`, `display_name`, `created_at`; `id` ตรงคำขอไม่ใช่ผู้ใช้ | Not run |
| PEND-02 | session H1; ใช้ P1 ที่มี Q1–Q6 ตาม fixtures แล้ว GET P1 | ไม่มี Q4/Q5 (Approved/Rejected) และ Q6 (Party อื่น); ชื่อ/รหัสจาก P2 ไม่หลุดมาด้วย | Not run |
| PEND-03 | session H1; สร้าง Party ของ H1 ที่ไม่มี Pending แต่มี Approved/Rejected ได้; GET | 200 พร้อม `{"data":[]}` ไม่ใช่ null/404 | Not run |
| PEND-04 | session H2, A1 และ M1 แยกเคส; GET P1 | ทุกกรณีได้ 403 FORBIDDEN; การเป็น Host ที่อื่น/ผู้สมัคร/สมาชิกไม่ให้สิทธิ์อ่าน P1 | Not run |
| PEND-05 | ไม่มี session; GET P1 และ numeric ID ที่ไม่มีจริงแยกเคส | 401 AUTH_REQUIRED ทั้งสองกรณี ก่อนตรวจ Party | Not run |
| PEND-06 | authenticated H1 แต่ไม่มี identity, identity เป็นของ H2, provider ไม่ใช่ tu, หรือขาด timestamp ยืนยันแต่ละแบบ; GET P1 | 403 FORBIDDEN ทุก variant; ไม่มีรายการหลุดก่อนผ่าน guard | Not run |
| PEND-07 | session H1 ผ่าน guard; GET numeric Party ID ที่ไม่มีจริง | 404 NOT_FOUND ใน JSON error envelope | Not run |
| PEND-08 | session H1; GET P1 พร้อม query user_id/host_id ของ H2, party_id=P2 และ status=Approved | ยังได้เฉพาะ Pending ของ P1; query ไม่เปลี่ยน actor/Party/status | Not run |
| PEND-09 | session H2; GET P1 พร้อม query host_id/user_id ของ H1 | 403 FORBIDDEN ไม่สามารถปลอม Host ผ่าน query | Not run |
| PEND-10 | session H1; GET P1 ที่ Q3 อ้าง N1 ไม่มี profile; ตั้ง email/username เป็น sentinel แยกจาก display name | Q3 มี display_name=`ผู้ใช้`; field keys ตรง allowlist และไม่มี email/username/identity/password/token หรือ user object หลุด | Not run |
| PEND-11 | session H1; ตั้ง Q1/Q2/Q3.created_at ต่างกัน แล้ว GET; จากนั้นตั้ง Q1/Q2 เวลาเท่ากันแล้ว GET อีกครั้ง | เก่าไปใหม่; เวลาเท่ากันเรียงตาม PK เพิ่มขึ้นตาม D04 (baseline ยังไม่รับประกัน tie-break; ต้อง implement ก่อนตรวจรับ) | Not run |
| PEND-12 | session H1; ตั้งเวลาของ Q1 เป็นค่าที่รู้แน่นอนแล้ว GET | created_at เป็น ISO 8601 มี offset; แปลงกลับแล้วตรง instant เดิม และแสดงตาม Asia/Bangkok; การอ่านไม่เลื่อนเวลาใน DB | Not run |
| PEND-13 | session H1; GET สำเร็จแล้วทำให้ session หมดอายุ จากนั้น GET อีกครั้ง; แยกเคส logout ผ่าน endpoint จริงพร้อม CSRF แล้วใช้ cookie เก่า | GET หลังหมดอายุ/หลัง logout ได้ 401 AUTH_REQUIRED; cookie เก่าอ่านไม่ได้ | Not run |
| PEND-14 | session H1; ปิดบัญชีแล้ว GET ผ่าน ModelBackend จริง; แยก direct guard case ที่มี authenticated inactive user | HTTP/session case ได้ 401 AUTH_REQUIRED ตาม backend ปัจจุบัน; direct guard case ได้ 403 ACCOUNT_INACTIVE; บันทึกวิธีทดสอบแยกกัน | Not run |
| PEND-15 | session H1 ผ่าน guard; HEAD/OPTIONS และ POST/PUT/PATCH/DELETE ไป GET route; unsafe methods แนบ CSRF ถูกต้อง; เพิ่ม POST ไม่มี CSRF เป็นเคสย่อย | method ไม่รองรับได้ 405 พร้อม Allow: GET; HEAD ไม่ตรวจ JSON body เพราะ HTTP HEAD ไม่มี body; POST ขาด CSRF ได้ 403 CSRF_FAILED; domain ไม่เปลี่ยน | Not run |
| PEND-16 | session H1; GET แล้วเปลี่ยน Q1 เป็น Rejected พร้อม decision metadata อย่างถูกต้องใน fixture จากนั้น GET ซ้ำ | GET รอบสองไม่มี Q1; success/error responses ของ route ที่ผ่าน decorators มี Cache-Control: no-store; ไม่อ้างว่าทดสอบ decision API สำเร็จจากการแก้ fixture | Not run |
| PEND-17 | session H1; แยก P1 state Open, Full (capacity=2), InProgress, Completed, Cancelled โดยตั้งเวลา/ข้อมูลให้ถูก constraint แล้ว GET | แต่ละ state ได้ 200 และ Pending เดิมตาม D03; ไม่มี PARTY_FULL/PARTY_STARTED/PARTY_CANCELLED จาก GET; ไม่เปลี่ยนสถานะคำขอ | Not run |
| PEND-18 | session H1; ถ่าย snapshot Party.capacity/updated_at, memberships และ JoinRequests; GET P1 ซ้ำสองครั้ง | ไม่มีแถวเพิ่ม/ลบ/แก้, decided_at/by และจำนวน active memberships ไม่เปลี่ยน; ที่ว่างยัง 2; snapshot ใช้ domain tables ไม่รวม session machinery | Not run |

Routing boundary เพิ่มเติม: `party_id=abc` หรือ `-1` ไม่เข้า view และได้ routing 404; ไม่ assert ว่าเป็น JSON error ของ view ส่วน `party_id=0` ที่ผ่าน guard แล้วต้องได้ JSON 404 NOT_FOUND

## 4. รายการตรวจร่วมกับ Frontend

เป็นเคสส่งต่อให้ US10-F ไม่ใช่การประกาศทำ UI เสร็จใน D-01:

| กรณี | Expected | Actual / ผล |
| --- | --- | --- |
| Host เปิด Pending | แสดง loading ระหว่างรอ แล้วใช้ชื่อและรหัสคำขอจาก data array | Not run |
| ไม่มี Pending | แสดง empty state ไม่ใช่ error | Not run |
| Detail บอกว่าไม่ใช่ Host | ไม่แสดงส่วนรายการคำขอ; backend ยังปฏิเสธ direct request ตาม PEND-04 | Not run |
| 401 / 403 / 404 | จัดการ login / ไม่มีสิทธิ์ / ไม่พบกิจกรรมตามสถานะ ไม่แสดงรายการเก่าค้าง | Not run |
| network/5xx หรือเปลี่ยน Party ระหว่างรอ | แสดง error/retry หรือผลของ Party ปัจจุบัน ไม่แสดงข้อมูลเก่าของอีก Party เป็นผลสำเร็จ | Not run |
| ชื่อที่มีอักขระ HTML | แสดงเป็นข้อความ ไม่สร้าง DOM จาก HTML ที่ผู้ใช้กรอก | Not run |

## 5. บันทึกผลเมื่อ implement และทดสอบจริง

ทำรายงานตามโครงนี้ต่อเคส/variant ไม่เปลี่ยน `Not run` เป็น Pass ก่อนมีหลักฐาน:

```text
Case ID / variant:
Contract revision / ข้อสรุป D01–D05:
Commit / branch:
Environment / Django / PostgreSQL:
Fixture aliases และ PK ในฐานทดสอบ (ไม่แนบ credentials):
วิธี: automated integration / direct guard / manual HTTP / browser
Precondition และขั้นตอนที่ใช้จริง:
Expected:
Actual HTTP/status/body และ domain snapshot ก่อน–หลัง:
Result: Not run / Pass / Fail / Blocked
Tester / วันเวลา:
Evidence: command + log หรือ PR/CI/report link
Bug / retest reference:
```

เทสต์เดิมที่พบจาก source มีเพียงการตรวจรายการพื้นฐานรวมกับ approve ใน `JoinRequestDecisionTests` จึงต้องเพิ่มชุดตรวจรายการเฉพาะ Task50 ตามเคสที่ทีมรับ ไม่ถือว่ามี coverage ทั้งชุดอยู่แล้ว
รันชุดที่เปลี่ยนก่อน และบันทึก `make verify`/CI ตามกติกา repository; ตรวจ browser แยกเมื่อเชื่อม UI จริง
งาน Design รอบนี้ตรวจเฉพาะความสอดคล้องของเอกสาร ลิงก์ ตัวอย่าง JSON และ diff ไม่รัน runtime tests, `make verify` หรือ `make smoke` เพราะไม่เปลี่ยนโค้ดระบบ
