# S2-US14-D-01 — มติและข้อเสนอของ US14 (รีวิว ดาว และ No-show)

> **ปรับสถานะอ้างอิง 14 พ.ย. 2026:** เนื้อหาวันที่2พ.ย.ด้านล่างเป็นบันทึกตามเวลานั้น. สำหรับNo-show P-1–P-9 ให้ใช้ [มติGearวันที่13พ.ย.](us14-no-show-approved-policy.md) ซึ่งแทนข้อเสนอเก่าแล้ว; flagยังปิดโดยdefaultและการเปิดใช้งานเป็นdeploymentdecisionแยก. สถานะbranch/Blockedในตารางเก่าไม่ใช่สถานะGitHubปัจจุบัน ดู [Task44 matrix](sprint-2-planning-contract.md) และIssue/PRจริง ไม่อ้างว่าNo-showยังไม่มีpolicyจากบันทึกเก่า

วันที่บันทึก: 2 พฤศจิกายน 2026 (Asia/Bangkok)
Task: [Issue #100](https://github.com/GearJP2/cs261-group2-100001/issues/100)
คนหลัก: Austin; คู่ช่วย: P (ตามหัว Issue)

เอกสารนี้แยกสองเรื่องออกจากกัน: **มติที่ยืนยันแล้ว** (หัวข้อ 1) ใช้เป็นกติกาของรีวิวและดาวได้ ส่วน **ข้อเสนอ** (หัวข้อ 2) เป็นเรื่อง No-show และ conduct credit ที่ยังไม่มีมติ ตัวเลขในโค้ดเป็นเพียงค่าร่างหลัง feature flag ห้ามอ้างว่าทีมอนุมัติแล้ว

- **ที่มาของมติ:** สรุปตามที่ Austin ระบุในงานนี้เมื่อ 2 พ.ย. 2026 ยังไม่ได้แนบบันทึกการประชุม และยังรอคู่ช่วย review ตาม checklist ของ #100
- **ที่มาของข้อเท็จจริงเรื่องโค้ด:** อ่านจาก branch ด้วย `git show` ไม่ได้รันโค้ดหรือ tests ในงานเอกสารนี้

## งานที่เกี่ยวข้อง

| งาน | Issue | Branch | Commit | สถานะ ณ วันที่บันทึก |
| --- | --- | --- | --- | --- |
| S2-US14-B-01 ส่งรีวิว | [#103](https://github.com/GearJP2/cs261-group2-100001/issues/103) | `feat/s2-us14-b-01-submit-review` | `2ebb7d8` | ยังไม่ merge |
| S2-US14-B-02 อ่านรีวิวและ summary | [#104](https://github.com/GearJP2/cs261-group2-100001/issues/104) | `feat/s2-us14-b-02-read-reviews` | `ab5072d` | ยังไม่ merge |
| S2-US14-B-03 No-show และ credit | [#105](https://github.com/GearJP2/cs261-group2-100001/issues/105) | `feat/s2-us14-b-03-no-show` | `e1fde1f` | ยังไม่ merge; flag ปิดเป็นค่าเริ่มต้น |
| S2-US14-T-API ทดสอบ API | [#109](https://github.com/GearJP2/cs261-group2-100001/issues/109) | `test/s2-us14-t-api-unit-and-manual` | ยังไม่ commit | ยังไม่ merge; เคส No-show เป็น Blocked |

Branch ทั้งสามของ Backend ซ้อนกันตามลำดับ B-01 → B-02 → B-03 และยังไม่ได้ push จึงยังไม่มีเลข PR ให้อ้าง เอกสารนี้จึงอ้างเลข Issue แทน

## 1. มติที่ยืนยันแล้ว

| # | เรื่อง | มติ | งาน |
| --- | --- | --- | --- |
| C-1 | ขอบเขต | US14 ครอบคลุมรีวิวและการรายงาน No-show; ดาวเฉลี่ยกับ conduct credit เป็นคนละค่า ไม่คำนวณจากกัน (การนำ No-show เข้า Sprint 2 ยังเป็นข้อเสนอ P-1) | #100, #103, #104 |
| C-2 | สิทธิ์รีวิว | กิจกรรมต้องเป็น `Completed` และไม่ถูกยกเลิก; ผู้รีวิวและผู้ถูกรีวิวต้องเป็น Host หรือสมาชิกที่ `left_at IS NULL` หรือ `left_at >= ends_at`; ห้ามรีวิวตัวเอง | #103, #109 |
| C-3 | ข้อมูลรีวิว | `rating` เป็นจำนวนเต็ม 1–5; `comment` บังคับกรอก ไม่เกิน 500 ตัวอักษร | #103, #109 |
| C-4 | ความซ้ำ | หนึ่งรีวิวต่อผู้รีวิว + ผู้ถูกรีวิว ต่อหนึ่ง Party; Sprint 2 ไม่มีการแก้ไขหรือลบรีวิว | #103, #109 |
| C-5 | ความเป็นส่วนตัว | ผู้ใช้ที่ login แล้วอ่านรีวิวของผู้ใช้คนใดก็ได้; ฟิลด์สาธารณะคือ `display_name` ของผู้รีวิว, `rating`, `comment`, `created_at`; read API ห้ามส่ง email, รหัสนักศึกษา, reviewer ID หรือ party ID | #104, #109 |
| C-6 | ค่าเฉลี่ยดาว | `rating_sum / rating_count` จาก cache บน `UserProfile`; ส่ง `null` เมื่อ `rating_count = 0` ไม่ใช่ 0 | #104, #109 |

### รายละเอียดที่โค้ดใช้ตามมติ

- **C-2:** Host มีสิทธิ์แม้ไม่มีแถว `PartyMembership`; สถานะ `Cancelled` มาก่อน `Completed` ใน `get_party_state` จึงได้ `PARTY_NOT_COMPLETED` แม้เลยเวลาจบแล้ว
- **C-3:** API ตัดช่องว่างหัวท้ายก่อนนับและก่อนบันทึก และปฏิเสธ `true`, `"5"`, `5.0`, ข้อความมี NUL และ lone surrogate; **ฐานข้อมูลไม่บังคับ `comment`** (`blank=True`) การบังคับกรอกและความยาวอยู่ที่ API เท่านั้น
- **C-4:** บังคับด้วย unique constraint `unique_party_review` ไม่ได้ตรวจก่อน insert อย่างเดียว; method อื่นได้ 405
- **C-5:** ผู้อ่านต้องผ่าน university guard ไม่ใช่แค่มี session; ผู้รีวิวที่ไม่มีโปรไฟล์แสดงเป็น `ผู้ใช้` ไม่ใช้ login แทนชื่อ
- **C-6:** ปัดเศษ 2 ตำแหน่ง (5, 4, 4 → 4.33)

## 2. ข้อเสนอ — รอทีมยืนยัน

**ทุกข้อในหัวข้อนี้ยังไม่ใช่มติ** ค่าในโค้ดอยู่ที่ `backend/conduct/policy.py` บน branch B-03 และหลัง `NO_SHOW_ENABLED=false` เจ้าของที่ระบุคือคนตอบคำถามให้ได้ข้อสรุป ไม่ใช่ผู้อนุมัติแทนทีม

| # | สถานะ | เรื่อง | ค่าในร่าง | คำถามที่ต้องตอบ | เจ้าของ | งาน |
| --- | --- | --- | --- | --- | --- | --- |
| P-1 | **ข้อเสนอ** | No-show อยู่ Sprint 2 หรือ backlog | ทำโค้ดไว้หลัง flag ที่ปิดอยู่ | เอาเข้า Sprint 2 หรือไม่ และถ้าเป็น backlog จะ merge B-03 พร้อม flag ปิด หรือพักทั้ง branch | Austin + P, ทีม | #100, #105 |
| P-2 | **ข้อเสนอ** | เกณฑ์ผู้รายงาน | N = ผู้เข้าร่วมที่ไม่รวมผู้ถูกรายงาน; `N == 1` → 1 คน มิฉะนั้น `max(2, N // 2 + 1)` | ยอมรับฐานนับนี้แทน "มากกว่าครึ่งของสมาชิก active" ในสัญญาหรือไม่ และยอมให้คนเดียวตัดสินเมื่อ N = 1 หรือไม่ | Austin + P, ทีม | #100, #105 |
| P-3 | **ข้อเสนอ** | จำนวนที่หัก | −5 ครั้งเดียวต่อคนต่อ Party | ใช้ −5 หรือไม่ (ส่วน "ครั้งเดียว" ตรงกับ D-15 ในสัญญาอยู่แล้ว) | Austin + P, ทีม | #100, #105 |
| P-4 | **ข้อเสนอ** | ค่าเริ่มต้นเครดิต | 100 เมื่อ `credit_score` เป็น NULL ตอนหักครั้งแรก | **ขัดกับ D-6 และกฎข้อ 13:** ผลคือ 95 แต่ผลรวม ledger คือ −5 จะยอมรับยอดที่ไม่เท่าผลรวม ledger, บันทึก event ตั้งต้น หรือเลือกวิธีอื่น | Austin + P, เจ้าของสัญญา (โกล, กอล์ฟ) | #100, #105 |
| P-5 | **ข้อเสนอ** | ช่วงเวลารายงาน | 7 วันหลัง `ends_at` (ครบ 7 วันพอดียังรายงานได้) | ใช้ 7 วันหรือไม่ | Austin + P, ทีม | #100, #105 |
| P-6 | **ข้อเสนอ** | การแสดง `credit_score` บนโปรไฟล์สาธารณะ | ซ่อนหรือหน่วงการแสดงผล เพราะผู้รายงานอาจรู้ว่ารายงานของตนทำให้ถูกหักหรือไม่ | จะซ่อน หน่วง หรือยอมรับ **ตอนนี้โค้ดยังไม่ซ่อน** ดูหัวข้อ 3.5 | Austin + P, เจ้าของ US8 | #100, #105 |
| P-7 | **ข้อเสนอ** | ขอบล่างของ `credit_score` | ไม่มี ค่าติดลบได้ | ต้องมีขอบล่างหรือไม่ | Austin + P, ทีม | #100, #105 |
| P-8 | **ข้อเสนอ** | การอุทธรณ์ | ไม่มีใน Sprint 2 | ยอมรับว่าไม่มีช่องทางแก้เมื่อถูกรายงานผิดหรือไม่ (enum `AppealReversal`, `AdminAdjustment` มีอยู่ แต่ไม่มี API ใช้) | Austin + P, ทีม | #100, #105 |
| P-9 | **ข้อเสนอ** | การสะกด `kind` ใน ledger | โค้ดเก็บ `NoShowDeduction` | สัญญาหัวข้อ 2.6 เขียน `NO_SHOW_DEDUCTION` แต่หัวข้อ 3.7 และ database-by-story เขียน `NoShowDeduction` จะยึดแบบใด (คอลัมน์ยาว 15 ตัวอักษร `NO_SHOW_DEDUCTION` ยาว 17 จึงต้องมี migration ถ้าเปลี่ยน) | Austin + P, เจ้าของสัญญา (โกล, กอล์ฟ) | #100, #105 |

### หมายเหตุประกอบข้อเสนอ

**P-1:** #105 ระบุว่างานนี้ Blocked และห้าม implement สูตรสมมติจนกว่าทีมอนุมัติ แต่ branch B-03 มีโค้ดตามค่าร่างแล้วโดยปิด flag ไว้ ทีมต้องตัดสินว่าแนวทางนี้เข้ากับเงื่อนไขของ #105 หรือไม่ และ flag ปิดเฉพาะ endpoint: ถ้า merge B-03 ตาราง `NoShowReport` และ `ConductCreditEvent` จะถูกสร้างด้วย

**P-2:** เมื่อ N ≥ 2 ค่า `N // 2 + 1` มีค่าอย่างน้อย 2 เสมอ `max(2, ...)` จึงไม่เปลี่ยนผล สูตรนี้เท่ากับ "มากกว่าครึ่งของ N" จุดต่างจากสัญญาคือ **ฐานนับ** ไม่ใช่สูตร

| Party มีผู้เข้าร่วม (รวมผู้ถูกรายงาน) | N | ผู้รายงานที่ต้องการตามร่าง | มากกว่าครึ่งโดยนับผู้ถูกรายงานด้วย |
| --- | --- | --- | --- |
| 2 | 1 | 1 | 2 |
| 3 | 2 | 2 | 2 |
| 4 | 3 | 2 | 3 |
| 5 | 4 | 3 | 3 |
| 6 | 5 | 3 | 4 |

ฐานนับในร่างยังใช้กติกาเดียวกับ C-2 จึงนับ Host และสมาชิกที่ออกตั้งแต่ `ends_at` เป็นต้นไปด้วย ส่วน "สมาชิก active" ในสัญญาหมายถึง `left_at IS NULL` ผู้รายงานและผู้ถูกรายงานก็ใช้กติกา C-2 เช่นกัน ซึ่งเป็นส่วนหนึ่งของข้อเสนอนี้

## 3. ข้อเท็จจริงจาก implementation ที่ทีมควรรู้

### 3.1 Endpoints

Path ใช้ prefix `/api/v1` ทุก endpoint ใช้ university guard, ผู้กระทำมาจาก session และ POST ต้องมี CSRF

| Endpoint | Body / Query | สำเร็จ | งาน |
| --- | --- | --- | --- |
| `POST /parties/{id}/reviews` | `reviewee_id`, `rating`, `comment` | 201 `data.review`: `id`, `party_id`, `reviewer` (`id`, `display_name`), `reviewee_id`, `rating`, `comment`, `created_at` | #103 |
| `GET /users/{id}/reviews` | `page` (ค่าเริ่มต้น 1), `page_size` (ค่าเริ่มต้น 20, สูงสุด 100) | 200 `data`: `user_id`, `average_rating`, `rating_count`, `reviews`, `page`, `page_size`, `total`; เรียงใหม่สุดก่อน | #104 |
| `POST /parties/{id}/no-show-reports` | `reported_id` | 201 `data.report`: `id`, `party_id`, `reported_id`, `created_at` — ไม่บอกว่าเกิดการหักเครดิตหรือไม่ | #105 |

### 3.2 Error codes

| Endpoint | HTTP | Code | กรณี |
| --- | --- | --- | --- |
| ทุก endpoint | 401 | `AUTH_REQUIRED` | ไม่มี session |
| ทุก endpoint | 403 | `ACCOUNT_INACTIVE` | บัญชีถูกระงับ |
| ทุก endpoint | 403 | `FORBIDDEN` | session ไม่มีหลักฐานมหาวิทยาลัย |
| POST ทั้งสอง | 403 | `CSRF_FAILED` | token หายหรือผิด |
| ทุก endpoint | 405 | `METHOD_NOT_ALLOWED` | method ไม่รองรับ |
| POST ทั้งสอง | 400 | `INVALID_INPUT` | content type, JSON หรือฟิลด์ไม่ถูกต้อง รวมฟิลด์เกิน, ตัวเอง, ผู้ใช้เป้าหมายไม่ใช่ผู้เข้าร่วมหรือไม่มีโปรไฟล์ |
| POST ทั้งสอง | 403 | `FORBIDDEN` | ผู้ส่งไม่ใช่ผู้เข้าร่วม |
| POST ทั้งสอง | 404 | `NOT_FOUND` | ไม่พบ Party |
| POST ทั้งสอง | 409 | `PARTY_NOT_COMPLETED` | กิจกรรมยังไม่จบหรือถูกยกเลิก |
| POST reviews | 409 | `REVIEW_EXISTS` | รีวิวคู่นี้ใน Party นี้แล้ว |
| POST no-show-reports | 409 | `REPORT_WINDOW_CLOSED` | เลยช่วงรายงาน (ค่าตาม P-5) |
| POST no-show-reports | 409 | `REPORT_EXISTS` | รายงานคู่นี้ใน Party นี้แล้ว |
| POST no-show-reports | 404 | `NOT_FOUND` | flag ปิด |
| GET reviews | 400 | `INVALID_INPUT` | `page` หรือ `page_size` ผิด หรือส่งซ้ำ |
| GET reviews | 404 | `NOT_FOUND` | ไม่พบผู้ใช้หรือผู้ใช้ไม่มีโปรไฟล์ |

ลำดับตรวจของ service หลัง lock Party: สถานะ Party → (No-show เท่านั้น) ช่วงรายงาน → ผู้ส่งเป็นผู้เข้าร่วม → ไม่ใช่ตัวเอง → ผู้ใช้เป้าหมายเป็นผู้เข้าร่วม

### 3.3 จุดที่ response ไม่เหมือนกัน

- **POST รีวิวส่ง `party_id` และ `reviewer.id` แต่ GET ไม่ส่ง** ข้อห้ามใน C-5 ใช้กับ read API ส่วน POST ตอบกลับเฉพาะผู้ส่งเอง
- **GET ส่ง `id` ของรีวิวด้วย** ซึ่งไม่อยู่ในรายการฟิลด์สาธารณะของ C-5 ค่านี้เป็นเลขของแถวรีวิว ไม่ใช่ตัวระบุบุคคลหรือ Party
- **Pagination ของ GET อยู่ใน `data`** รับ `page`/`page_size` ตามแบบ venues แต่ venues ส่ง `page`, `page_size`, `total` ไว้ระดับบนตามสัญญาหัวข้อ 6 ส่วน endpoint นี้ส่งไว้ใน `data` เพราะมี summary ร่วมด้วย Frontend ต้องอ่านจาก `data`

### 3.4 พฤติกรรมที่โค้ดเลือกไว้แต่ไม่ได้ระบุในมติ

- ไม่มีเส้นตายของรีวิว: รีวิวได้เสมอหลังกิจกรรมจบ
- ผู้ใช้ที่ไม่มีโปรไฟล์ **ถูกรีวิวไม่ได้** (ไม่มี cache ให้นับ จึงตอบ `INVALID_INPUT` และ rollback) แต่ **รีวิวคนอื่นได้**
- ข้อความ error ของผู้ใช้เป้าหมายใช้ข้อความเดียวกันทุกสาเหตุ เพื่อไม่บอกว่าบัญชีนั้นมีอยู่จริงหรือไม่
- รีวิวของบัญชี inactive ที่มีโปรไฟล์ยังอ่านได้ เหมือน API โปรไฟล์

### 3.5 ข้อขัดกันที่ต้องรู้ก่อนเปิด flag

`submit_no_show_report` ไม่บอกผู้รายงานว่าเกิดการหักหรือไม่ แต่ `credit_score` ยังแสดงทันทีทั้งใน API โปรไฟล์สาธารณะ (`backend/accounts/views.py`) และหน้าโปรไฟล์ (`backend/core/views.py`) ผู้รายงานจึงเปรียบเทียบค่าก่อนและหลังรายงานได้ ถ้าเปิด flag โดยยังไม่ตัดสิน P-6 ข้อมูลนี้จะรั่ว

### 3.6 Feature flag

`NO_SHOW_ENABLED` ค่าเริ่มต้นเป็น false (`backend/config/settings.py`, `.env.example` บน branch B-03) เมื่อปิด endpoint ตอบ 404 `NOT_FOUND` ก่อนตรวจ login, parse body หรือ query ฐานข้อมูล ยกเว้น POST ที่ไม่มี CSRF ซึ่ง middleware ตอบ 403 `CSRF_FAILED` ก่อนถึง view

### 3.7 Migrations และแอป

| Migration | เนื้อหา | อยู่ตั้งแต่ branch |
| --- | --- | --- |
| `accounts/0005_userprofile_rating_cache` | `UserProfile.rating_sum`, `rating_count` และ check ห้ามติดลบ (`accounts/0004` ถูกใช้โดย `0004_reject_blank_display_name` แล้ว) | B-01 |
| `conduct/0001_initial` | `PartyReview` | B-01 |
| `conduct/0002_noshowreport_conductcreditevent` | `NoShowReport`, `ConductCreditEvent` | B-03 |

โค้ดสร้างแอปใหม่ชื่อ `conduct` ตามที่สัญญาแนะนำ แต่ Q-13 ในสัญญายังมีสถานะรอโกลและกอล์ฟ จึงยังต้องให้เจ้าของปิดข้อนี้

## 4. เอกสารที่ยังไม่ได้แก้ในงานนี้

| เอกสาร | จุดที่ไม่ตรงกับเอกสารนี้ |
| --- | --- |
| [user-stories.md](user-stories.md) US14 Scenario 1 | เขียนว่า "คำนวณค่าเฉลี่ยเครดิตใหม่" ขัดกับ C-1 ที่แยกดาวกับเครดิต |
| [database-by-story.md](database-by-story.md) หัวข้อ 7 | ยังเขียนชื่อไฟล์ `accounts/0004_profile_rating.py` |
| [s2-data-01-fixtures.md](s2-data-01-fixtures.md) แถว US14 | ยังเขียนว่าไม่มี Review model และ #100 รอยืนยัน policy |

## 5. เอกสารที่อ้างอิง

- [BASE-02 Schema Contract](base-02-schema-contract.md) หัวข้อ 2.6, 3.7, 4.2, 6, 8, D-6, Q-9 และ Q-13
- [Sequence ของ US14](sprint-2-sequences/README.md#us14--รีวิวหลังจบ)
- [Database แยกตาม Story](database-by-story.md)
