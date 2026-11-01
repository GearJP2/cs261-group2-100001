# Seeds

Sprint 2 Task46 ใช้ `seed_sprint2 --confirm-test-data` แยก namespace จาก BASE-03
ดู [วิธีรันบนฐานแยก, fixture dictionary, SQL และผล Expected/Actual](../../docs/s2-data-01-fixtures.md).
SQL อยู่ที่ `sprint2_snapshot.sql` (อ่านอย่างเดียว) และ `sprint2_rehearsal.sql` (transaction แล้ว rollback บนฐานทดสอบ)

BASE-03-01 ใช้ Django management command `seed_demo` สร้างข้อมูลสมมติบน schema ปัจจุบันของทีม ไม่สร้าง migration หรือ endpoint ใหม่

BASE-01 ยังไม่สร้างบัญชีนักศึกษาหรือ Party จำลองให้อัตโนมัติ หากต้องเข้าหน้า admin ให้สร้างบัญชี local ด้วย `make superuser` ข้อมูลสำหรับ UAT ต้องระบุว่าเป็นตัวอย่างและห้ามใช้ credentials มหาวิทยาลัยจริงใน repository

## วิธีรัน

ใช้ฐานพัฒนาในเครื่องและ `DEBUG=true` ตาม `.env.example`:

```bash
make init
make up
make migrate
make seed
```

ถ้าไม่มี Make ใช้ `docker compose up --build -d --wait` และ `docker compose run --rm -T backend python backend/manage.py migrate` แทน `make up`/`make migrate` ไม่ต้องสร้าง migrations ใหม่

คำสั่งพิมพ์ Party ID ของแต่ละสถานการณ์เพื่อใช้กับ `/api/v1/parties/{id}` ไม่ hardcode ID เพราะฐานของแต่ละคนมีข้อมูลเดิมต่างกัน

## ผู้ใช้ตัวอย่าง

| Username | บทบาท |
| --- | --- |
| `base03_h` | Host ทุก Party ในชุด |
| `base03_a` | ผู้ขอ A (Pending) |
| `base03_b` | ผู้ขอ B (Rejected ใน Open / Pending ใน Last slot) |
| `base03_m` | สมาชิกที่อนุมัติแล้ว |
| `base03_x` | คนนอก ไม่มี membership/request และไม่มีกีฬาที่สนใจ |
| `base03_inactive` | บัญชี inactive |

ทุกคนมี profile, `credit_score=null`; H/A/B/M สนใจกีฬา `[BASE-03] Badminton` ส่วน X/inactive ไม่มีกีฬาที่สนใจ ไม่มีสิทธิ์ staff/superuser ไม่มี UniversityIdentity และรหัสผ่านเป็น unusable password จึง login ด้วย password ไม่ได้ ชุดนี้ไม่ใช่หลักฐานการยืนยันนักศึกษาจริง การทดสอบ session ใน automated tests ใช้ Django test client `force_login`; การเปิดหน้าเว็บด้วยบัญชีตัวอย่างต้องใช้วิธี dev login ที่ทีมรับรองแยกต่างหาก ไม่มีการเพิ่มทางลัด login ในงานนี้

## สนามและ Party

ชื่อสนามและ Party ขึ้นต้น `[BASE-03]`:

| สนาม | สถานะ |
| --- | --- |
| Open venue | active เปิดทุกวัน 00:00–23:59:59.999999 เพื่อให้ข้อมูลสถานะ Party ใช้ได้ทุกเวลาที่ seed |
| Closed venue | active แต่ไม่มี opening hours จึงปิดทุกวัน ใช้เป็น input ของกรณีเลือกเวลาที่ใช้ไม่ได้ |
| Inactive venue | inactive แม้มี opening hours; ใช้ทดสอบการเลือกสนามที่ถูกปิดใช้งาน |

| Party | สมาชิก active / capacity | กรณีทดสอบ |
| --- | --- | --- |
| Open | H+M / 4 | A Pending, B Rejected (สำหรับขอใหม่); ยังเหลือ 2 ที่ |
| Last slot | H+M / 3 | A/B Pending พร้อมกัน แต่ยังเหลือ 1 ที่ ใช้ทดสอบอนุมัติแข่งกัน |
| Full | H+M / 2 | เต็ม แม้ยังไม่เริ่ม |
| InProgress | H+M / 4 | เริ่มแล้ว ยังไม่จบ |
| Completed | H+M / 4 | จบแล้ว |
| Cancelled | H+M / 4 | ยกเลิกก่อนเริ่ม |

