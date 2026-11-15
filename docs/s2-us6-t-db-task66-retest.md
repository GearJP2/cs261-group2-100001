# Task66 retest — ปิด Host count failure และ real leave dependency

วันที่ตรวจ: 14 พฤศจิกายน 2026 (Asia/Bangkok) · Owner Gold (`gold555555`) · ผู้ตรวจที่ขอ GearJP2

งาน [#81](https://github.com/GearJP2/cs261-group2-100001/issues/81) / S2-US6-T-DB / IT-US6-DB-01..03
Branch `test/s2-us6-db-retest`; base main `86f2ca26c5f0b3c81973039d17552f95f4edb51c`

**ผลรับงานทางเทคนิค: PASS ครบขอบเขตที่เคยค้าง**. ส่งreview/mergeก่อนComplete; ไม่ติ๊กpeerreviewแทนผู้ตรวจ. Issue81เคยปิดจากPR133ทั้งที่reviewระบุยังไม่ผ่านacceptance จึงreopenติดตามretest และให้PRรอบนี้ปิดหลังmergeจริง

## 1. ที่มา / สิ่งที่แก้ / ขอบเขต

[รอบเดิม](s2-us6-t-db-task66.md) มีmain7skipped, preview6PASS/1FAIL: DB66-BUG-01นับHostที่ไม่มีactive rowเกินSQL และDB66-DEP-02ยังไม่มีleaveendpoint. PR133reviewGearบอกชัดว่ายังใช้ปิดTask66ไม่ได้

ปัจจุบันMembersPR123และLeavePR158mergeแล้ว. Mainใช้actualactive rowsและHostยังมีสิทธิ์อ่านโดยไม่สังเคราะห์แถวในresponse. ไม่แก้productionAPI/serviceของเพื่อน

- ถอดroute-dependent `skipUnless` และข้อความเก่าว่าmainไม่มีMembers. หากrouteหายให้testFAIL ไม่skipซ่อนregression
- เปิดCSRFchecksจริงในautomatedtestsเดิม และเพิ่มA08POSTleave/ซ้ำ/ประวัติ/สิทธิ์หลังถอน, A09Hostไม่มีmembershiprow
- ปรับ `scripts/us6-db-api-evidence.py` ให้ทำM09ผ่านHTTPleaveจริง2ครั้งด้วยsessionของM ไม่ใช้Hostถอนแทน แล้วHostอ่านMembersเทียบSQL/Detail. เก็บrequest/response/history/เวลาและsourcefingerprints ไม่มีauthheadersในหลักฐาน
- เปลี่ยนHTTProuteหายเป็นFAILตามcontractที่mergeแล้ว; ไม่ใส่M09Blockedแบบhardcodedอีก
- เก็บrawหลักฐานรอบเก่าไว้ ไม่เขียนทับผลFAIL/Blockedย้อนหลัง

## 2. Environment / วิธีทดสอบ

ผู้ช่วยรันตามคำขอโกลบนMOCKfixturesเท่านั้น. Python3.12.15/Django5.2.18/PostgreSQL17.11. Compose `s2-task66-retest`, DB `s2_task66_retest`, testDB `test_s2_task66_retest`, hostDB15466. HTTPserverชื่อ `s2-task66-retest-http`, socket8000ภายในcontainer ไม่มีhostportหรือTUlogin

1. Automated: Django test client+CSRF/sessionfixtures+PostgreSQLจริง, targeted36tests (Task66เดิม7+ใหม่2 และMembers27), **36ผ่าน/no skipped** (3.125s)
2. Assistant-operated **real network HTTP**: urllibส่งHTTPsocketไปDjangorunserverloopback127.0.0.1:8000; serverอ่านDBเดียวกับSQLoracle. Client()ในscriptใช้สร้างsyntheticverifiedsessionเท่านั้น ไม่ใช้ตอบdomainHTTPrequests. อ่านSQLจากไฟล์แยก ไม่ใช้helperของAPIคำนวณExpected
3. psqlอ่านactive/historyหลังrehearsalอีกครั้ง ยืนยันแถวที่leftยังอยู่

ไม่ใช่humanUI/UATหรือTUauthenticationจริง. ScriptsจำกัดDEBUG/DBprefixs2_task66_/HTTPloopbackก่อนseedและแก้เฉพาะsyntheticfixtures. HTTPscriptจะresetfixturesในDBแยก ไม่รันกับข้อมูลจริง

## 3. Cases / Expected–Actual / bug-retest trace

Precondition: seed_sprint2มี6Party ทุกPartyHostH+Mactive2/left-history1; A/Bเป็นPending/Rejectedตามscenario; ไม่มีrequestกินที่ก่อนapprove. แต่ละautomatedtestใช้fixtureแยก. HTTPrehearsalเป็นflowต่อเนื่องและระบุcountตามลำดับจริง

| Case / IT | ขั้นตอน | Expected | Actual / หลักฐาน |
| --- | --- | --- | --- |
| A01/M01×6 / IT01 | SELECTactiveSQL→GETmembers→GETdetailทั้ง6Party | IDs/count/roleเฉพาะleft_atNULL; active2ไม่รวมPending/Rejected/left | PASSทุกParty; responseและSQLในhttp-sql.json; automatedตรวจroleด้วย |
| A02/M03–04 / IT02 | HostPOSTapproveA→SQL/API→approveซ้ำ | ครั้งแรก200/Approved/count2→3; ซ้ำ409/count3 | PASS |
| A03/M05 / IT01 | HostrejectBในLastslot | 200/Rejected/no membership/count2เดิม | PASS |
| A04/M06×2 / IT03 | SQLเตรียมleft_atซ้ำแล้วอ่านAPI/Detail/history | pk/joined_at/requestApprovedยังเดิม; countไม่ลดเพิ่ม | PASS; ยังระบุว่าSQLstatepreparation ไม่อ้างแทนHTTPleave |
| A05/M07 / IT01 | profileสมาชิกactiveหาย/เพิ่มXอีกParty | activeIDยังแสดงfallback; ไม่ปนสมาชิกอีกParty | PASS |
| A06/M02 | GETMembers/Detail→เทียบfieldsก่อน/หลัง | membership/request/profileไม่mutate | PASS |
| A07/M08 / BUG-01 retest | ตั้งHost.left_atในfixturelegacy→SELECTSQL→GETmembers/detailด้วยHost | Hostมีสิทธิ์อ่านแต่ไม่สร้างHostrow/countเพิ่ม; SQL=API=Detail | **PASS**: HTTPSQLIDs=[2], count1/APIcount1/Detailcount1; ก่อนเคยAPIcount2 |
| A08/M09×2 / DEP-02 / IT02,03 | ใช้sessionM+CSRF→POSTleave{}→HostSQL/Members/Detail→Mmembers→POSTleaveซ้ำ | 200ทั้งคู่/left_atเดียว/IDjoined_atrequestcapacityเดิม; Mmembers403; countลดครั้งเดียว | **PASS**: HTTPflowหลังapproveAมี3คน→2→2; Mmembers403ทั้ง2. Automatedfixtureเริ่ม2คน→1→1 ไม่ใช่fixtureเดียวกัน |
| A09 / BUG-01เพิ่ม | ลบHostmembershiprowในfixture→GETด้วยHostเทียบSQL | ไม่สังเคราะห์Hostในรายการ; count1ตรงSQL/Detail | PASS |

HTTPscriptมี **16case records ผ่านทั้งหมด**, 42HTTPrequests; M01ซ้ำ6Party, M06/M09ซ้ำ2attempt จึงไม่ใช่16caseIDsไม่ซ้ำ. ไม่มีFAIL/Blockedในreportรอบนี้. คำขอCSRF/sessiontokenเก็บในmemoryไม่ลงJSON; source_sha256ผูกไฟล์ที่รันกับหลักฐาน

Fullverification: **610discovered=609ผ่าน+1skipped** (52.530s). Skippedเป็นUS14unitplaceholderเดิมไม่ใช่Task66; Task66ไม่มีskipแล้ว. Django check/migrationdry-run/Ruffผ่านทั้งหมด. ไม่รันmake smokeเพราะไม่แก้runtime/UI; realHTTPrehearsalตรงscopeถูกเก็บแยกด้านบน

## 4. หลักฐาน

- [Targeted36tests/ชื่อและผลจริง](evidence/task66/retest/targeted-tests.log)
- [RealHTTP+SQL JSON16records](evidence/task66/retest/http-sql.json): requests42ครั้ง, payload/status/body, SQLIDs/count, historyก่อน/หลัง, source/runtime/timestamps
- [psqlactiveหลังflow](evidence/task66/retest/active-sql.log) / [psqlhistoryที่ยังเก็บ](evidence/task66/retest/history-sql.log)
- [Serverstartup/HTTPrequestlog](evidence/task66/retest/server.log) / [Fullverification](evidence/task66/retest/verification.log)
- [Source/commit/environmentmanifest](evidence/task66/retest/source-manifest.json)
- Sources: [automatedtests](../backend/parties/test_members_database.py), [HTTPscript](../scripts/us6-db-api-evidence.py), [SQLoracle](../database/seeds/us6_active_members.sql)

## 5. ทำซ้ำ (PowerShell จากrepo)

เตรียม.env/Dockerlocal, ใช้DBแยก. Serverไม่publishhostport จึงไม่ชนlocalhostของผู้ใช้. ตั้งcontainernameด้านล่างให้ไม่ชนงานอื่นถ้ารันพร้อมกัน

```powershell
$env:POSTGRES_DB='s2_task66_retest'
$env:POSTGRES_HOST_PORT='15466'
$env:APP_PORT='18066'
docker compose -p s2-task66-retest up -d --wait database
docker compose -p s2-task66-retest run --rm -T -e POSTGRES_DB=s2_task66_retest backend python backend/manage.py test parties.test_members_database parties.test_members --noinput --verbosity 2
docker compose -p s2-task66-retest run -d --name s2-task66-retest-http --no-deps -e POSTGRES_DB=s2_task66_retest backend sh -c 'python backend/manage.py migrate --noinput && exec python backend/manage.py runserver 0.0.0.0:8000 --noreload'
# รอhealthready200ก่อนรันscript; หากยังไม่readyตรวจdockerlogsไม่ตีความว่าtestผ่าน
docker exec s2-task66-retest-http python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready/',timeout=5).status)"
$task66Source=git rev-parse HEAD
docker exec -e "US6_EVIDENCE_SOURCE=$task66Source" s2-task66-retest-http python scripts/us6-db-api-evidence.py > task66-retest-http.json
# exit0 = allcasePASS; exit1 = มีFAIL/BLOCKEDหรือscriptขัดข้อง ต้องเปิดJSONตรวจ
docker compose -p s2-task66-retest run --rm -T -e POSTGRES_DB=s2_task66_retest backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'
docker rm -f s2-task66-retest-http
docker compose -p s2-task66-retest down
```

เก็บrawJSON/errorcodesตามจริง ไม่ใช้HTTPleaveผ่านไปอนุมานUIยืนยัน/Canceldialogผ่าน. Task66เป็นreadconsistency/historytest ไม่ใช่capacityraceของUS4/US10; testsraceแยกTask75/57 ไม่ใช้แทนกัน. Retestนี้ยืนยันBUG-01และDEP-01/02ปิดทางเทคนิคบนbaseที่ตรวจ ไม่เปลี่ยนผลเก่าหรืออ้างผู้ตรวจอนุมัติแล้ว
