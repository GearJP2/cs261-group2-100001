# US4 — แบบทดสอบถอนตัวจาก Party

งาน: `S2-US4-D-01` / [Issue #82](https://github.com/GearJP2/cs261-group2-100001/issues/82)
อ้างอิง [policy](us4-leave-party-policy.md) และ [API / data contract](us4-leave-party-api-contract.md)
คนหลัก: Golf (@Seamui); ผู้ตรวจที่รอ: Austin (@Siestashi)
สถานะทุกเคส: **Not run** — เป็นการออกแบบทดสอบสำหรับส่งต่อ implementation ไม่ใช่ผลทดสอบระบบ

## 1. AC และ fixtures

ใช้ working mapping จาก [sequence checklist](sprint-2-sequences/README.md#us4--ถอนตัว): AC1 ถอนสำเร็จ, AC2 ยกเลิก dialog, AC3 คืนที่ว่างครั้งเดียว, AC4 ถอนเฉพาะตนเอง, AC5 สิทธิ์/สถานะ/เวลา
Issue #82 อ้าง AC1/3/4/5 ส่วน AC2 เก็บไว้ตรวจ flow UI ให้ครบ ผู้ตรวจต้องยืนยันหมายเลขกับ Story Sprint 2 ต้นทาง เพราะ [User Story ใน repo](user-stories.md#us4--ถอนตัวจากปาร์ตี้-leave) มี Scenario 1/2 ไม่ใช่รายการ AC 1–5

ตั้ง Party P: capacity=3, starts_at=T, ends_at=T+1 ชั่วโมง, cancelled_at=null; T เป็น aware datetime เช่น `2030-01-07T10:00:00+07:00`
H เป็น Host, M เป็นสมาชิก active รวม 2 คน จึงเหลือ 1 ที่; L เป็นผู้ถอนแล้ว left_at=L0; N ไม่มี membership; A มี Pending และ R มี Rejected โดยทั้งคู่ไม่มี membership
ทุกคนมี university session ที่ผ่าน guard เว้นแต่เคส auth; reset fixtures ต่อเคส ใช้ POST body `{}` และ CSRF ถูกต้องเป็น baseline

กรณี Full ให้เพิ่มสมาชิก active อีกหนึ่งคน; กรณี Completed ตั้ง now>=ends_at; กรณี Cancelled กำหนด cancelled_at ก่อนทดสอบ
ตรวจ response คู่กับ DB: membership IDs/left_at/joined_at, Party.capacity/cancelled_at, JoinRequest และ active count ก่อน/หลัง ไม่ใช้เพียงข้อความบนหน้าจอเป็นหลักฐาน

## 2. API และข้อมูล

| ID | AC | ขั้นตอน | ผลที่คาดหวัง |
| --- | --- | --- | --- |
| API01 | 1 | M ถอนก่อน T ใน Open | 200; data มี party_id, is_member=false, left_at แบบ ISO 8601 มี offset; active 2→1, slots 1→2; membership แถวเดิมและ joined_at เดิม |
| API02 | 1 | M ถอนก่อน T ใน Full | 200; active ลด 1; remaining_slots=1 และ state=Open หากไม่มี writer อื่น |
| API03 | 3 | POST ซ้ำหลัง API01 | 200 payload เดิม; left_at ไม่เปลี่ยน; ไม่มีการเขียนหรือคืนที่ว่างเพิ่ม |
| API04 | 3,5 | L ส่งซ้ำเมื่อ Party เริ่ม/จบ/ยกเลิก แยกแต่ละกรณี | 200 left_at=L0; ไม่มี mutation แม้สถานะเปลี่ยน |
| API05 | 4 | N, A, R ส่งคำขอ แยกแต่ละคน | 403 NOT_MEMBER; ไม่สร้าง membership/ไม่แก้ JoinRequest |
| API06 | 4 | M ส่ง user_id ของ H/L/ตนเอง, membership_id, host_id, left_at, status หรือเวลาผ่าน body แยกแต่ละ field | 400 INVALID_INPUT; ไม่เปลี่ยนสมาชิกคนใด |
| API07 | 5 | H ส่งคำขอใน Open/Full/InProgress/Completed/Cancelled | 403 HOST_CANNOT_LEAVE ทุกสถานะ; ไม่ถอน Host และไม่ cancel อัตโนมัติ |
| API08 | 5 | M ถอนที่ T−1 microsecond, T, T+1 microsecond แยก fixtures | ก่อน T ได้ 200; ที่ T และหลัง T ได้ 409 PARTY_STARTED โดย left_at ยัง null |
| API09 | 5 | M ถอนที่ ends_at และหลัง ends_at | 409 PARTY_STARTED; ไม่มี mutation |
| API10 | 5 | M ถอนจาก Cancelled ก่อนและหลัง T | 409 PARTY_CANCELLED ทั้งคู่ ตามลำดับ checks |
| API11 | 4,5 | N ถอนจาก Cancelled/Completed | 403 NOT_MEMBER ก่อนตรวจสถานะกิจกรรม |
| API12 | 4 | ไม่มี session/หมดอายุ แต่ CSRF ถูกต้อง | 401 AUTH_REQUIRED; ไม่เปลี่ยน DB |
| API13 | 4 | session ไม่ผ่าน university identity; แยก inactive user | 403 FORBIDDEN; inactive session อาจ 401 จาก ModelBackend; direct authenticated inactive guard ได้ 403 ACCOUNT_INACTIVE |
| API14 | 4 | POST ไม่มี/ผิด CSRF โดยมี session ถูกต้อง | 403 CSRF_FAILED จาก middleware; ไม่มี mutation |
| API15 | 4 | ผ่าน guard/validation ใช้ numeric ID ที่ไม่มีจริง; แยก anonymous | 404 NOT_FOUND; anonymous ที่ CSRF ถูกต้องได้ 401 ก่อนตรวจ Party |
| API16 | 4 | GET/HEAD/OPTIONS/PUT/PATCH/DELETE โดยผ่าน guard และ CSRF เมื่อจำเป็น | 405 METHOD_NOT_ALLOWED และ Allow: POST |
| API17 | 4 | body ว่างและ {} แยก fixtures | ทั้งคู่ผ่าน validation และถอนตามกฎปกติ |
| API18 | 4 | malformed JSON, [], null, boolean, unknown field, body ไม่ว่างที่ไม่ใช่ application/json | 400 INVALID_INPUT ทุกกรณี ไม่มี mutation |
| API19 | 1,4 | ตรวจ success และ handled error responses | Content-Type application/json, Cache-Control มี no-store; envelope ตรง contract; ไม่ส่ง User/identity/email/student ID หรือข้อมูลผู้อื่น |
| API20 | 5 | ทดสอบ now เท่ากับ T โดยแทน instant ด้วย +07:00 และ Z | ทั้งคู่ 409 PARTY_STARTED ไม่ขึ้นกับ timezone browser |

ทุกเคส API01–API20 เป็นระดับ HTTP/DB เว้นกรณี direct guard ใน API13 ใช้ guard unit test
หลังเคสถอนสำเร็จต้องตรวจ capacity/JoinRequest/จำนวนแถว membership ไม่เปลี่ยน และ Host ยังคง active
HTTP tests ต้องเปิด CSRF checks จริง; routing ID ที่ไม่ตรง integer route เป็น Django 404 และไม่รับรอง JSON ตาม contract

## 3. Transaction และ integration

ใช้ PostgreSQL และ connection แยกจริงสำหรับเคสแข่งกัน ควบคุมลำดับได้ lock ด้วย synchronization และมี timeout ไม่ใช้การยิงต่อกันหรือ SQLite อ้างว่าเป็น concurrency test

| ID | AC | ขั้นตอน | ผลที่คาดหวัง |
| --- | --- | --- | --- |
| DB01 | 1,3 | บังคับ write ล้มเหลวก่อน commit | rollback ทั้งหมด; left_at/count คงเดิม; ไม่ส่ง success |
| DB02 | 3 | สอง connection ถอน M พร้อมกัน | ทั้งสองได้ 200 left_at เดียวกัน; active ลดครั้งเดียว; ไม่เพิ่มแถว |
| DB03 | 3 | P Full แข่ง M ถอนกับ H approve A โดยทดสอบทั้งลำดับได้ lock | approve ก่อน leave ถูกปฏิเสธตามกฎ Full เดิม; leave ก่อน approve อนุมัติได้เมื่อผ่านกฎเดิม; active<=capacity เสมอ |
| DB04 | 3,5 | แข่ง leave กับ cancel ก่อน T ทดสอบทั้งลำดับ | cancel ก่อน: leave 409 PARTY_CANCELLED; leave ก่อน: leave สำเร็จและการ cancel ไม่ย้อนผลถอน |
| DB05 | 3 | แข่ง leave กับ capacity edit ทดสอบทั้งลำดับ | edit ใช้ active count หลังได้ lock; ไม่ยอมให้ capacity ต่ำกว่า active และไม่เกิด lost update |
| DB06 | 5 | เริ่ม request ก่อน T แต่ถือ Party lock อีก connection จนถึง T แล้วปล่อย | leave ตรวจเวลาหลังได้ lock แล้วได้ 409 PARTY_STARTED |
| DB07 | 1,3 | ถอน → ขอใหม่ US3 → approve US10 → ถอนรอบใหม่ก่อน T | ก่อน approve ยังไม่ active; reuse request/membership ตาม schema; รอบใหม่ถอนใหม่ได้โดยตรวจเวลา/สิทธิ์อีกครั้ง |
| DB08 | 3 | หลัง leave มี approve อีกคนก่อน refresh detail | detail แสดง count/slots จริง ไม่จำเป็นต้องเหลือที่ว่างเพิ่มจากค่าก่อนถอน |

## 4. UI ที่ต้องตรวจเทียบกับแบบของผู้ใช้

| ID | AC | ขั้นตอน | ผลที่คาดหวัง |
| --- | --- | --- | --- |
| UI01 | 2 | เปิด dialog แล้วกดยกเลิก | ไม่ส่ง API และไม่เปลี่ยนสถานะสมาชิก |
| UI02 | 1,3 | ยืนยันถอนขณะ response ช้า | ป้องกันกดส่งซ้ำระหว่างรอ; ไม่แสดงผลสำเร็จก่อนทราบผล |
| UI03 | 1,4 | ถอนสำเร็จแล้วโหลด detail/members | detail แสดง is_member=false/count จริง; members ได้ 403 ตามสิทธิ์เดิม ต้องล้างรายชื่อและไม่แสดงว่า leave ล้มเหลว |
| UI04 | 1 | leave ได้ 200 แต่ refresh detail ล้มเหลว | แจ้งถอนสำเร็จแล้วแต่โหลดข้อมูลไม่ได้; retry เฉพาะโหลดข้อมูล |
| UI05 | 3 | network ขาดก่อนทราบผล leave | แจ้งยังไม่ทราบผล; ตรวจสถานะ/retry ได้เฉพาะรอบสมาชิกเดิม ไม่แสดง success จาก network error |
| UI06 | 4,5 | API ตอบ 401/403/404/409 แยกแต่ละกรณี | 401 ไป login flow; 403/404 แจ้งเหตุผล; 409 refresh สถานะ; ไม่คงข้อมูลเก่าว่าเป็นข้อมูลล่าสุด |
| UI07 | 5 | เปิดแบบสมาชิก/Host/ไม่เป็นสมาชิก/เริ่มแล้ว/จบแล้ว/ยกเลิกแล้ว | ปุ่มและเหตุผลตรง policy; Host ใช้เส้นทาง cancel ไม่ใช่ leave; Backend ต้องตรวจซ้ำเสมอ |

ยังไม่พบไฟล์หรือลิงก์แบบ UI ของผู้ใช้ในเอกสารชุดนี้ จึงเป็นเกณฑ์สำหรับตรวจเทียบ ไม่อ้างว่าตรวจ UI จริงผ่านแล้ว

## 5. ตรวจความสอดคล้องและส่งต่อ review

| ประเด็น | ผลตรวจเอกสาร |
| --- | --- |
| Host/ถอนเฉพาะตนเอง | policy ข้อ 1/5 ตรง contract ข้อ 2/4; API05–API07 |
| สถานะ/เวลา | policy ข้อ 2/5 ตรง contract ข้อ 4/5; API08–API11, API20, DB06 |
| กดซ้ำ/กลับเข้าร่วมใหม่ | policy ข้อ 3/4 ตรง contract ข้อ 3/5; API03–API04, DB02, DB07 |
| คืนที่ว่าง/ข้อมูลเดิม | policy ข้อ 3 ตรง contract ข้อ 5/6; API01–API02, DB01–DB05, DB08 |
| สิทธิ์อ่านรายชื่อหลังถอน | contract ข้อ 6; UI03 ต้องรองรับ 403 ไม่ใช่คาดว่าจะอ่านสมาชิกต่อได้ |
| UI ของผู้ใช้ | รอแนบไฟล์/ลิงก์และตรวจเทียบ UI01–UI07 |
| AC numbering / S2-PLAN-01 | รอหลักฐานจาก Story ต้นทางและ planning ก่อนยืนยัน |

- [ ] Austin review policy/API และ expected results พร้อมบันทึกชื่อ วันที่ และลิงก์หลักฐาน
- [ ] แนบแบบ UI และตรวจเทียบกับ contract โดยเฉพาะสิทธิ์หลังถอน
- [ ] ยืนยัน AC 1/3/4/5 และ dependency S2-PLAN-01
- [ ] ส่งต่อ API/DB cases ให้ implementation #85 และ API tests #89; UI cases ให้ผู้รับผิดชอบ Frontend

ผลตรวจในรอบนี้เป็นการตรวจเอกสารเท่านั้น ทุกเคส API/DB/UI ยัง Not run เมื่อรันจริงให้บันทึก case ID, environment, ขั้นตอน/คำสั่ง, expected/actual, Pass/Fail และลิงก์หลักฐาน โดยไม่ติ๊ก review แทนผู้ตรวจ