ทุก Party ใช้ Open venue และมี Host เป็นสมาชิกหนึ่งคน M มี Approved request พร้อมข้อมูลผู้ตัดสิน Pending ไม่ถูกนับเป็นสมาชิก สถานะ Party คำนวณจากเวลา/สมาชิก/การยกเลิก ไม่เพิ่มคอลัมน์ state ใหม่ Closed/Inactive venue ไม่ถูกผูกกับ Party เพื่อไม่สร้างนัดที่ผิดกติกา

เวลาคำนวณใหม่จากเวลารันด้วย `Asia/Bangkok` และบันทึกเป็น aware datetime: Party อนาคตเป็นพรุ่งนี้ 10:00–11:00, Completed เป็นเมื่อวาน 10:00–11:00, InProgress เป็นวันนี้ตั้งแต่เที่ยงคืนถึงสิ้นวัน จึงควรรันใหม่ก่อนเริ่มทดสอบแต่ละรอบ ไม่มีการเก็บ Indoor/Outdoor เพราะ schema ปัจจุบันยังไม่มี `venue_type`

## การรันซ้ำ

คำสั่งทำงานใน transaction เดียว ใช้ username/ชื่อกีฬา/ชื่อสนาม/ชื่อ Party ที่สงวนให้ชุดนี้ค้นหาแถวเดิม รักษา User/Party ID เดิม ไม่ใช้ `flush` และไม่แก้ข้อมูลนอกชุด

**การรันซ้ำรีเซ็ตการทดลองบน Party ตัวอย่างทั้ง 6**: ลบ memberships/requests ของ Party เหล่านี้แล้วสร้างสถานการณ์ตั้งต้นใหม่ รวมทั้งรีเซ็ตตารางเวลาเปิดสนามตัวอย่าง รหัสผ่านผู้ใช้ตัวอย่างจะกลับเป็น unusable การเปลี่ยน membership/request ด้วยมือจึงไม่ถูกเก็บไว้ ข้อมูลที่อ้างแถว membership/request/opening hour ไม่ควรผูกกับ ID ของ seed เพราะ ID ย่อยเปลี่ยนได้

คำสั่งปฏิเสธเมื่อ `DEBUG=false` หรือพบ username/ชื่อสนาม/Party ชนข้อมูลที่ไม่มี marker ของชุดนี้ ใช้ชื่อที่สงวน `[BASE-03]`/`base03_*` สำหรับ command เท่านั้น การตรวจ DEBUG ไม่ใช่การตรวจ hostname ของฐานข้อมูล จึงต้องตรวจว่า `.env` ชี้ฐาน local ก่อนรัน

## ตรวจสอบ

```bash
docker compose run --rm -T backend python backend/manage.py test core.test_seed_demo --noinput --verbosity 2
make verify
```

Tests ตรวจสถานการณ์ เวลา จำนวนที่ว่าง Pending ไม่กินที่ รันซ้ำ/คืนสถานการณ์เดิม การไม่แตะข้อมูลนอกชุด การชนชื่อและ rollback รวมถึงการปฏิเสธเมื่อไม่ใช่ development settings การมีข้อมูลพร้อมไม่ได้ยืนยันว่า API อนุมัติ/ถอนตัวหรือ concurrency ทำงานแล้ว ต้องทดสอบใน Story เจ้าของฟีเจอร์ต่อ

### ผลตรวจรอบ 16 ต.ค. 2026

- Ruff lint และ formatting: ผ่าน (`backend` และ `scripts`)
- Tests ใหม่ `core.test_seed_demo`: ผ่าน 6 tests บน SQLite in-memory โดย override DATABASES เฉพาะ process ทดสอบ, Django 5.2.18 / Python 3.11 ของเครื่อง; ไม่แตะฐานพัฒนาและไม่เปลี่ยน settings ของโปรเจกต์
- ใช้ migrations จริงสร้างฐานทดสอบ และตรวจอ่านข้อมูลผ่าน Party detail API เดิมแล้ว
- หลังเปิด Docker ใหม่: ตรวจ Django system check, migrations --check --dry-run, Ruff lint/format และ tests ทั้งหมด 46 ข้อผ่านบน PostgreSQL 17 / Python 3.12 (คำสั่งเทียบเท่า `make verify`)
- Apply migrations บนฐาน local ว่างและรัน `seed_demo` สองรอบสำเร็จ; ทั้งสองรอบใช้ Party ID 1–6 เดิม ไม่เพิ่ม Party ซ้ำ
- เครื่องนี้พอร์ต 5433 มีบริการใช้อยู่ จึงตั้ง `POSTGRES_HOST_PORT=55433` ใน `.env` local เท่านั้น; ภายใน Docker ยังเชื่อม `database:5432` ตามเดิม
