# Task45 — Sprint 2 test scope และ case inventory

งาน [#118](https://github.com/GearJP2/cs261-group2-100001/issues/118) / `S2-QA-01` · คนหลัก GearJP2 · คู่ช่วย Gold · จัดทำร่วมกับผู้ช่วยวันที่ **15 พฤศจิกายน 2026**
Baseline main: `b6b4dc36d85f37e1cd2f2caae63b6b1c36dbe9b9` (รวม Search PR #132). สถานะ: เอกสาร Design ส่ง review; ทุก execution ในแผนนี้เริ่ม **Not run** ไม่รับรองผลทดสอบหรืออนุมัติแทนคู่ช่วย

## สิ่งส่งมอบและวิธีใช้

1. [Coverage matrix: 24 PLAN AC → TC IDs → วิธีตรวจ](sprint-2-coverage.md)
2. [Inventory 101 cases (CSV)](sprint-2-cases.csv): UI17, API64, DB17, UNIT3 พร้อม precondition, steps, expected และช่องบันทึก execution
3. [แม่แบบ Test Case / execution / bug-retest](test-case-template.md)

CSV เป็นรูปแบบแก้ไข/กรองได้ใน spreadsheet; อ่าน UTF-8 และรักษา TC IDs ไว้. UI/API/DB/UNIT คือวิธีตรวจ ไม่ใช่ผลรัน. API หมายถึงแผน manual HTTP + SQL ตรวจผลกระทบในเคสที่เขียนข้อมูล; DB หมายถึง SQL integration หรือ automated PostgreSQL race ตามขั้นตอน; UNIT แยก function ด้วย mock ไม่มีฐานข้อมูลจริง. Source เป็น repo-root path เปิดได้จาก [repository](https://github.com/GearJP2/cs261-group2-100001/tree/b6b4dc36d85f37e1cd2f2caae63b6b1c36dbe9b9); ชื่อ method/raw logs ดูแหล่งเดิมต่อ ไม่อ้างว่าเคส inventory ทุกข้อมี automation ครบ

## Scope และ dependency

In scope: US10 Pending/approve/reject/reapply; US6 actual active members/privacy/order/refresh; US4 soft leave/retry/state/lock/history/rejoin; US2 AND/title/time/state/pagination/venue type/UI states; US14 review/cache/privacy/No-show/credit และ boundary/error/permission/race ที่เกี่ยวข้อง. Login, profile, venue เป็น prerequisites และ regression ของ flow ไม่ขยายเป็นการออกแบบใหม่ทั้งหมด

Out of scope: friends/chat/invites, court booking, notifications, production load benchmark, real TU provider acceptance, production deployment, appeal workflow, venue categorization ที่ยังไม่มีผู้ดูแลยืนยัน. Integration ข้าม story ทุกรอบอยู่ #111; demo/retrospective อยู่ #112

ใช้ [Task44 plan](../sprint-2-planning-contract.md) เป็น proposed AC crosswalk: PLAN IDs ไม่ใช่หมายเลข Trello ที่เปลี่ยนแทนทีม. #60 ปิดแล้วและเอกสารเข้า main แต่ checklist มติที่ยังไม่รับรองให้ผู้เกี่ยวข้องยืนยันตาม scope; การ merge เอกสารไม่ทำให้ checklist ทุกข้อผ่านเอง. US2 implementation ตาม PR #132 ใช้ starts-within[from,to), q title-only, default Open และ pagination; ไม่ใช้ params รุ่นเก่า date/time_from/spots/sort กับ API. D07 venue_type nullable: fixture ที่ต้องการ Indoor/Outdoor ต้องจัดค่าชัดเจน ไม่เดาจากชื่อกีฬา/REAL-MOCK

US14 ใช้ [approved policy](../us14-no-show-approved-policy.md): Gear ยืนยันแล้ว; No-show flag ปิด default เป็น deployment decision แยก. ข้อความเก่าในรายงานว่ารอ policy/skip ไม่ใช่สถานะ policy ล่าสุด และไม่แปลง skip เป็น Pass

## Fixtures / preconditions ที่ใช้ร่วมกัน

ทุกครั้งใช้ disposable DB และระบุ commit/environment จริงใน execution ไม่ใช้ข้อมูลผู้ใช้จริง. Reset แยกแต่ละ case/variant ก่อนตรวจ (ยกเว้นเคส retry/rejoin ที่จงใจต่อ flow). ห้ามนำจำนวนจาก fixture ต่างชุดมาเทียบเป็น before/after เดียวกัน

| Fixture | ข้อมูลและ invariant |
|---|---|
| FX-PARTY | H=Host active; M=active member; A/B=applicants Pending/Rejected ตามเคส; L=left; N=verified outsider. Pเริ่มในอนาคต/ไม่cancelled. cap3, active H+M=2, เหลือ1. Qเป็นอีก Party สำหรับ cross-party negative; สร้าง Pending ให้ A/B ใหม่ตามเคส |
| FX-FULL | เช่น FX-PARTY แต่ cap2/active2; A Pending ไม่ใช่สมาชิก. Reject ไม่คืนที่เพราะ A ยังไม่เคยได้ที่ |
| FX-SEARCH | Controlled now N; dates A=2030-11-20T00:00+07:00, B=2030-11-21T00:00+07:00. Party starts A−1us/A/B−1us/B และเริ่มก่อนAแต่จบหลังA. ทุก5states หลายกีฬา หลายสนาม Indoor/Outdoor/NULL, >100rows และ starts_at tie สำหรับ pagination; venue/sport จัดคู่ให้ถูกต้อง |
| FX-REVIEW | Completed P ไม่cancelled, H/M/peer อยู่ถึง ends_at; Lออกก่อนจบ; N outsider. HรีวิวMได้ ไม่ใช่ตนเอง. เพิ่ม Completed Q สำหรับ multi-party. แยก no-review/cache0 และ creditNULL/current95 fixtures. Reporter N ในสูตรหมายถึง eligible count ไม่ใช่ username N |
| FX-AUTH | Anonymous, expired session, verified active university user, unverified local account, inactive user; CSRF valid/missing/wrong/untrusted Origin แยก variant. Inactive session อาจ401จาก ModelBackend; direct inactive guard403 |
| FX-UNIT | SimpleNamespace/mock ตาม unit tests ต้นทาง; no ORM/network; แช่ clock เมื่อเกี่ยวข้อง |

แหล่งเตรียมจริง: [seed_sprint2](../../backend/core/management/commands/seed_sprint2.py), [JoinRequestFixture](../../backend/parties/test_join_requests.py), [ReviewFixture](../../backend/conduct/test_reviews.py). ใช้ role aliases ไม่ hardcode PK; lookup username/marker แล้วบันทึก fixture IDs ที่สร้างจริงใน execution. Automated fixtures ของ Task69/75 มี cap2/active2 ต่างจาก FX-PARTY: ให้ยึด precondition ของ method เมื่อ rerun automation และบันทึกความต่าง ห้ามอ้างเป็น manual case เดียวกันโดยไม่เทียบ steps/expected

สำหรับ manual: ตั้ง Compose project/DBชื่อเฉพาะ, make init/build, migrate แล้วใช้ `seed_sprint2 --confirm-test-data` เฉพาะ DEBUG disposable DB. Seed มี Open/Full/InProgress/Completed/Cancelled แต่ต้องเตรียม boundary/venue_type/large pagination เพิ่มตาม FX-SEARCH. บันทึก reference time ของ seed. Unit/HTTP/DB tests สร้าง test DB ตาม fixture ของตนเอง

## Endpoint / expected oracle

ทุก path ด้านล่างมี prefix `/api/v1`, ไม่มี slash ท้าย. อ่าน identity จาก session ไม่ยอมให้ payload เลือก actor. GET ไม่ต้อง CSRF; unsafe method ต้องผ่าน middleware ก่อน. Guard/CSRF ก่อน domain errors; ทดสอบหลายเงื่อนไขแยก fixture เพื่อไม่คาด error ผิดลำดับ

| Story | Endpoint หลัก | Oracle อิสระ |
|---|---|---|
| US10 | GET parties/P/join-requests/pending; POST parties/P/join-requests/R/decision status Approved/Rejected; POST parties/P/join-requests {} สำหรับขอใหม่ | SQL JoinRequest + Membership; count active ไม่ใช่นับ Pending |
| US6 | GET parties/P/members และ parties/P | [active SQL](../../database/seeds/us6_active_members.sql), [history SQL](../../database/seeds/us6_members_history.sql); Hostมีสิทธิ์แต่ไม่มีrowต้องไม่สังเคราะห์ |
| US4 | POST parties/P/leave empty body/{}; GET parties/P, members | [leave snapshot](../../database/seeds/us4_leave_snapshot.sql); capacity/requests/IDs/joined_atคงเดิม |
| US2 | GET parties?q&sport_id&venue_id&venue_type&starts_from&starts_to&state&page&page_size | raw Party starts/state/count และ [design26cases](../us2-search-test-cases.md); กรองก่อนcount/page |
| US14 | POST parties/P/reviews; GET users/U/reviews และ users/U/profile; POST parties/P/no-show-reports | [review snapshot](../../database/seeds/us14_review_test_snapshot.sql), [cache audit](../../database/seeds/us14_review_cache_audit.sql); ledger event/credit แยกจากดาว |

Controlled clock: Python mock clock สำหรับ tests; manual ให้สร้างกิจกรรมเหมาะสมและบันทึก instant/SQL ไม่ใช้ความรู้สึกว่ากดใกล้เวลาเป็นหลักฐาน exact boundary. Race ต้อง PostgreSQL separate connections + synchronization และ blocker/PID evidence ตาม source tests; ยิงต่อกันหรือ snapshot อย่างเดียวไม่พิสูจน์ race

## Evidence reuse / handoff / gaps

ผลรัน Task56 วันที่ 16 พ.ย. 2026: [US10 API acceptance report](../us10-t-api-test-report.md) — 18 unit tests และ 47 HTTP variants พร้อม SQL; แยก exact-time HTTP/TU login/browser UAT ที่ยัง Not run และไม่เปลี่ยนผล inventory ทั้งแถวจาก variant บางส่วน

| Story | แหล่งเดิมที่ใช้ต่อ | งานรัน/รับรองแยก |
|---|---|---|
| US10 | [Pending design](../us10-pending-api-test-cases.md), [Reject19tests](../us10-b-03-test-report.md), [DB57](../s2-us10-t-db-task57.md) | UI#70, API#71, DB#72; #135 ยังเปิด ณตรวจ ต้องตรวจ head จริงก่อนรันUIรับงาน |
| US6 | [DB66 retest](../s2-us6-t-db-task66-retest.md), backend test_members/unit/database | UI#79, API#80, DB#81; ไม่ใช้HTTPscriptแทนกดUI |
| US4 | [Design API/DB/UI IDs](../us4-leave-party-test-cases.md), [Task70](../us4-b-01-test-report.md), [DB75](../s2-us4-t-db-task75.md) | UI#88, API#89, DB#90; UI confirm/refresh ยังต้องตรวจจริง |
| US2 | [S01–S26 design](../us2-search-test-cases.md), backend test_creation_api (PR132merged) | UI#97, API#98, DB#99; venue classification ต้องเตรียมก่อนรัน |
| US14 | [รายงานเดิม](../us14-t-api-test-report.md), [DB87](../s2-us14-db-task87.md), [DB95](../s2-us14-t-db-task95.md), approved policy | UI#108, API#109, DB#110; flag-onเฉพาะDBทดสอบ; legacy skipped placeholderยังไม่ใช่ผลPass |

QA IDs เป็น alias ของ scope รอบนี้; `existing_case_id` เก็บ Sxx/APIxx/DBxx/UIxx เดิม. ถ้าเคสเดิมหนึ่งแถวมีหลาย variants ให้สร้าง execution suffix เช่น `QA-US2-API-09/a`, `/b` พร้อมผลแยก ห้ามผล variantหนึ่งแทนทุกvariant. เคสใหม่ที่รวม permission/input variants ก็ใช้หลักเดียวกัน

Retest ไม่เขียนทับ raw evidence เดิม. ระบุ case+variant, commit/env, actual, status, tester/time และลิงก์ screenshot/request-response/SQL/log ให้ตามกลับได้. แยก `new run`, `reused evidence` และ `not run`; เมื่อต้องใช้หลักฐานเก่า ให้ระบุ commit/env เก่าและเหตุผลเทียบพฤติกรรมได้ ไม่เปลี่ยนเป็นผลรันใหม่

## ลำดับทำและเกณฑ์รับงาน #118

1. Gear/Gold review AC mapping, cases, fixtures และ scope ก่อนรัน; ข้อแตกต่างกับ contractให้บันทึก ไม่แก้ expected ตาม bug
2. รัน automation/API/DB ที่พร้อมบน main ที่จะตรวจจริง; UI ที่ยังไม่พร้อมรายงาน Blocked พร้อม issue และเหตุผล หลังลอง/ยืนยัน prerequisite แล้ว ไม่ติ๊ก Blockedล่วงหน้าทั้งStory
3. ต่อ flow ข้าม Story ใน #111; สรุป coverage/gaps/demo ใน #112. สถานะใน inventory ไม่ได้เปลี่ยนเมื่อ CIผ่านโดยอัตโนมัติ

- [x] มีครบ5Stories/24PLAN IDs และ inventory101cases
- [x] Precondition/fixtures/steps/expected และ execution fields ครบ
- [x] อ้างเคสและsourceเดิม แยกmanual/automation/SQL/unit
- [ ] Gold/ทีม review และแนบหลักฐานอนุมัติจริงก่อนปิด #118

รอบนี้ตรวจเอกสารเท่านั้น ไม่มีการรันTC/API/UI/SQLใหม่ ไม่มีการเปิดNo-showหรือแก้production. ผลตรวจลิงก์/schema CSV/coverage อยู่ใน PR description; ไม่ใช้ผล runtime จากงานก่อนอ้างเป็นผลใหม่
