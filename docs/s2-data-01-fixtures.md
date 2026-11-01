# S2-DATA-01 — fixtures และ SQL สำหรับ Sprint 2

Task46 / [Issue #61](https://github.com/GearJP2/cs261-group2-100001/issues/61) /
[Trello](https://trello.com/c/KlWzL5mK). ใช้ schema ของ main ที่ `dfbb8d8` เป็นฐาน
ไม่มี migration, endpoint, dependency หรือการเปลี่ยนกติกา Party ในงานนี้

## Scope และ dependency

ใช้ command `seed_sprint2` reuse กลไก transaction/collision/reset ของ `seed_demo`
แต่แยก namespace `[S2-DATA]` / `s2data_*` จึงไม่รีเซ็ตชุด BASE-03 ของเพื่อน
สร้างข้อมูล MOCK ทั้งหมด ไม่มีข้อมูลสนามจริง นักศึกษาจริง UniversityIdentity หรือ dev-login bypass
ผู้ใช้มี unusable passwords จึงใช้เข้าหน้าเว็บด้วย password ไม่ได้
การทดสอบ HTTP/session ให้ใช้ test helper เดิมในชุด automated หรือบัญชีทดสอบที่ทีมอนุมัติ
ห้ามอ้างว่าการ seed ผ่านเท่ากับ UAT/API ผ่าน

| Story / Task ที่ใช้ต่อ | ข้อมูลที่เตรียม | ส่วนที่ยังรอ |
| --- | --- | --- |
| US10 / Task49,57 | Pending สองคนแย่งหนึ่งที่, Approved/Rejected, Full/เริ่ม/ยกเลิก | ทดสอบ API และ race จริงอยู่ใน Task เจ้าของ |
| US6 / Task60,66 | Host, active member, left history, outsider | สิทธิ์/response ของ API ตาม contract ทีม |
| US4 / Task69,75 | membership ที่มี `left_at` และ Approved history ยังอยู่ | กฎ Host ถอนตัว/เวลาตัดสิทธิ์ ต้องยืนยันก่อน implement |
| US2 / Task78,84 | สองกีฬา สองสนามที่ใช้จัด Party และขอบเวลาแน่นอน | schema main ไม่มี indoor/outdoor (`venue_type`); ไม่ปลอม field ด้วยชื่อสนาม |
| US14 / Task87,95 | Completed + ประวัติร่วมกิจกรรมสำหรับใช้ต่อ | ไม่มี Review model และ #100 ยังรอยืนยัน policy; ไม่สร้าง rating/no-show/สูตรเครดิตแทนทีม |

ส่วนที่รอคือข้อจำกัดของ fixture รอบนี้ ไม่ใช่ผล Pass ของฟีเจอร์นั้น ๆ
เมื่อตกลง schema/policy แล้วต้องเพิ่ม fixture และ expected results ของส่วนนั้นต่อ

## ฐานทดสอบแยกและคำสั่งรัน (PowerShell)

รันจาก root repository หลังสร้าง `.env` และเปิด Docker ใช้ฐานใหม่ชื่อ
`s2_data01_check` เฉพาะงานนี้ ไม่เปลี่ยน `.env` และไม่ใช้ `flush`/ลบ volume ของทีม
ตรวจว่า environment ชี้ PostgreSQL local ก่อนรัน; DEBUG อย่างเดียวไม่ได้ตรวจ hostname
หากฐานชื่อนี้มีอยู่แล้ว ให้ใช้ฐานทดสอบของรอบเดิมโดยไม่รัน `createdb` ซ้ำ

```powershell
docker compose up -d --wait database
$taskDbUser = docker compose exec -T database printenv POSTGRES_USER
docker compose exec -T database createdb -U $taskDbUser s2_data01_check
docker compose run --rm -T -e POSTGRES_DB=s2_data01_check backend python backend/manage.py migrate --noinput
docker compose run --rm -T -e POSTGRES_DB=s2_data01_check backend python backend/manage.py seed_sprint2 --confirm-test-data --at 2026-11-02T15:00:00+07:00
```

`--confirm-test-data` ต้องระบุทุกครั้งและ `DEBUG=true` จึงรันได้
`--at` รับ ISO datetime ที่มี timezone เพื่อให้ทุกคนใช้ reference เดียวกัน;
ละ `--at` เพื่อสร้างสถานการณ์อิงเวลารันจริงก่อนทดสอบ
สถานะเปลี่ยนตามเวลาจริง จึงต้องเทียบกับ reference ที่ระบุ ไม่ใช้ fixture เก่ามาสรุปผลวันนี้
แสดงผล SQL เป็นเวลา Bangkok ส่วน PostgreSQL เก็บ aware datetime

การรันซ้ำรักษา User/Party/Venue IDs และจำนวนข้อมูลเดิม แต่รีเซ็ต membership/request/opening hours
ของชุด S2 รวมถึงสิ่งที่ลองทำกับ Party ชุดนี้ไว้ ดังนั้นเก็บหลักฐานก่อนรันซ้ำ
IDs ย่อยของ membership/request ไม่คงเดิม ให้ค้นด้วย username/title/marker
คำสั่งปฏิเสธเมื่อชน username/venue/party ที่ไม่ใช่ marker เจ้าของและ rollback ทั้งชุด
ชื่อกีฬา `[S2-DATA] Badminton/Tennis` เป็นชื่อสงวนของ fixture

## Data dictionary และ expected baseline

ผู้ใช้ 7 คน: `s2data_h` Host, `s2data_m` สมาชิก active,
`s2data_a` ผู้ขอ A, `s2data_b` ผู้ขอ B, `s2data_left` เคยเป็นสมาชิกแล้วถอน,
`s2data_x` outsider, `s2data_inactive` inactive
ทุกคนมี profile และ `credit_score=null`; ไม่มี staff/superuser

ทุก Party มี active H+M = 2 คน และ left history = 1 คน
Approved request = 2 แถว (M กับ left) จึงห้ามนับจำนวน Approved เป็น active count

| Party | capacity | active | left | ที่ว่าง | Pending | Approved | Rejected |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Open | 4 | 2 | 1 | 2 | 1 (A) | 2 | 1 (B) |
| Last slot | 3 | 2 | 1 | 1 | 2 (A,B) | 2 | 0 |
| Full | 2 | 2 | 1 | 0 | 0 | 2 | 0 |
| InProgress | 4 | 2 | 1 | 2 | 0 | 2 | 0 |
| Completed | 4 | 2 | 1 | 2 | 0 | 2 | 0 |
| Cancelled | 4 | 2 | 1 | 2 | 0 | 2 | 0 |

Last slot ใช้ Tennis/Alternate venue; อีก 5 Party ใช้ Badminton/Open venue
สนาม Open และ Alternate เปิดทุกวัน 00:00–23:59:59.999999;
Closed ไม่มี opening hours; Inactive มีชั่วโมงแต่ `is_active=false`
รวม 2 กีฬา 4 สนาม 6 Party; Closed/Inactive ไม่ผูก Party เพื่อไม่สร้างนัดที่ผิดกติกา
สำหรับ `--at` ตัวอย่าง: อนาคต 3 พ.ย. 10:00–11:00 Bangkok,
Completed 1 พ.ย. 10:00–11:00, InProgress วันที่ 2 พ.ย. ทั้งวัน,
Cancelled มี `cancelled_at` เท่ากับ reference

## SQL ตรวจด้วยตัวเอง

```powershell
docker compose cp database/seeds database:/tmp/s2-data01-sql
docker compose exec -T database psql -X -U $taskDbUser -d s2_data01_check -f /tmp/s2-data01-sql/sprint2_snapshot.sql
docker compose exec -T database psql -X -U $taskDbUser -d s2_data01_check -f /tmp/s2-data01-sql/sprint2_rehearsal.sql
```

snapshot เป็น SELECT อย่างเดียว ใช้ marker+host จำกัดเฉพาะ S2;
ใช้ `COUNT(DISTINCT ...)` ป้องกันจำนวนบวมจาก join memberships × requests
rehearsal ใช้ BEGIN → Approved+membership → snapshot → ROLLBACK → snapshot
บนฐานทดสอบเท่านั้น โดยตรวจ baseline ก่อนเขียนและหยุดเมื่อผิดคาด
นี่เป็นการทดลองข้อมูล/SQL ไม่ใช่การเรียก API และไม่ใช่ race test ของสอง connection
ถ้ารันผิดกลางทาง psql หยุดและ connection ปิดทำให้ transaction ยังไม่ commit ถูก rollback

## ผลตรวจ 2 พ.ย. 2026

Environment: Docker Compose, Python 3.12, Django ใน image ทีม, PostgreSQL 17;
base commit `dfbb8d8`, branch `chore/s2-data-01-fixtures-sql`.
ไฟล์ command/SQL/test/report ส่งใน commit เดียวของ PR; ดู exact SHA ใน PR เพื่อทำซ้ำ

| TC | Precondition / วิธีทดสอบ | Expected | Actual / ผล |
| --- | --- | --- | --- |
| DATA-01 | ฐาน `s2_data01_check` ใหม่ migrate แล้ว; seed ด้วย reference ข้างต้น | 7 users/2 sports/4 venues/6 parties; counts ตามตาราง | ตรงทุกแถวจาก psql snapshot — Pass |
| DATA-02 | รัน seed ซ้ำด้วย reference เดิม | Party IDs 1–6 เดิม จำนวนและ baseline ไม่เปลี่ยน | IDs 1–6 และ SQL counts เดิมทั้งสองรอบ — Pass |
| DATA-03 | รัน rehearsal หลัง reset; ดู Last slot ทั้งสามช่วง | active/remaining/pending: ก่อน 2/1/2 → ระหว่าง 3/0/1 → หลัง rollback 2/1/2 | psql ออกค่าตรงทั้งสามช่วง — Pass |
| DATA-04 | automated สร้าง BASE-03 แล้ว seed S2 สองรอบและเปลี่ยน interaction ระหว่างรอบ | BASE-03 IDs เดิม; S2 reset ได้ ไม่มีข้อมูลเพิ่มซ้ำ | ผ่าน test บน PostgreSQL — Pass |
| DATA-05 | automated ชน Alternate venue ที่ไม่ใช่ marker หลังเริ่มสร้างชุด | ข้อผิดพลาดและไม่เหลือ user/party ที่สร้างบางส่วน | ผ่าน collision rollback test — Pass |
| DATA-06 | automated ไม่มี confirmation / naive หรือ invalid `--at` / DEBUG=false | ปฏิเสธก่อนสร้าง fixture | ผ่าน — Pass |
| DATA-07 | automated เวลาเริ่ม−1µs / เริ่มพอดี / จบพอดี | Open / InProgress / Completed | ผ่าน shared state helper — Pass |
| DATA-08 | execute ไฟล์ SQL snapshot จริงใน Django PostgreSQL test DB | 6 rows, active=2/left=1 ไม่ถูก join คูณ | ผ่าน — Pass |
| DATA-09 | กด UI หรือส่ง HTTP approve/leave/review จริง | ต้องทดสอบตาม task UI/API เจ้าของ Story | Not run ในงานนี้ |
| DATA-10 | indoor/outdoor / Review+No-show fixture | ต้องมี schema/policy ที่ทีมอนุมัติก่อน | Blocked ตาม dependency ด้านบน |

Automated checks (แยกจาก manual SQL DATA-01..03):

```bash
docker compose run --rm -T backend python backend/manage.py test core.test_seed_demo core.test_seed_sprint2 --noinput --verbosity 2
```

13 tests ผ่านบน PostgreSQL รวม 6 regression tests ของ BASE-03 และ 7 tests ใหม่
ตรวจเทียบเท่า `make verify` แล้ว: Django check / migrations check / Ruff lint+format ผ่าน
และ tests ทั้งโปรเจกต์ 312 tests ผ่านบน PostgreSQL (19.826 วินาที)
รายงานนี้ไม่อ้างว่าผ่าน UAT, endpoint ใหม่, concurrent approvals หรือครบทุก Story
ผล review/CI ให้ดู PR จริง ไม่ติ๊กแทนผู้รีวิว
