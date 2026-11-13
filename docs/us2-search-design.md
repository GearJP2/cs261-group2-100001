# US2 — Search semantics และ API contract

งาน `S2-US2-D-01` / [Issue #91](https://github.com/GearJP2/cs261-group2-100001/issues/91)
คนหลัก Golf (@Seamui); ผู้ตรวจที่รอ Austin (@Siestashi)
สถานะ: ข้อเสนอสำหรับ review ยังไม่ใช่มติทีม และยังไม่ได้ implement
Dependency: รอยืนยัน S2-PLAN-01 ก่อนส่งต่อ #94; test cases ส่งต่อ #98

## 1. ฐานเดิมและช่องว่าง

- [US2](user-stories.md#us2--ค้นหาและกรองกิจกรรม-search) ระบุค้นหาตามกีฬา วันเวลา และสถานที่ แต่ยังไม่กำหนด time predicate/pagination
- [Sequence](sprint-2-sequences/README.md#us2--ค้นหา) กำหนด AND filters และให้ยืนยันขอบเวลา/สถานะในงานนี้
- `backend/parties/views.py:create_party_api` รองรับ GET และ POST ที่ `/api/v1/parties` อยู่แล้ว GET ปัจจุบันไม่อ่าน filters, แสดงเฉพาะอนาคต ไม่ยกเลิก ไม่เต็ม เรียง starts_at และตัด 50 รายการ
- `party_data` และ `services.get_party_state` มี field/state เดิมให้ reuse ไม่สร้างนิยามสถานะอีกชุด
- `backend/venues/models.py:Venue` ยังไม่มี Indoor/Outdoor; `venue_catalog.py` มี venue_kind เป็น REAL/MOCK ซึ่งเป็นแหล่งที่มาข้อมูล ไม่ใช่ประเภทในร่ม/กลางแจ้ง
- `frontend/static/js/app.js:initHome` อ่าน `data` เป็น array; metadata ที่เสนอเพิ่มยังคง array เดิม แต่ UI ต้องเปลี่ยนให้รองรับ pagination และ controls

## 2. มติที่เสนอ

| ID | ข้อเสนอ | ความหมาย |
| --- | --- | --- |
| D01 | ทุกตัวกรองรวม AND | sport_id ตรง Party.sport_id, venue_id ตรง Party.venue_id, venue_type ตรงประเภทสนามจริง ไม่ใช้ชื่อกีฬาแทนประเภทสนาม |
| D02 | ช่วงเวลาใช้ starts-within แบบ `[from,to)` | `starts_at >= starts_from` และ `starts_at < starts_before`; ไม่ใช้ overlap ไม่กรอง ends_at |
| D03 | วันที่/เวลา UI อ้าง Asia/Bangkok | เลือกวันที่ D คือ [D 00:00+07:00, D+1 00:00+07:00) ไม่ใช้ 23:59:59 และไม่ยึด timezone เครื่องผู้ใช้ |
| D04 | default state=Open ตาม GET เดิม | เลือกดู Full/InProgress/Completed/Cancelled หรือ all ได้โดย explicit filter; การเห็นรายการไม่ใช่สิทธิ์ขอเข้าร่วม |
| D05 | ใช้ state/count แบบ Detail | Cancelled → Completed → InProgress → Full → Open ตามลำดับเดิม ใช้ now เดียวตลอด request; ณ starts_at เป็น InProgress และ ณ ends_at เป็น Completed |
| D06 | pagination และลำดับคงที่ | page=1, page_size=20 (สูงสุด 100), order starts_at ASC แล้ว id ASC; กรองก่อนนับ/แบ่งหน้า |
| D07 | venue_type เป็น Indoor/Outdoor แบบ optional | เสนอเพิ่ม Venue.venue_type แบบ nullable พร้อม migration เมื่อ implement; null หมายถึงยังไม่จัดประเภท ไม่เดาค่าจากชื่อ/กีฬา |
| D08 | ข้อความค้นหา q | ค้นหาแบบ case-insensitive substring ใน Party.title เท่านั้น หลัง trim; ไม่ค้นชื่อกีฬา/ชื่อสนาม/description โดยอัตโนมัติ |

D07 และ D08 เป็นข้อเสนอเพิ่มรายละเอียดที่ต้องยืนยันกับทีม ไม่อ้างว่ามีข้อมูลหรือ contract นี้อยู่แล้ว หากทีมไม่รับให้แก้ contract/UI/test cases ก่อน implement
สนามเดียวรองรับหลายกีฬาได้ sport กับ venue จึงเป็นคนละ filter การเลือกสนามที่ไม่รองรับกีฬาที่เลือกให้ผลว่าง ไม่ขยายเป็น OR หรือเปลี่ยนกีฬาที่ส่งมาเอง

## 3. GET query contract ที่เสนอ

`GET /api/v1/parties` ใช้ university session guard และ never_cache เดิม ไม่มี request body; GET ไม่ต้องแนบ CSRF แต่ POST สร้าง Party เดิมยังคง CSRF/validation ของตนเอง

| Parameter | รูปแบบ / default | Validation และ predicate |
| --- | --- | --- |
| q | string, default ไม่กรอง | trim; สูงสุด 100 ตัวอักษรหลัง trim; ว่างเท่ากับไม่กรอง; title icontains |
| sport_id | positive decimal integer, optional | exact Party.sport_id |
| venue_id | positive decimal integer, optional | exact Party.venue_id |
| venue_type | Indoor หรือ Outdoor, optional | case-sensitive enum; exact Venue.venue_type |
| starts_from | ISO 8601 datetime, optional | ต้องมี T และ offset หรือ Z; ขอบล่างรวม |
| starts_before | ISO 8601 datetime, optional | ต้องมี T และ offset หรือ Z; ขอบบนไม่รวม |
| state | Open (default), Full, InProgress, Completed, Cancelled, all | เลือกค่าเดียว; all ไม่กรองสถานะ แต่ยังใช้ filters อื่น |
| page | positive decimal integer, default 1 | ไม่รับ 0/ลบ/ทศนิยม |
| page_size | positive decimal integer 1–100, default 20 | มากกว่า 100 คืน validation error ไม่ clamp เงียบ ๆ |

ไม่รับ repeated query keys หรือ unknown parameters; empty value ของทุก field ยกเว้น q เป็น invalid ให้ client ละ parameter ที่ไม่เลือกแทนส่งค่าว่าง
IDs ที่รูปแบบถูกแต่ไม่มีจริงคืน 200 รายการว่าง ไม่ใช่ 404; ไม่กรอง Venue.is_active เพิ่มโดยปริยายเพราะ Detail ยังอ่าน Party เดิมได้
ถ้ามีขอบเวลาทั้งคู่ต้อง `starts_from < starts_before`; ขอบเดียวใช้ได้ วัน/เวลาไม่มี offset หรือ date-only ใน API ไม่รับ แต่ UI แปลงวันเป็นช่วงก่อนส่ง
q ว่างเป็น no-op; AND ระหว่าง q และ filters อื่นเสมอ ไม่รองรับ multi-value, sort อื่น หรือหลายช่วงเวลาในรอบนี้

ตัวอย่างเลือกกีฬา 1 เฉพาะสนาม 2 ในร่ม และวันที่ 20 พฤศจิกายน 2030 (URL encode เครื่องหมาย + เป็น %2B):

```text
GET /api/v1/parties?sport_id=1&venue_id=2&venue_type=Indoor&starts_from=2030-11-20T00:00:00%2B07:00&starts_before=2030-11-21T00:00:00%2B07:00&state=Open&page=1&page_size=20
```

## 4. Response และข้อผิดพลาด

HTTP 200, application/json, Cache-Control มี no-store ใช้ Party data allowlist เดียวกับ Detail ไม่ expose email, student ID, identity หรือ User object

```json
{
  "data": [
    {
      "id": 12,
      "title": "เล่นแบดมินตัน",
      "description": "หาเพื่อนเล่นกีฬา",
      "host": {"id": 7, "display_name": "ผู้จัดกิจกรรม"},
      "sport_id": 1,
      "venue_id": 2,
      "starts_at": "2030-11-20T18:00:00+07:00",
      "ends_at": "2030-11-20T19:00:00+07:00",
      "capacity": 4,
      "member_count": 2,
      "remaining_slots": 2,
      "state": "Open",
      "is_host": false,
      "is_member": false
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

host.display_name ไม่มี profile ใช้ fallback เดียวกับ Detail ไม่ใช้ username/email แทน total คือจำนวนที่ผ่าน filters ทั้งหมดก่อนแบ่งหน้า; หน้าที่เกินจำนวนหน้าได้ 200 data=[] โดยยังคง total จริง กรณีไม่พบเลย:

```json
{"data": [], "page": 1, "page_size": 20, "total": 0}
```

```json
{"error": {"code": "INVALID_INPUT", "message": "ตัวกรองค้นหาไม่ถูกต้อง", "fields": {"starts_before": "ต้องอยู่หลัง starts_from"}}}
```

| HTTP | code | เงื่อนไข |
| --- | --- | --- |
| 400 | INVALID_INPUT | query ไม่ตรง contract; fields เป็น map ชื่อ parameter → ข้อความ; unknown/repeated key ระบุ key นั้น |
| 401 | AUTH_REQUIRED | ไม่มี session/หมดอายุ |
| 403 | ACCOUNT_INACTIVE / FORBIDDEN | ตาม university guard เดิม; inactive session อาจถูก ModelBackend resolve เป็น anonymous แล้วได้ 401 |
| 405 | METHOD_NOT_ALLOWED | method อื่นนอกจาก GET/POST ตาม route เดิม; Allow: GET, POST |

ลำดับ guard → dispatch method → validate query สำหรับ GET → query/count/paginate/serialize; invalid query ไม่ตอบรายการว่างแทน error
POST ใช้ contract สร้างเดิม ไม่ผ่าน query validation ของ GET; unsafe method อาจถูก CSRF middleware ปฏิเสธก่อน view
404 ของ path ไม่ใช่ list-result contract; network/unhandled 5xx ไม่รับประกัน JSON และไม่ใช่ empty success

## 5. Data และสถานะ

- นับเฉพาะ memberships.left_at IS NULL รวม Host ไม่รวม Pending/Rejected/ผู้ถอน; ระวัง join กีฬา/สนามทำให้ count ซ้ำ ใช้ annotation/query ที่ไม่คูณแถว
- reuse get_party_state โดยส่ง now เดียวที่ capture ก่อน query และ member_count จาก active count ให้ filtering กับ serialization ใช้ predicate เดียวกัน
- default Open ต้องยังไม่ยกเลิก, now < starts_at, active_count < capacity; Full เหมือนกันแต่ active_count >= capacity
- ไม่ทำงานเขียน ไม่ล็อก/จองสมาชิกหรือสนาม การส่งคำขอ US3 และอนุมัติ US10 ต้องตรวจ state/capacity ใหม่ทุกครั้ง
- pagination เรียง starts_at,id ป้องกัน tie ในข้อมูลคงที่ แต่ไม่ใช่ snapshot ข้าม requests เมื่อมีการแก้ไข/ถอน/อนุมัติ ผลและ total อาจเปลี่ยน ต้อง refresh ได้
- D07 ต้องเพิ่ม field/migration และจัดประเภท fixture/catalog โดยผู้ดูแลข้อมูลยืนยัน ค่าเก่า null อยู่ในผลเมื่อไม่กรอง venue_type แต่ไม่ตรง Indoor/Outdoor; ไม่เติมค่าจากการคาดเดา UI ต้องดึงประเภทจากข้อมูลที่ยืนยันแล้ว เช่นเพิ่ม venue_type ใน venues API ซึ่งต้องประสานเจ้าของ US9 ก่อน implement

## 6. UI handoff และ review

ข้อเสนอนี้เป็น behavior สำหรับเชื่อม UI เดิม ไม่ใช่ภาพ UI ที่ review แล้ว:
เลือก sport, venue, Indoor/Outdoor แยก controls พร้อมข้อความค้นหา วัน/ช่วงเวลา และสถานะ; ชี้ชัดว่าช่วงเวลากรองเวลาเริ่มกิจกรรม ทุก control รวม AND
เมื่อเปลี่ยน sport ให้โหลดสนามที่รองรับและล้าง venue ที่ไม่ใช้แล้ว เมื่อเปลี่ยน filter/reset ให้กลับ page=1; reset คืน q/filters ว่าง, state=Open, page_size=20
แสดง loading, results พร้อม pagination, empty พร้อมล้างตัวกรอง, validation error และ retry สำหรับ network/5xx ไม่ใช้ข้อความ error เป็น empty state
ใช้ request version หรือ AbortController ป้องกัน response เก่าและ error เก่าทับคำค้นใหม่ การ clear/reset ต้อง invalidate request ที่ค้างด้วย
Full/Started/Cancelled ที่เลือกดูได้ต้องมี badge ตรง Detail และไม่เปิดปุ่ม join จากผลค้นหา; เข้า Detail แล้วอ่านสิทธิ์/state ปัจจุบันอีกครั้ง

- [ ] Austin review D01–D08 โดยเฉพาะ starts-within, default Open, pagination, q และ field ประเภทสนาม
- [ ] ยืนยัน S2-PLAN-01 และ AC 1/2/3/5 จาก Story ต้นทาง; [Story ใน repo](user-stories.md) มีเพียง Scenario 1/2 จึงยังไม่อ้างว่าเลข AC ยืนยันแล้ว
- [ ] แนบ UI ที่ใช้จริงและตกลง query names กับ Frontend ก่อน implement #94
- [ ] เจ้าของข้อมูลยืนยัน migration/การจัดประเภทสนามและผลกระทบ venues API
- [ ] บันทึกชื่อ/วันที่/ลิงก์ review และส่ง [test cases](us2-search-test-cases.md) ต่อ #98

validation รอบนี้เป็นตรวจเอกสารเทียบ source เท่านั้น ยังไม่รัน API/browser/DB tests หรือ CI และยังไม่ปิด Issue #91 แทน review ของทีม
