# US2 Backend — Task79 API และผลตรวจรับ

งาน `S2-US2-B-01` / [Issue #94](https://github.com/GearJP2/cs261-group2-100001/issues/94)
ตรวจ local วันที่ 15 พฤศจิกายน 2026; คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
Design และ test plan อยู่ใน [PR #157](https://github.com/GearJP2/cs261-group2-100001/pull/157); flow ประกอบอยู่ใน [us2.mmd](sprint-2-sequences/us2.mmd)

## พฤติกรรม API ที่เปิดใช้

ต่อยอด `GET /api/v1/parties` เดิมให้ validate/filter/paginate; POST สร้าง Party ใช้ guard/CSRF และ validation เดิม
GET ใช้ university session guard เดิม ไม่ต้องส่ง CSRF คืน no-store; query invalid ได้ 400 INVALID_INPUT พร้อม error.fields หลังผ่าน guard

| Query | กฎ |
| --- | --- |
| q | trim แล้ว title icontains; ไม่ค้น description/ชื่อสนาม/กีฬา; สูงสุด 100 ตัวอักษร; ว่างไม่กรอง; ไม่รับ NUL |
| sport_id / venue_id | จำนวนเต็มบวก; IDs ไม่มีจริงได้รายการว่าง |
| venue_type | Indoor / Outdoor ตาม Venue.venue_type; แยกจากกีฬา |
| starts_from / starts_to | ISO 8601 มี T และ timezone offset/Z; ช่วง `[starts_from, starts_to)` กรอง starts_at ไม่ใช่ overlap; ขอบเดียวใช้ได้ |
| state | default Open; เลือก Full/InProgress/Completed/Cancelled/all ได้ |
| page / page_size | default 1/20; page บวก, page_size 1–100; หน้าเกินได้ array ว่าง |

ทุก filter รวม AND; ไม่รับ unknown/repeated keys และค่าว่างนอกจาก q; ถ้าส่งขอบเวลาทั้งคู่ starts_from ต้องน้อยกว่า starts_to
วันที่ UI ต้องแปลงเป็นช่วงวัน Asia/Bangkok แล้วส่ง offset; API ไม่รับ date-only หรือ datetime ไม่มี timezone

Response เป็น `data` array รูปแบบ Party Detail เดิม พร้อม metadata `page`, `page_size`, `total` ซึ่งนับหลังกรองแต่ก่อนแบ่งหน้า
เรียง starts_at ASC แล้ว id ASC; huge page ที่เกิน total ไม่ส่ง OFFSET ที่เกินช่วง PostgreSQL แต่คืน array ว่างและ total จริง
ใช้เวลา now เดียวสำหรับ state filtering และ serialization; precedence Cancelled → Completed → InProgress → Full → Open; active count รวม Host และไม่รวมสมาชิกถอน/คำขอ Pending/Rejected
ผลข้าม requests ไม่ใช่ snapshot; search ไม่จองที่และไม่แก้ข้อมูล join/approve ยังต้องตรวจ state/capacity ใหม่

## Migration และข้อมูลสนาม

เพิ่ม `venues/0002_venue_venue_type.py` และ `Venue.Type` ตาม [schema contract หัวข้อ 2.3](base-02-schema-contract.md#23-รอบถัดไป--us2-ค้นหา-และวันปิดสนาม) ซึ่งยืนยัน Indoor/Outdoor nullable ไว้แล้ว
ใช้ `make migrate` เพื่อใช้ migration เมื่ออัปเดต environment (startup development ทำ migrate ตาม workflow เดิมด้วย)
ข้อมูลสนามเก่าเป็น null ไม่เปลี่ยนเป็น Indoor/Outdoor อัตโนมัติ; ต้องให้ผู้ดูแลยืนยันและจัดประเภทก่อนคาดหวังว่าตัวกรองประเภทสนามจะพบสนามเหล่านั้น
null ยังแสดงได้เมื่อไม่กรองประเภท; สนาม inactive ไม่ถูกซ่อนเพิ่มจากกฎ Detail เดิม
ไม่มี environment variable ใหม่ และไม่เปลี่ยน venues API ให้ส่ง venue_type ในงานนี้

## ผลตรวจ automated tests

| การตรวจ | ผล |
| --- | --- |
| `make verify` | ผ่าน Django check, migration check, lint/format และ 601 tests (skip 1) |
| `make smoke` | ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS |
| `git diff --check` | ผ่าน |

เคสที่ skip คือ UT-US14-API-06 เพราะ policy ยังไม่ยืนยันใน #100/#105 ไม่ใช่ search test

Tests ใหม่มี 21 methods แบ่งเป็น:

- `backend/parties/test_search_query.py` — 7 tests ตรวจ default/normalize, integer/enum, unknown/repeated keys, text limit, timezone และช่วงเวลาผิด
- `backend/parties/test_search_filters.py` — 7 tests ตรวจ AND, venue type/null/inactive, ขอบช่วงเวลา, state เทียบ get_party_state, active count, text scope และไม่แก้ข้อมูล
- `backend/parties/test_search_api.py` — 7 tests ใช้ Django Client เปิด enforce_csrf_checks=True ตรวจ session guard, HTTP validation/response allowlist, combined filters, pagination/order/total, huge page/IDs และ now เดียว

แก้ assertion ของ list test ใน `test_creation_api.py` ให้ตรวจ metadata ใหม่พร้อม data เดิม ไม่เปลี่ยน contract POST
Session ใน tests เป็น local verified fixture ไม่ใช่ผลยืนยัน TU provider จริง; integration ใช้ PostgreSQL ตาม Docker environment ของทีม

## ข้อจำกัดและ review

- งานนี้ไม่เพิ่ม controls/pagination บนหน้าเว็บ หน้า home เดิมที่อ่านเฉพาะ data จะแสดงหน้าแรกตาม default 20 รายการ; ส่งต่อ Frontend ให้ใช้ metadata และ query contract
- Runtime smoke ตรวจ HTTP/readiness/template/CSS ทั่วไป ไม่ใช่ manual search API หรือ browser UAT ของทุก filter
- Manual API testing และหลักฐานเคสตรวจรับเป็นงาน #98; tests ที่รันไม่ใช่การติ๊กแบบ Design ทุกเคสว่าผ่าน โดยเฉพาะ UI
- เลข AC1/2/3/5 เป็น working mapping ของเอกสาร Design ที่ต้องยืนยันกับ Story ต้นทาง ไม่ใช่มติใหม่จากผล automated tests
- [ ] Austin review semantics/implementation เทียบข้อสรุป #91 และผล tests
- [ ] แนบหลักฐาน S2-PLAN-01 และมติ review #157 ก่อนปิด #94
- [ ] แนบผล GitHub CI และส่งต่อ #98/Frontend

local verification ไม่แทน peer review หรือผล GitHub CI

## Retest หลังรวม main — 16 พฤศจิกายน 2026

รวม `origin/main` ที่ `69c53f5` เข้า branch Search API และแก้ conflict โดยใช้ parser/queryset ใน `search.py` ชุดเดียว พร้อมเก็บ tests ล่าสุดจาก main รวมทั้ง Task78 query audit
ใช้ model และ migration `venues/0002_venue_venue_type.py` ของ main; ลบ `0002_venue_type.py` ของ branch ที่เพิ่ม field เดียวกันซ้ำ จึงเหลือ migration graph สายเดียว ไม่เพิ่มคอลัมน์สองครั้ง

- `make verify` ผ่าน 659 tests (skip 1 เคส US14 ที่รอ policy #100/#105); Django/migration/lint/format checks ผ่าน
- `make smoke` ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS
- ไม่มีการเปลี่ยน historical evidence files ของทีมเพื่อให้ตรง implementation ใหม่

กรณี local เคยใช้ `0002_venue_type` ของ branch ไปแล้ว: ต้องตรวจประวัติ migration และคอลัมน์จริงก่อน หากเป็น `venue_type` แบบ varchar(7), nullable ตรง migration ใหม่ จึงใช้ `python backend/manage.py migrate venues 0002_venue_venue_type --fake` ใน container เพื่อบันทึกชื่อ migration ของ main โดยไม่เพิ่มคอลัมน์ซ้ำ
ขั้นตอนนี้ใช้กับ local ที่ตรวจแล้วเท่านั้น ไม่ใช้ --fake กับฐานใหม่หรือ schema ที่ไม่ตรง; ฐานใหม่รัน migrate ปกติ Local รอบนี้ตรวจและปรับประวัติแล้ว ไม่มีการลบข้อมูลสนาม
