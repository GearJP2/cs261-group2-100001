# Task84 — Search SQL acceptance / HTTP ก่อน–หลัง

[Issue #99](https://github.com/GearJP2/cs261-group2-100001/issues/99) ·
[Trello](https://trello.com/c/4dakJG9O) · `S2-US2-T-DB` · Gold.
รันจริง **16 พฤศจิกายน 2026** โดย agent บนเครื่อง Gold; ส่งให้ GearJP2 ตรวจรับ.
**ผลนี้เป็น automated real HTTP + PostgreSQL integration ไม่ใช่ unit test,
การกดหน้าเว็บโดยคน, UAT หรือผลยืนยัน TU provider.**

## Revision / dependency ที่ตรวจจริง

- Source ของผลหลัก: **`d032c84b375dffbaf916c5454cd484a495347fb2`**.
- รวม main **`69c53f5`** ซึ่ง merge [Task78 PR167](https://github.com/GearJP2/cs261-group2-100001/pull/167)
  แล้ว และมี search API บน main; ไม่ใช้คำว่า Task78 ผ่านแทนผลรัน Task84.
- เทียบ Design [S02–S12, S15–S16, S22](us2-search-test-cases.md),
  [PLAN-US2-01/02/03/04/05](sprint-2-planning-contract.md), และ IT-US2-DB-01/02/03 ใน Issue.
  หมายเลข AC1/2/3/5 ใช้ mapping ของ Story/แผนเดิม ไม่กำหนดมติแทนทีม.
- Task79 มี implementation เพิ่มที่ branch `feat/s2-us2-b-01-search-api` ยังไม่ merge
  ณตรวจ จึงทดสอบเพิ่มบน candidate **`c0639a8`** ใน detached worktree ด้วย test source เดียวกัน:
  6 methods ผ่าน ไม่มี skip. เก็บ [transcript](evidence/task84/candidate-task79-suite.txt)
  และ [revision/test SHA-256](evidence/task84/candidate-metadata.json) แยกจากผลหลัก.
  ไม่เอา candidate code เข้า PR นี้ ไม่อ้างว่ามัน merge แล้ว; หาก head/contract เปลี่ยนให้ retest.

## Scope / ข้อมูลที่เตรียม

1. แยก Compose project `task84-acceptance` และ PostgreSQL port55484;
   test runner สร้าง `test_task84_acceptance` แล้วลบเมื่อจบ ไม่ใช้ฐานเดิมของผู้ใช้.
2. ควบคุมเวลา N=`2030-11-19T12:00:00+07:00`,
   A=`2030-11-20T00:00:00+07:00`, B=`2030-11-21T00:00:00+07:00`.
   เวลานี้เป็น fixture clock ไม่ใช่เวลาทดสอบจริง (JSON ระบุ executed_at แยก).
3. เตรียม11 Party: lower=A, inside=B−1µs, upper=B, overlap=A−1µs,
   outdoor, unknown type, other sport, full(cap2), started=N, ended ที่ ends_at=N,
   cancelled ที่จบแล้ว. รายอื่น capacity3; active Host+Member2 แถว, left1 แถว,
   Pending1, Rejected1 ต่อ Party.
4. 2กีฬา/3สนาม Indoor/Outdoor/NULL; Indoor รองรับ2กีฬา ส่วน Outdoor/NULL
   รองรับกีฬาแรก. NULL แปลว่ายังไม่จัดประเภท ไม่ใช่ Outdoor. ทุกชื่อ/ประเภทใน fixture เป็น **mock**.
5. DB84-04 เพิ่ม101 Party ที่ starts_at เท่ากัน (รวม112 Party)
   ชื่อ `DB84 page 000..100`, active0; ค้นเฉพาะ marker นี้เพื่อแยก total จาก baseline11.
6. สร้าง verified identity/session สังเคราะห์ใน test DB ให้ Host กับ applicant;
   browser/TU password ไม่เกี่ยวข้อง และ cookie/CSRF เก็บในหน่วยความจำ ไม่ใส่หลักฐาน.

## วิธีตรวจที่ใช้ทุก variant

อ่าน [`us2_search_snapshot.sql`](../database/seeds/us2_search_snapshot.sql) ด้วย cursor ของ
PostgreSQL ก่อนส่ง request. SQLใช้ correlated count + CASE อิสระ ไม่เรียก ORM/helper ของ Search
เพื่อสร้าง expected state/count. รายชื่อ Party ที่ควรพบระบุไว้ล่วงหน้าใน fixture aliases ของแต่ละเคส;
แปลงเป็น ID จากข้อมูลที่สร้างจริง และเรียง starts_at,id ตาม SQL ก่อนส่ง GET.

ส่ง HTTP ผ่าน `urllib` ไป Django `LiveServerTestCase` บน loopback port แบบ dynamic:
GET `/api/v1/parties?...` แล้วตรวจ HTTP200, exact ordered IDs, ไม่มีIDซ้ำ,
total/page/page_size, sport/venue/start/state/count/remaining_slots เทียบ SQL.
GET Detail ของผลลัพธ์ทุกตัวตรวจ state/count ที่เวลา N เดียวกัน.
จากนั้นอ่าน SQL snapshot ซ้ำและ assert เท่ากันทั้งก่อน–หลัง GET/Detail.

ขอบเขต readonly proof คือ projection ใน SQL: Party IDs/title/sport/venue/type/start/end/
capacity/cancelled_at/updated_at, active count และ Membership/JoinRequest history ที่ระบุในไฟล์.
ไม่ใช่ claim ว่าทุกตาราง/ทุกคอลัมน์รวม session ไม่เปลี่ยน.
JSON มี baseline snapshot, SQL expected rows ราย query, raw request/response,
before/after SHA-256 และผล assert; ไม่มีการสรุป Pass จากจำนวน tests เพียงอย่างเดียว.

## ผลรายกลุ่ม — Expected / Actual

ตารางราย **38 variants** พร้อม path/query จริง, expected/actual IDs/state/count/total,
status, SQL hashes, source/เวลา และตำแหน่ง raw event: [execution.csv](evidence/task84/execution.csv).
เลข variant เช่น `DB84-02/1` อ้างตามลำดับ execution ใน CSV ไม่ใช่การสร้าง AC ใหม่.

| Case / mapping | ขั้นตอนและ Expected | Actual | ผล / หลักฐาน |
|---|---|---|---|
| DB84-01 (8 variants), IT-US2-DB-01, S02–S05 | ค้นไม่กรอง/กีฬา/สนาม/Indoor/Outdoor/AND+q; Indoorรองรับหลายกีฬาแต่ไม่คูณแถว; NULLพบเมื่อไม่กรองtype; คู่กีฬา–สนามไม่รองรับ/IDไม่มีจริงต้องว่าง | IDs/order/countตรง fixture+SQL ทุกvariant; Open7, sportแรก6, Indoor/สนามIndoor5, Outdoor1, AND+q1, incompatible/unknownID0; active2ไม่กลายเป็น3จากleftหรือเพิ่มจากrequests | PASS [JSON](evidence/task84/DB84-01.json) |
| DB84-02 (4), IT-US2-DB-02, S06–S08 | `[A,B)` รวมlower/inside ตัดoverlap/upper; ขอบล่างอย่างเดียวรวมupper, ขอบบนรวมoverlap; instantUTCเท่ากับBangkok | 2/3/3/2 รายการตรงSQLตามลำดับ; +07/Z instantเดียวกันได้IDsเดียวกัน | PASS [JSON](evidence/task84/DB84-02.json) |
| DB84-03 (6), IT-US2-DB-02/03, S10–S12 | Open/Full/InProgress/Completed/Cancelled/all; ณstartเป็นInProgress, ณendเป็นCompleted; Cancelledชนะเวลาและcapacity; เทียบDetail | totals7/1/1/1/1/11; state/countตรงSQL+Detailทุกผลลัพธ์ | PASS [JSON](evidence/task84/DB84-03.json) |
| DB84-04 (8), IT-US2-DB-01, S15–S16 | ค้น101รายการที่เวลาเท่ากัน; page1..6/999 size20 แล้วsize100; filterก่อนtotal/page และidเป็นtie-break | ทุกหน้ามีtotal101; page1..5=20, page6=1, page999=0, size100=100; ordered IDsตรงSQL ไม่มีjoin fanout | PASS [JSON](evidence/task84/DB84-04.json) |
| DB84-05 (6 search variants +3write HTTP), IT-US2-DB-03, S22 | Openก่อนapprove; Hostส่งdecision Approved แล้วต้องหายจากOpen/อยู่Full; applicantส่งleaveแล้วกลับOpen; Hostcancelแล้วหายจากOpen/อยู่Cancelled; อ่านSQLหลังcommitทุกช่วง | active2→3→2, leaveเก็บmembershipและApproved history; Open counts1→0→1→0 ตามขั้นตอน; Full/Cancelledพบเป้าหมาย; SQL/Detail/Searchตรงกันหลังแต่ละwrite | PASS [JSON](evidence/task84/DB84-05.json) |
| DB84-06 (6), S09/S17–S18 เฉพาะDB readonly | ส่งช่วงเท่ากัน/กลับด้าน/nooffset/date-only/unknownkey/size101; ต้อง400INVALID_INPUTและprojectionSQLเท่าเดิม | ทุกvariant400; before/after SQLเท่ากัน ไม่เปลี่ยนParty/historyที่ตรวจ | PASS [JSON](evidence/task84/DB84-06.json) |

DB84-05 เป็น **sequential committed refresh** ไม่ใช่ race.
การทดสอบ GET อ่านซ้ำไม่ได้รับประกัน snapshot เดียวกันข้าม HTTP requests ที่มี writers แข่งขันกัน.
งานนี้ไม่ทดสอบการจองที่หรือเขียน query/transaction ใหม่.

## Source / Environment / ผลตรวจรวม

Primary JSON ทั้ง6ไฟล์รัน 16พ.ย.2026 ประมาณ01:56–01:57 Asia/Bangkok;
แต่ละไฟล์มีเวลาจริง, source fullSHA, SHA-256 ของ view/service/test/SQL และ DB name.
Python3.12.15 / Django5.2.18 / PostgreSQL17.11 / Linux Docker บนเครื่อง Windows ของ Gold.

- Django check: 0 issues; `makemigrations --check --dry-run`: No changes detected.
- Ruff check: All checks passed; Ruff format: 111 files already formatted.
- ชุดรวมบน source `d032c84`: **Ran644 tests in66.030s; OK(skipped=1)**.
  มี1skipเดิมใน `conduct/test_reviews_unit.py` (legacy policy placeholder)
  จึงไม่เขียนว่าผ่าน644เคส; Task84ทั้ง6methodsไม่มีskip/failure.
  [Integrated transcript](evidence/task84/integrated-suite.txt) เก็บผลจริง (ตัดเฉพาะช่องว่างท้ายบรรทัด).
- Candidate Task79 `c0639a8`: **6 tests in11.729s; OK**, ไม่มีskip;
  ใช้testsourceSHAเดียวกัน แต่เป็นคนละDB/คนละrevisionกับprimary.
- ไม่มี runtime/config/migration เปลี่ยน จึงไม่รัน `make smoke` ใน Task84.
- ไม่แก้ inventoryกลางจาก Not run ให้เป็น Pass ของ Manual API/UI; ผลรอบนี้อยู่ใน execution.csv ของงานนี้เท่านั้น.

## วิธีรันซ้ำ / เก็บหลักฐานรอบใหม่ (PowerShell)

จาก repo root มี `.env` ของทีมและ Docker Engine. ตั้ง project/DB/port เฉพาะนี้
ไม่ส่ง secret หรือ cookie ลง log. ไม่ต้องเชื่อมต่อ test DB หลังรันเพราะ runner ลบให้;
ใช้ raw snapshot/response ที่บันทึกไว้ หรือรันเคสใหม่เพื่อดูผลใหม่.

```powershell
$env:POSTGRES_HOST_PORT='55484'
$env:POSTGRES_DB='task84_acceptance'
docker compose -p task84-acceptance up -d --wait database
# ทำเมื่อยังไม่มี image/dependencies ของทีม
docker compose -p task84-acceptance build backend

# รันโดยไม่เขียน evidence
docker compose -p task84-acceptance run --rm -T --no-deps -e POSTGRES_DB=task84_acceptance backend python backend/manage.py test parties.test_search_database_acceptance --noinput --verbosity 2

# เลือกชื่อโฟลเดอร์ใหม่ทุกครั้ง; ไม่เขียนทับไฟล์หลักฐานเก่า
$task84Source = git rev-parse HEAD
docker compose -p task84-acceptance run --rm -T --no-deps -e POSTGRES_DB=task84_acceptance -e "TASK84_SOURCE=$task84Source" -e TASK84_EVIDENCE_DIR=/app/backend/task84-new-run backend python backend/manage.py test parties.test_search_database_acceptance --noinput --verbosity 2
docker compose -p task84-acceptance down
```

SQL snapshot รับ parameter เดียวคือ aware reference time; ดู `snapshot()` ใน
[`test_search_database_acceptance.py`](../backend/parties/test_search_database_acceptance.py).
เปิด JSON → baseline_sql_snapshot เพื่อดูข้อมูลตั้งต้น → events ตาม CSV เพื่อดู HTTP/SQL expected/actual.
PASS artifact เขียนหลัง assertions ของทั้งกลุ่มสำเร็จ และใช้ exclusive create ป้องกันเขียนทับ;
ถ้า commandล้มเหลว/ไฟล์หาย/Fail ไม่ถือว่าผ่านจากไฟล์ของรอบเก่า.

## ข้อจำกัด / ส่งต่อผู้ตรวจ

ไม่ตรวจ Manual UI/browser timezone/reset/stale responses (#97), Manual APIทุกvalidation/authvariant (#98),
TU providerจริง, ข้อมูลสนามจริง, simultaneous race หรือ production load.
Fixturesในเวลา2030เป็นการควบคุมboundary ไม่ใช่ผลตรวจวันเปิดสนามจริง.
Task78ยังเป็นงานquery/index auditเดิม งานนี้เพิ่มหลักฐานHTTP+SQLแยกต่างหาก;
reviewจากGearJP2/CIยังต้องตรวจสถานะจริงก่อนย้ายComplete ไม่อนุมัติแทนทีม.
