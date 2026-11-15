# Task78 — ตรวจ query/filter และ index ของ Party/Venue/Sport

งาน [Issue #93](https://github.com/GearJP2/cs261-group2-100001/issues/93),
[Trello Task78](https://trello.com/c/6tBBaNAh), `S2-US2-DB-01`.
ผู้รับผิดชอบ Gold; ผลรันโดย agent บนเครื่อง Gold วันที่ **15 พ.ย. 2026**.
Source ที่รัน `14d13e5` (ต่อจาก main `9fe4149`); commit เอกสาร/evidence ตามหลัง source นี้.
**ส่งตรวจ Task78 ยังไม่ใช่ผู้รีวิวอนุมัติ และไม่ใช่ผล Manual UI/UAT หรือปิด Task84.**

## สิ่งที่พบและสิ่งส่งมอบ

main มี search API จาก Task79 และ nullable `Venue.venue_type` จาก migration
`venues.0002_venue_venue_type` แล้ว แม้เอกสาร Design เก่ายังเขียนว่าเป็นข้อเสนอ/ยังไม่มี field.
งานนี้ตรวจ implementation จริงเทียบ [Design D01–D08](us2-search-design.md),
[planning PLAN-US2-01/02/03/04](sprint-2-planning-contract.md), และกรณี S02–S12/S15–S16.
ใช้ mapping กลุ่ม AC ตามเอกสารแผน ไม่รับรองเลข AC หรือมติทีมแทนผู้ตรวจ.

- API ใช้ `Party.sport_id`, `Party.venue_id`, `Venue.venue_type` เป็น AND;
  `VenueSport` บอกว่าสนามรองรับหลายกีฬา แต่ไม่ join ตารางนี้มาคูณผล Party/count.
- ช่วงเวลาใช้ **starts-within `[from,to)`** ไม่ใช่ overlap; `+07:00` กับ UTC instant เดียวกันได้ผลเท่ากัน.
- state ใช้ Cancelled → Completed → InProgress → Full → Open;
  active count นับ Membership ที่ `left_at IS NULL` ไม่เอา Pending/Rejected หรือแถวที่ออกแล้วมานับ.
- กรองก่อน total/page และเรียง `starts_at,id`; field `venue_type` อนุญาต NULL
  โดยไม่ตีความ REAL/MOCK หรือเดาประเภทจากชื่อสนาม. ประเภทใน fixtures เป็นข้อมูลจำลอง.
- ผลเทียบ SQL ตรงกับ API จึงไม่มีการเปลี่ยน runtime API หรือ schema ใน PR นี้.
  ส่งมอบ SQL oracle, catalog audit, regression tests และ raw evidence ให้ตรวจย้อนหลังได้.

## ออกแบบการตรวจ / ข้อมูลตั้งต้น

ใช้ Django test runner สร้างฐาน **`test_task78_audit`** บน PostgreSQL แยก Compose project
`task78-audit`; เมื่อจบ runner ลบ test DB อัตโนมัติ ไม่ใช้ข้อมูลหรือ session จริง.
ใช้ `force_university_login` สร้าง identity/session สังเคราะห์ใน test DB และควบคุม clock;
ไม่เรียก TU API และไม่ทดสอบการ login ในงานนี้.

- now คงที่ N = `2030-11-19T12:00:00+07:00`
- A = `2030-11-20T00:00:00+07:00`, B = `2030-11-21T00:00:00+07:00`
- 2 กีฬา; 3 สนาม (Indoor, Outdoor, NULL); ทุกสนามรองรับทั้ง 2 กีฬา.
- 11 Party: A, B−1µs, B, A−1µs/overlap, Outdoor, NULL type, กีฬาอื่น,
  Full, เริ่มที่ N, จบที่ N, Cancelled ที่จบแล้ว.
- ต่อ Party มี Host+Member active 2 แถว, left 1 แถว, Pending 1 และ Rejected 1.
  capacity=3 ยกเว้น Full/Cancelled=2. Host ไม่มี profile เพื่อไม่บังคับ inner join ตัด Party ทิ้ง.
- performance fixture เพิ่ม Party กีฬาอื่น/ช่วงเวลาอื่น 10,000 แถว รวม **10,011**;
  fixture ใน test transaction ไม่ใช่ seed เพิ่มในฐานใช้งาน.

วิธี oracle: ส่ง GET ผ่าน **Django test Client (in-process)** เข้าสู่ middleware/view/query จริง;
เทียบ `(id,state,member_count)`, ลำดับ, total และ page metadata กับ
[`us2_search_oracle.sql`](../database/seeds/us2_search_oracle.sql).
SQL นี้ใช้ correlated count + CASE แยกจาก ORM/`get_party_state` ของ API;
ไม่ดึง expected จาก response เอง. เงื่อนไข q ใช้ `strpos(upper(...))` เพื่อรวมกรณี `%` เป็นอักษรจริง.

## Expected–Actual และหลักฐานรายจุด

| Case / วิธีตรวจ | Expected | Actual | ผล / raw evidence |
|---|---|---|---|
| Q78-01: ส่ง 9 query variants แยก sport/venue/type และรวม AND/q/unknown ID | ผลตรงทุกเงื่อนไข; Indoor+Outdoor ขัดกันว่าง; q trim/case-insensitive; `%` ไม่ใช่ wildcard; ไม่คูณ active count | API IDs/state/count ตรง SQL ทั้ง 9 variants; Membership จริง 3 แต่ active 2; requests ยัง 2 | PASS [JSON](evidence/task78/Q78-01.json) |
| Q78-02: ส่งช่วง A/B แบบ Bangkok และ UTC | รวม A/B−1µs; ไม่รวม B/A−1µs แม้ overlap; UTC ได้รายการเดียวกัน | ทั้ง 2 query ได้ lower/upper_inside ตามลำดับเหมือนกัน | PASS [JSON](evidence/task78/Q78-02.json) |
| Q78-03: ส่ง Open/Full/InProgress/Completed/Cancelled/all และอ่าน Detail ที่ clock เดียวกัน | state/count ตรง SQL และ Detail; ณเริ่มเป็น InProgress/ณจบเป็น Completed; Cancelled ชนะเวลา | ตรงทั้ง 6 states รวมกรณี Full ที่มี left/request history | PASS [JSON](evidence/task78/Q78-03.json) |
| Q78-04: Indoor/all/page_size=2, page 1/2/3/99 | filter ก่อนแบ่ง; starts_at เท่ากันเรียง id; total คงเดิม; page99 ว่าง | ทุกหน้าและ total ตรง SQL; หน้า99 data=[] | PASS [JSON](evidence/task78/Q78-04.json) |
| Q78-05: รัน catalog SQL + introspection ของ PostgreSQL จริง | มี venue_type nullable varchar(7), sport/venue FK และ indexes เดิม | พบ column/FKs และ index sport+starts_at / venue_id; มีรายการ index definitions แนบ | PASS [JSON](evidence/task78/Q78-05.json) |
| Q78-06: 10,011 Party; จับ SQL/params ที่ API รันจริงแล้ว EXPLAIN ANALYZE ทั้ง count/data | ผลยังตรง SQL; count SELECT คืน 1 row, data SELECT คืน 2 Party; ได้แผนจริงโดยไม่บังคับ enable_seqscan | พบ index sport+starts_at อ่าน candidate 3 Party แล้ว active-capacity ตัด Full เหลือ2; count/data actual rows 1/2 | PASS [JSON + SQL + plans](evidence/task78/Q78-06.json) |

6 test methods ข้างต้นเป็น **automated PostgreSQL/query integration audit** ไม่ใช่ manual testing.
ชื่อ test source: [`SearchQueryAuditTests`](../backend/parties/test_search_query_audit.py).
JSON บันทึก expected/actual แยกกัน, source commit, SHA-256 ของ source, tester,
เวลารันจริงและ controlled time, Python/Django/PostgreSQL/database.
IDs ใน JSON เป็น IDs จาก test DB รอบนั้น ห้ามใช้แทน IDs ฐานจริง.

## ผล query plan / เหตุผลไม่เพิ่ม index

รันจริง 15 พ.ย. 2026 23:02 น. Asia/Bangkok; Python3.12.15, Django5.2.18, PostgreSQL17.11.
แผน count/data ใช้ `Index Scan` ที่ **`parties_par_sport_i_13983d_idx`**
ด้วย sport_id และช่วง starts_at (รวม default Open/starts_at>now).
Execution time ที่บันทึก: count **0.077ms**, data **0.145ms**; เป็น SELECT execution
บนข้อมูลสังเคราะห์หนึ่งครั้ง ไม่ใช่ end-to-end API latency, SLA หรือ benchmark production.

Catalog ใน Q78-05 แสดง FK indexes และ index `(party_id,left_at)` เดิมด้วย.
ไม่เพิ่ม index ซ้ำ sport_id หรือ composite เดิม ไม่เพิ่ม index สำหรับ title substring แบบคาดเดา.
ยังไม่มีหลักฐานว่าต้องเพิ่ม `(venue_id,starts_at)`/trigram/partial index ใน workload นี้.
แผนอื่นอาจเลือก sequential scan โดยเหมาะสมได้; tests ไม่บังคับชื่อ index หรือเวลาเฉพาะ.
หากข้อมูล/รูปแบบค้นหาเปลี่ยน ให้เก็บ query frequency, data distribution และ EXPLAIN ใหม่
ของ workload จริงก่อนตัดสินใจ; งานนี้ไม่ได้อ้างว่าทุก query ได้ประสิทธิภาพดีที่สุดแล้ว.

## วิธีรันซ้ำ (PowerShell จาก repo root)

ต้องมี `.env` จาก `.env.example` และ Docker Engine; เก็บ secret ใน `.env` ไม่ใส่ log.
ใช้ image dependencies ของทีม; ชื่อ project/DB/port นี้เป็นของทดสอบ Task78 เท่านั้น.

```powershell
$env:POSTGRES_HOST_PORT='55478'
$env:POSTGRES_DB='task78_audit'
docker compose -p task78-audit up -d --wait database
# หากยังไม่มี image ให้ build ก่อน
docker compose -p task78-audit build backend
# ปกติไม่สร้าง artifact; เพิ่ม env flags ด้านล่างเมื่อจะเก็บหลักฐานรอบใหม่
docker compose -p task78-audit run --rm -T --no-deps -e POSTGRES_DB=task78_audit backend python backend/manage.py test parties.test_search_query_audit --noinput --verbosity 2

$task78Source = git rev-parse HEAD
docker compose -p task78-audit run --rm -T --no-deps -e POSTGRES_DB=task78_audit -e "TASK78_SOURCE=$task78Source" -e TASK78_EVIDENCE_DIR=/app/backend/task78-evidence backend python backend/manage.py test parties.test_search_query_audit --noinput --verbosity 2
# JSON รอบใหม่อยู่ backend/task78-evidence; เก็บคนละรอบกับ evidence ที่ commit ไว้
docker compose -p task78-audit down
```

SQL oracle มี placeholders สำหรับ cursor execute ไม่ใช่ standalone seed.
ดู parameter order ในต้นไฟล์และ `audit(query)` ใน source; index inventory เป็น read-only SQL
ที่รันจาก cursor/psql ได้. การทดสอบรัน `ANALYZE` เฉพาะตารางใน test DB.

## การตรวจรวมและสิ่งที่ยังไม่ตรวจ

บน source `14d13e5` รันคำสั่งเทียบเท่า `make verify` โดยใช้ isolated project/DB:

```text
python backend/manage.py check                         -> 0 issues
python backend/manage.py makemigrations --check --dry-run -> No changes detected
ruff check backend scripts                            -> All checks passed
ruff format --check backend scripts                   -> 110 files already formatted
python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1
-> Ran 638 tests in 57.930s; OK (skipped=1)
```

Full transcript: [full-suite.txt](evidence/task78/full-suite.txt).
638 คือจำนวนที่ค้นพบ/รายงานรวม **มี 1 skipped** ไม่ใช่ผ่าน638เคส;
skip เป็น placeholder เดิมใน `conduct/test_reviews_unit.py` ที่เขียนรอ policy
(ข้อความเก่า ไม่ใช่ผลตรวจ No-show รอบใหม่). Task78 ทั้ง6methodsไม่มี skip/failure.
ไม่ได้รัน `make smoke` เพราะไม่มี runtime/UI/config/migration เปลี่ยน.

**Task84 ยังต้องทำแยก**: SQL acceptance ตาม QA inventory บน integrated revision/fixtures
ที่ยืนยันแล้ว บันทึก execution รายเคส/variant, readonly-before/after และข้อจำกัดจริง;
ไม่ยกผล Task78 ไปติ๊กผ่านทั้งหมดอัตโนมัติ.
Manual HTTP #98, UI #97, การจัดประเภทสนามจริง, race ข้าม requests และ production load
ไม่ได้ตรวจในงานนี้. ผู้รีวิว GearJP2 ยังต้องตรวจ PR ก่อน merge/Complete.
