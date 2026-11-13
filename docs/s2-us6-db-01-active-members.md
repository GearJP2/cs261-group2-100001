# Task60 — S2-US6-DB-01: active membership / User / Profile

[Issue #75](https://github.com/GearJP2/cs261-group2-100001/issues/75) /
[Trello Task60](https://trello.com/c/EFL3QV9A) /
[US6](https://trello.com/c/foIWawSZ), AC 1–3 ตามการ์ด Story

## ขอบเขตและผลตรวจของเดิม

ฐานเริ่มงาน `main` ที่ `cb178a7` มี `count_active_members` ใช้ `left_at IS NULL`
ถูกต้องอยู่แล้ว แต่ยังไม่มี query กลางที่อ่าน User/Profile โดยไม่เกิด N+1
จึงเพิ่ม `parties.services.active_memberships(party)` และให้ตัวนับเดิมใช้ query เดียวกัน
ไม่เขียน Members API ซ้ำ ไม่เพิ่ม migration/index/dependency และไม่เปลี่ยน schema

กติกา query:

- membership ต้องอยู่ใน Party ที่ส่งเข้ามา และ `left_at IS NULL` เท่านั้น
- อ่าน User และ Profile ด้วย `select_related("user__profile")`; ไม่มี Profile ก็ไม่ตัดสมาชิกทิ้ง
- เรียง `joined_at, pk` เพื่อให้แถวที่เวลาเท่ากันมีลำดับแน่นอน
- Pending/Rejected ไม่ถูก join มาสร้างสมาชิก; Approved ที่ถอนแล้วก็ไม่ถูกนับ
- ใช้ unique `(party,user)` และ index `(party,left_at)` เดิม ไม่เพิ่ม index ซ้ำ
- ไม่สังเคราะห์ Host row และไม่แก้/ลบประวัติระหว่างอ่าน
- helper นี้เป็น internal query ไม่ใช่ permission guard/serializer; endpoint ต้องตรวจสิทธิ์และเลือก public fields เอง

## ขอบเขตเทียบกับ PR #123 และ Task66

Members API ของเพื่อนอยู่ [PR #123](https://github.com/GearJP2/cs261-group2-100001/pull/123)
ซึ่งยังไม่ merge ณ เวลาเริ่มตรวจ จึงไม่เอา implementation API นั้นมาปน PR Task60
query ใน PR นั้นกรอง `left_at IS NULL` และ eager-load profile เช่นกัน
เมื่อรวมงาน ให้ endpoint reuse helper จาก `parties.services` แทนมี helper กฎเดียวกันซ้ำใน views
และให้ Task66 เทียบ Members response กับ SQL นี้จริงบน revision ที่รวม API แล้ว

จุดที่ต้องตรวจรับเพิ่มใน API: PR #123 เพิ่ม Host ลง response แม้ไม่มี active Host membership
แต่ตัวนับ Party นับจาก membership จริง จึงอาจไม่ตรงกันบนข้อมูล legacy ที่ Host ถอน/ไม่มี row
Task60 ไม่ซ่อมข้อมูลประวัติและไม่เพิ่มสมาชิกอัตโนมัติเพื่อซ่อนความผิดปกตินี้
ให้เจ้าของ API/ทีมยืนยันนโยบายข้อมูล legacy แล้วทดสอบความสอดคล้องใน Task66 ก่อนรับครบทั้ง flow
ผล Task60 ไม่ใช่การรับรอง Members endpoint หรือการปิด Task66

## ชุดข้อมูลและ SQL ที่ใช้

ใช้ Task46 `seed_sprint2` บนฐานใหม่ `s2_us6_db_check` แยกจากฐานพัฒนาปกติ
ข้อมูล MOCK ทั้งหมด ไม่ใช้บัญชี/credentials นักศึกษาจริง
H และ M active, left มีประวัติที่ไม่ active, A Pending, B Rejected ใน Open,
X เป็น outsider; มี 6 Party (Open/Last slot/Full/InProgress/Completed/Cancelled)

SQL oracle คือ `database/seeds/us6_active_members.sql` เป็น SELECT อย่างเดียว
เลือกเฉพาะ fixture marker+Host แล้ว INNER JOIN active memberships/User
และ LEFT JOIN Profile จึงไม่ทำแถวหายเมื่อไม่มี profile
ส่งเฉพาะ ids, display_name/fallback, role, joined_at, count ไม่มี email/password/token/เครดิต
`COUNT(*) OVER (PARTITION BY party_id)` นับจากแถวสมาชิก ไม่ join requests จึงไม่คูณจำนวน
SQL fallback เป็นข้อมูลสำหรับตรวจ ไม่ได้เพิ่ม API serialization ใหม่ในงานนี้

## วิธีทำซ้ำ — manual SQL

Environment: Windows PowerShell, Docker Compose, Python 3.12, PostgreSQL 17, Django ใน image ทีม
ตรวจว่า Compose ชี้ PostgreSQL local สำหรับทดสอบก่อนสร้างฐาน; ไม่แก้ `.env` และไม่ flush ฐานทีม
หากฐาน `s2_us6_db_check` มีแล้ว ให้ข้าม createdb และตรวจว่าเป็นฐานทดสอบของรอบนี้

```powershell
$us6DbUser = docker compose exec -T database printenv POSTGRES_USER
docker compose exec -T database createdb -U $us6DbUser s2_us6_db_check
docker compose run --rm -T -e POSTGRES_DB=s2_us6_db_check backend python backend/manage.py migrate --noinput
docker compose run --rm -T -e POSTGRES_DB=s2_us6_db_check backend python backend/manage.py seed_sprint2 --confirm-test-data --at 2026-11-02T15:00:00+07:00
docker compose cp database/seeds/us6_active_members.sql database:/tmp/us6_active_members.sql
docker compose exec -T database psql -X -U $us6DbUser -d s2_us6_db_check -v ON_ERROR_STOP=1 -f /tmp/us6_active_members.sql
docker compose exec -T database psql -X -U $us6DbUser -d s2_us6_db_check -c 'SELECT u.username,m.left_at IS NOT NULL AS has_left,COUNT(*) FROM parties_partymembership m JOIN accounts_user u ON u.id=m.user_id GROUP BY u.username,has_left ORDER BY u.username;'
```

## ผลตรวจรายเคส — 2 พ.ย. 2026

Base commit `cb178a7`, branch `chore/s2-us6-db-active-members`; exact implementation commit ดูใน PR
การตรวจดำเนินการผ่านผู้ช่วยรันคำสั่ง ไม่อ้างว่าเป็น UAT ที่คนกดหน้าเว็บ

### DB60-M01 — baseline SQL / ประวัติคนถอนตัว (manual SQL)

Precondition: migrate + seed ตามคำสั่งข้างต้นบนฐานใหม่
Steps: รันไฟล์ SQL แล้วตรวจทุก Party; ตามด้วย SQL GROUP BY ประวัติ
Expected: 12 active rows = H+M ในแต่ละ6Party; role Host/Member และ count=2 ทุกแถว;
ไม่มี A/B/left/X/inactive ปน; history ของ left ยังอยู่6แถว
Actual: psql คืน12แถว, user_ids1(H)/4(M), display_name S2-DATA H/M และ count2;
query ประวัติคืน H active6, M active6, left has_left=true6 — **PASS**
IDs เป็นผลฐานรอบนี้เท่านั้น ไม่ hardcode ใน query/automation

### DB60-A01 — ขอบเขต Party และ membership จริง (automated DB integration)

Precondition: fixtures เดียวกันใน Django PostgreSQL test DB
Steps: อ่านทุก Partyด้วย shared helper+count; ตรวจ Pending/Rejected/Approved-left มีจริง;
เพิ่ม X เป็นสมาชิกอีก Party แล้วอ่าน Open ซ้ำ
Expected: ทุก Partyเริ่มH/M2คน; Xเพิ่มเฉพาะอีกPartyเป็น3, Openยัง2
Actual: id sets/count ตรงทั้งหมด — **PASS**

### DB60-A02 — ไม่มี Profile และป้องกัน N+1 (automated DB integration)

Steps: ลบ Profile ของ M ใน test DB แล้วเพิ่มสมาชิก5คนพร้อม Profile;
อ่าน membership+user+profile ทุกคนภายใต้ assertNumQueries(1); นับแยกอีกหนึ่ง query
Expected: 7 rowsรวมMที่ไม่มีProfile; profileของMเป็นNone; list1query/count1query
Actual: 7 rows, Mยังอยู่, Hมีชื่อเดิม, query counts1/1 — **PASS**
ไม่ได้อ้าง throughput/latency บนข้อมูล production

### DB60-A03 — อ่านไม่แก้ประวัติ (automated DB integration)

Steps: snapshot ทุก field ทุก row ของ Membership/JoinRequest/UserProfile;
อ่าน list+count แล้วเทียบ snapshot หลังอ่าน
Expected: ทุก field/จำนวนเท่าเดิม และ left_at ของคนถอนตัวยังอยู่
Actual: snapshots เท่ากัน และ history ยังอยู่ — **PASS**

### DB60-A04 — soft leave ไม่ลบ history/ไม่นับซ้ำ (automated DB integration)

Steps: ตั้ง left_at ของ M ใน test DB ซ้ำ2ครั้ง; อ่าน list/count แต่ละครั้ง
Expected: เหลือH1คนทั้งสองรอบ; membership pk/joined_at และ Approved request ของMยังอยู่
Actual: count1/listH ทุกครั้ง ประวัติตรงเดิม — **PASS**
นี่เป็นการตรวจ query กับ state ใน DB ไม่ใช่การรับรอง POST leave/Task75

### DB60-A05 — legacy Host ไม่ active/ไม่มีสมาชิก (automated DB integration)

Steps: ตั้ง Host left_at แล้วอ่าน; จากนั้นทำ Partyว่างเฉพาะ test DB แล้วอ่านอีกครั้ง
Expected: คืนM1คนในรอบแรก และempty/count0เมื่อไม่มี rows; ไม่สร้าง Host หรือแก้ left_at
Actual: ได้1และ0ตามลำดับ ประวัติ Host ยังอยู่ก่อนล้าง fixture ใน test — **PASS**
ใช้เปิดเผยขอบเขต DB query; กติกา fallback ของ APIต้องตรวจแยกตามหมายเหตุ PR#123

### DB60-A06 — regression ตัวนับ Party เดิม (automated HTTP integration)

Steps: ใช้ university-session test helper เดิมกับHost แล้ว GET Party Detail และ Party List
Expected: member_count เท่ากับ shared count=2 และ remaining_slots=capacity−2
Actual: responses200 และค่าตรง — **PASS**
เป็น Django test client กับ DBจริง ไม่ใช่ unit/mock หรือ manual HTTP acceptance ของ Members API

### DB60-A07 — SQL oracle เทียบ helper เมื่อ Profile หาย (automated DB integration)

Steps: ลบ Profile ของMเฉพาะtestDB, executeไฟล์SQLจริงผ่านcursor;
เทียบ user_ids รายPartyและcountกับsharedhelper
Expected:12rowsทั้งชุด, count2ทุกแถว, Mไม่หายและSQL fallbackเป็นผู้ใช้
Actual: IDs/count/fallback ตรงทุกParty — **PASS**

## คำสั่ง automated และขอบเขตที่ยังไม่รัน

```bash
docker compose run --rm -T backend python backend/manage.py test parties.test_active_memberships --noinput --verbosity 2
```

7 tests ใหม่ผ่านบน PostgreSQL; tests ใช้ test DB ที่ Djangoสร้าง/ลบเอง ไม่มีการแก้ข้อมูลจริง
Manual SQL แยกจาก automated results ข้างต้น ไม่ใช้จำนวน tests แทนวิธี/ผลรายเคส
Not run: manual UI/UAT, Members API #123 ที่ยังไม่รวมในmain,
API permission/fields/pagination และ Task66 end-to-end acceptance
การเปลี่ยนนี้เป็น read query ไม่มี writer/transactionใหม่ จึงไม่อ้างผล concurrent writer/race

ผลตรวจเพิ่มเติมรอบส่งมอบ: Django check และ migrations check ผ่าน (ไม่มี migration ใหม่),
Ruff lint/format ผ่าน, tests ทั้งโปรเจกต์ 343 tests ผ่านบน PostgreSQL (27.409 วินาที)
Smoke ผ่าน HTTP, PostgreSQL readiness, Django template และ static CSS
รอบแรก bind พอร์ต8000ไม่ได้เพราะมีบริการใช้อยู่ จึงรันด้วย `APP_PORT=18060`
เฉพาะ process คำสั่งทดสอบ ไม่เปลี่ยน `.env` หรือหยุดบริการเจ้าของพอร์ต8000
