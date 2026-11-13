# Task66 — SQL เทียบ Members API ของ US6

งาน: [Issue #81](https://github.com/GearJP2/cs261-group2-100001/issues/81) · [Trello](https://trello.com/c/dipOXcWi) · ผู้รับผิดชอบ Gold (`gold555555`) · ผู้ตรวจที่ขอ GearJP2

**สถานะส่งมอบ: ชุดตรวจ/หลักฐานพร้อม review แต่ Task66 ยังไม่ผ่าน acceptance ทั้งหมด**
ไม่มีการแก้ production API ของเพื่อน ไม่มี migration และไม่ปิด Issue #81 ใน PR นี้

## 1. ทดสอบตรงไหน และต่างจาก Task60 อย่างไร

Task60 ตรวจ query ของสมาชิก active แล้ว งานนี้ตรวจข้ามชั้น: response ของ
`GET /api/v1/parties/{party_id}/members` → เทียบ User IDs, จำนวน, บทบาท กับ SQL
ที่อ่าน `PartyMembership.left_at IS NULL` จริง แล้วเทียบจำนวนกับ Party Detail ด้วย
ไม่ได้ใช้ helper ของ endpoint มาคำนวณ expected จึงจับการนับสมาชิกเกินได้

ขอบเขต US6 AC1–3 / IT-US6-DB-01..03:

- Host และสมาชิก active ต้องตรง SQL, ไม่ซ้ำและไม่ปนปาร์ตี้อื่น
- Pending/Rejected เป็นคำขอ ไม่เพิ่มสมาชิก; left เป็นประวัติ ไม่ใช่ active
- POST อนุมัติและปฏิเสธแล้วอ่าน SQL/API ซ้ำ; อนุมัติซ้ำไม่เพิ่มสมาชิกอีก
- GET ไม่เปลี่ยน Membership/JoinRequest/Profile; Profile หายไม่ทำให้สมาชิกหาย
- left_at ที่เตรียมด้วย SQL ทำให้ count ลดเพียงครั้งเดียวและประวัติยังอยู่
- Host เก่าที่ไม่มี active row ต้องไม่ทำให้ Members API ขัดกับ SQL/Party Detail

ไม่ครอบคลุม permission/PII matrix ทั้งหมดของ Task65, UI/UAT ของ Task64,
race/rollback ของ Task57/75 หรือ HTTP leave จริงของ Task70

## 2. ชนิดหลักฐานและ source ที่รันจริง

วันที่ **5 พฤศจิกายน 2026** (Asia/Bangkok) ผู้ช่วยรันตามคำขอ Gold;
ไม่อ้างว่า Gold กดทดสอบหน้าเว็บเองหรือเป็น UAT ที่ผู้ใช้ตรวจรับแล้ว

| ชุด | Source ที่ตรวจ | วิธี | ผลจริง |
|---|---|---|---|
| Main | `e5a254e64324603cfb11e000e2cd6400d66c6f3e` + test harness นี้ | Django test client + PostgreSQL | 7 Task66 tests **SKIPPED** เพราะไม่มี Members route |
| Main | source เดียวกัน | HTTP จริงผ่าน urllib ไป runserver + SQL จริง | Members 404 → **BLOCKED** |
| Preview | main ข้างต้น merge แบบไม่ commit กับ PR #123 head `84e3cf1faa2729e6320b6789c4ad5e90f593dd38` + harness นี้ | Django test client + PostgreSQL | **6 PASS / 1 FAIL** |
| Preview | source เดียวกัน | HTTP จริง + SQL จริง, 22:42:29–22:42:31 +07:00 | 13 observations PASS / 1 FAIL / 1 BLOCKED; baseline 6 ปาร์ตี้และ SQL leave 2 รอบนับแยก observations |
| Main regression | main + harness นี้ | Django check, migration drift, Ruff, full tests | checks ผ่าน; 350 discovered = **343 ผ่าน + 7 skipped**, 22.208s |

Preview เป็น checkout ทดลองในเครื่อง ไม่ได้นำ commit ของ PR #123 มารวมใน branch/PR ของ Task66
รายงาน JSON มีเวลาเริ่ม/จบ, DB, รุ่น Python/Django/PostgreSQL และ SHA-256 ของ source
ที่ mount ใช้งานจริง จึงไม่อ้างว่า uncommitted preview เป็น commit ที่ merge เข้า main แล้ว

Environment: Docker Engine 29.6.2, Python 3.12.15, Django 5.2.18, PostgreSQL 17.11.
Compose project `s2-task66` มี volume/network ของตัวเอง, DB `s2_task66_evidence`,
test runner สร้าง/ลบ `test_s2_task66_evidence`; host port HTTP 18066 / PostgreSQL 15466.
ไม่ได้แก้ `.env`, ไม่หยุด `cstu_backend`/`cstu_db`, ไม่ใช้ข้อมูลจริง

## 3. ข้อมูลตั้งต้นและการเข้าสู่ระบบทดสอบ

ใช้ `seed_sprint2 --confirm-test-data` ของ Task46: MOCK 7 users, 6 parties,
2 sports, 4 venues. แต่ละปาร์ตี้เริ่มมี H (Host) และ M (active), left มีประวัติถอนแล้ว
Open มี A=Pending/B=Rejected; Last slot มี A/B=Pending.
Seed ใช้เวลาปัจจุบันและคืน baseline ทุกครั้ง; **อย่า hardcode ID จากรอบนี้**

บัญชี fixture ไม่มี usable password หรือ TU identity ตั้งต้น โปรแกรมใช้
`accounts.test_support.force_university_login` สร้าง session/identity **เฉพาะฐานจำลอง**
แล้วส่ง cookie + CSRF token ใน memory ไป HTTP จริง ไม่เรียก TU API ไม่ใช่การทดสอบ Login.
ไม่เก็บ password, cookie, CSRF token หรือ TU key ในไฟล์หลักฐาน และ logout session จำลองหลังรัน

## 4. Test cases, ขั้นตอน, Expected และ Actual

ก่อนแต่ละ automated test Django แยก transaction ให้; HTTP rehearsal เริ่ม seed ใหม่หนึ่งครั้ง
แล้วทำ M01→M08 ตามลำดับ จึงต้องอ่าน count ให้สัมพันธ์กับขั้นตอนก่อนหน้า

| ID / อ้าง AC | ขั้นตอนที่รัน | Expected | Actual บน preview / หลักฐาน |
|---|---|---|---|
| M00 / prerequisite | บน main เรียก Members ของ fixture Open | route พร้อมก่อนทดสอบ API | HTTP **404**, BLOCKED; `main-http-sql.json` |
| A01 / M01 / IT-01 | seed → SELECT active SQL → GET Members และ Detail ของทั้ง 6 parties | H/M รวม 2; A/B/left ไม่ปน; IDs/roles/count ตรง | **PASS 6 parties**; แต่ละ response และ SQL IDs อยู่ JSON |
| A06 / M02 / read-only | snapshot ทุก field/row ของ Membership, JoinRequest, Profile → GET → snapshot อีกครั้ง | ไม่เปลี่ยนข้อมูล | **PASS unchanged** |
| A02 / M03 / IT-02 approve | Open/A Pending → POST decision `{"status":"Approved"}` → SQL/Members/Detail | 200, Approved, H/M/A รวม 3 | **PASS**, status200/count3 |
| A02 / M04 / duplicate | POST approve request เดิมอีกครั้ง → อ่านซ้ำ | 409; count คง 3; ไม่เพิ่มซ้ำ | **PASS**, status409/count3 |
| A03 / M05 / reject | Last slot/B Pending → POST `{"status":"Rejected"}` → อ่านซ้ำ | 200, Rejected; ไม่สร้าง membership; countคง2 | **PASS**, status200/count2 |
| A04 / M06 / IT-03 | UPDATE M.left_at ด้วย SQL ใน Open → SELECT history → Members/Detail; UPDATE ค่าเดิมซ้ำ | count3→2→2; pk/joined_at เดิม, left_at มีค่า, Approved request ยังอยู่ | **PASS 2 writes**; JSON มี history_before/after และ actual IDs/count; **ไม่ใช่ HTTP leave** |
| A05 / M07 / fallback | ลบ Profile ของสมาชิก active A ใน test DB → GET | A ยังปรากฏ, fallbackชื่อ; count2 | **PASS**; response มี `display_name` สำรอง; automated แยกกรณี profile M หายและ X อยู่อีกปาร์ตี้ |
| A07 / M08 / legacy | เตรียม H.left_at ให้ไม่ active → SQL/Members/Detail | Members ตรง actual rows ตาม Task60: A1คน | **FAIL**: SQL IDs `[2]`, count1; API IDs `[1,2]`, count2; Detail count1 |
| M09 / IT-02 leave จริง | POST leave แล้วตรวจ request/history/API | ต้องมี endpoint Task70 และเทียบผลหลังเรียกจริง | **BLOCKED / NOT RUN** ไม่มี leave endpoint ใน source ที่ตรวจ; M06 ใช้ปิดเคสนี้ไม่ได้ |

`Axx` = automated integration ผ่าน Django test client + PostgreSQL จริง ไม่ใช่ unit mock;
`Mxx` = ผู้ช่วยรัน HTTP/SQL rehearsal จริงด้วย script ไม่ใช่ human manual UAT.
M02 snapshot ใช้ ORM ตรวจ fields ทั้งหมด; SQL oracle เป็น read-only raw SQL แยกจาก endpoint

## 5. หลักฐานให้เปิดดู

- [Main HTTP/SQL JSON](evidence/task66/main-http-sql.json): request method/path, HTTP404, BLOCKED
- [Preview HTTP/SQL JSON](evidence/task66/preview-http-sql.json): request/response ทุกครั้ง, payload,
  SQL IDs/count, history before/after, เวลาและ source fingerprints; ไม่มี auth headers
- [Main targeted test log](evidence/task66/main-tests.log): ชื่อ 7 tests และเหตุผล skipped
- [Preview targeted test log](evidence/task66/preview-tests.log): 6ผ่าน/1fail พร้อม assertion และ traceback
- [Main verification log](evidence/task66/main-verification.log): check/migration/Ruff/full regression
- [psql active rows หลัง rehearsal](evidence/task66/preview-active-sql.log)
- [psql membership history หลัง rehearsal](evidence/task66/preview-history-sql.log): H/M/left ยังอยู่
- [Guard refusal](evidence/task66/guard-refusal.log): โปรแกรมปฏิเสธ DB ชื่อทั่วไปก่อน seed

Test source: `backend/parties/test_members_database.py`;
rehearsal source: `scripts/us6-db-api-evidence.py`;
active SQL: `database/seeds/us6_active_members.sql` (reuse Task60);
history SQL: `database/seeds/us6_members_history.sql`.
ไฟล์ raw เหล่านี้เป็นหลักฐานข้อมูลจริงที่ทำซ้ำได้ จึงไม่ใช้ภาพตกแต่งแทนผลทดสอบ

## 6. ทำซ้ำบนเครื่องใหม่ (PowerShell ที่ repository root)

เปิด Docker, เตรียม `.env` ตาม README ของทีม (`DEBUG=true`) และ build image ของทีมก่อน
คำสั่งต่อไปใช้ project/DB แยก ไม่ใช้ `docker compose up` บนฐานข้อมูลของงานจริง
ต้องส่ง `-e POSTGRES_DB=...` ให้ backend ด้วย เพราะ `env_file: .env` ไม่รับชื่อ DB จาก shell โดยอัตโนมัติ

```powershell
$env:POSTGRES_DB = 's2_task66_evidence'
$env:POSTGRES_HOST_PORT = '15466'
$env:APP_PORT = '18066'
docker compose -p s2-task66 up -d --wait database
docker compose -p s2-task66 run --rm -T -e POSTGRES_DB=s2_task66_evidence backend python backend/manage.py test parties.test_members_database --noinput --verbosity 2

# บน main ณ source ที่รายงาน: 7 skipped, ไม่ใช่ผ่าน acceptance
docker compose -p s2-task66 run -d --name s2-task66-http --service-ports --no-deps -e POSTGRES_DB=s2_task66_evidence backend sh -c 'python backend/manage.py migrate --noinput && exec python backend/manage.py runserver 0.0.0.0:8000 --noreload'
docker exec -e US6_EVIDENCE_SOURCE='ระบุ commit จริงจาก git rev-parse HEAD' s2-task66-http python scripts/us6-db-api-evidence.py > task66-main-http-sql.json
```

HTTP script คืน **exit 1 เมื่อมี FAIL หรือ BLOCKED** เป็นพฤติกรรมที่ตั้งใจ;
เปิด JSON ดู status รายเคส ห้ามตีความว่า script มีผลผ่านทั้งหมดเพราะสร้างไฟล์ได้
โปรแกรมปฏิเสธเมื่อ DEBUG ไม่เปิด/DB ไม่ขึ้นต้น `s2_task66_`/URL ไม่ใช่ HTTP loopback
คำสั่ง script จะ reset เฉพาะ fixtures S2 และเปลี่ยนสถานะ fixtures ในฐานจำลองนี้

### Preview แบบไม่รวมโค้ดเพื่อนใน PR ของเรา

กำหนด `$preview` เป็นโฟลเดอร์ใหม่ที่ยังไม่มี worktree; รันจาก repository งานนี้
ใช้ commit เต็มที่ pin ไว้เพื่อได้ implementation เดียวกับหลักฐาน; การ fetch head ครั้งใหม่อาจเปลี่ยน

```powershell
git fetch origin pull/123/head:refs/remotes/origin/pr-123
$preview = Join-Path (Split-Path (Get-Location) -Parent) 'cs261-task66-preview'
git worktree add --detach $preview e5a254e64324603cfb11e000e2cd6400d66c6f3e
git -C $preview merge --no-commit --no-ff 84e3cf1faa2729e6320b6789c4ad5e90f593dd38
Copy-Item backend/parties/test_members_database.py "$preview/backend/parties/test_members_database.py"
docker compose -p s2-task66 run --rm -T -e POSTGRES_DB=s2_task66_evidence -v "${preview}/backend:/app/backend" backend python backend/manage.py test parties.test_members_database --noinput --verbosity 2

# หยุดเฉพาะ test container ที่คำสั่งก่อนหน้าสร้าง
docker rm -f s2-task66-http
docker compose -p s2-task66 run -d --name s2-task66-http --service-ports --no-deps -e POSTGRES_DB=s2_task66_evidence -v "${preview}/backend:/app/backend" backend sh -c 'exec python backend/manage.py runserver 0.0.0.0:8000 --noreload'
docker exec -e US6_EVIDENCE_SOURCE='main e5a254e + PR123 84e3cf1 + harness ของ PR Task66' s2-task66-http python scripts/us6-db-api-evidence.py > task66-preview-http-sql.json

# SQL read-only หลัง rehearsal; ทุกข้อมูลในผลนี้เป็น MOCK
Get-Content database/seeds/us6_active_members.sql -Raw | docker compose -p s2-task66 exec -T database sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d s2_task66_evidence'
Get-Content database/seeds/us6_members_history.sql -Raw | docker compose -p s2-task66 exec -T database sh -c 'psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d s2_task66_evidence'
```

Preview tests ที่ pin นี้ต้องพบ 1 FAIL; ถ้ากติกาหรือ implementation เปลี่ยนให้ใช้ commit ใหม่
และเก็บหลักฐานรอบใหม่ อย่าแก้ expected ให้ตรง output โดยไม่มีมติทีม
ใน rehearsal seed ครบก่อนทุก run; psql หลัง M08 จึงเห็น state หลัง approve/reject/SQL left แล้ว
ใน Open จะเหลือ A active คนเดียว ขณะที่ H/M/left ยังมี membership rows เก็บประวัติ

หยุดเฉพาะเครื่องทดสอบที่สร้างในขั้นตอนนี้ (เก็บ volume ไว้):

```powershell
docker rm -f s2-task66-http
docker compose -p s2-task66 down
Remove-Item Env:POSTGRES_DB, Env:POSTGRES_HOST_PORT, Env:APP_PORT
```

## 7. ข้อพบ / bug และ retest ที่ต้องตามต่อ

**DB66-BUG-01 (reproduced; รอทีมตัดสิน policy)**:
PR #123 `party_members` สร้าง Host จาก Party เสมอ แม้ Host มี left_at แล้วหรือไม่มี membership
ต่างจาก Task60 ที่อ่าน actual active rows. M08 พิสูจน์ count1 เทียบ2 และ A07 fail จริง
ยังไม่ถือว่าการให้ Host ถอนตัวเป็น flow ที่รองรับ; นี่เป็น legacy consistency probe
ทีมต้องเลือกว่าจะยึด actual rows หรือเปลี่ยนนโยบาย count ทุกจุดให้ตรงกัน แล้วเจ้าของ Task61 แก้
หลังแก้ให้รัน A07/M08 ซ้ำและบันทึก commit ใหม่ → PASS ก่อนตรวจรับ ไม่ใช้ expectedFailure ซ่อนผล

**DB66-DEP-01**: Members API PR #123 ยังไม่ merge ณ รอบตรวจ จึงไม่ปิด Task66/Issue #81
แม้ CI ของ branch นี้ผ่าน regression (มี 7 skipped อย่างชัดเจน)

**DB66-DEP-02**: Task70 ยังไม่มี leave route ใน source ที่ตรวจ.
หลังพร้อมต้องใช้ POST leave จริง แล้วเทียบ SQL/Members/Detail, pk/joined_at/left_at/request เดิม
ทดสอบกดซ้ำตาม contract ที่ทีมตกลงด้วย; M06 เป็นเพียง DB-state rehearsal และไม่ใช้ปิด IT-US6-DB-02 ทั้งข้อ

Checklist รับงาน: IT-01/03 มีหลักฐาน preview ตามรายละเอียด แต่ยังไม่ติ๊กตรวจรับบน main;
IT-02 หลัง approve มีผลแล้ว ส่วน real leave BLOCKED. เก็บการ์ด Doing จน dependency/FAIL ถูกแก้
หรือทีมอนุมัติ scope แยกชัดเจนก่อนย้าย Done/Complete
