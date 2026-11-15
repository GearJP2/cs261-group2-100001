# Task95 — จำนวนรีวิว ค่าเฉลี่ย unique และ rollback

วันที่ตรวจ: 14 พฤศจิกายน 2026 (Asia/Bangkok) · Owner Gold (`gold555555`) · คู่ช่วย Austin (`Siestashi`)

- [Issue #110](https://github.com/GearJP2/cs261-group2-100001/issues/110), `S2-US14-T-DB`, US14 AC1–3ตามการ์ด
- Branch `test/s2-us14-db-evidence`; base main `86f2ca26c5f0b3c81973039d17552f95f4edb51c`
- ใช้ [Review C1–C6](us14-d-01-decisions.md) และ [มติ No-show 13 พ.ย.](us14-no-show-approved-policy.md). ไม่เปลี่ยนสูตรหรือเปิดflag
- Task87 [PR162](https://github.com/GearJP2/cs261-group2-100001/pull/162) ยังOPENขณะเริ่ม. Task95จึงbranchจากmain ไม่ดึงquery/testที่ยังไม่mergeมาเป็นdependency. Reviewmodel/service/migrationsที่ใช้มีบนmainอยู่แล้ว

## 1. Scope และสิ่งส่งมอบ

ตรวจIT-US14-DB-01..03ของการ์ด: duplicateconcurrentreviewนับครั้งเดียว, failureไม่ทิ้งReview/cacheครึ่งทาง, fixtureหลายคะแนนได้summaryตรงแถวจริงและไม่แก้credit/history

ใช้testsเดิม73ตัวต่อ, เพิ่ม4integrationtestsพร้อมrawSQL/response, ปรับracehelperเดิมให้จับPIDจากrequestconnectionจริง/pg_blocking_pidsและเก็บbefore/after. เพิ่ม [SQL snapshot](../database/seeds/us14_review_test_snapshot.sql) ต่อrevieweeที่รวมsummaryกับreviewrowsในstatementเดียว และ [psql seed wrapper](../database/seeds/us14_review_seed_snapshot.sql) สำหรับmanualfixtureเท่านั้น. ไม่แก้productionAPI/service/schema/dependency

SQLaggregateก่อนjoinreviewrows ไม่เอาจำนวนแถวผลลัพธ์มาบวกcountซ้ำ; summaryซ้ำทุกแถวเป็นค่าเดียวอ่านจากแถวแรก. actual_averageเป็นnumericไม่ปัดเศษ ส่วนAPIround2ตามโค้ดเดิม; cachecompareใช้sum/countไม่ใช่ค่าที่ปัด. credit_eventscountอ่านsubqueryแยกไม่ทำให้reviewfanout

## 2. Environment / ข้อมูล / วิธีแยกประเภท

ผู้ช่วยรันตามคำขอโกลบนMOCKfixtures: Compose `s2-task95`, DB `s2_task95_review`, testDB `test_s2_task95_review`, hostport15495/APP_PORT18095. Python3.12.15/Django5.2.18/PostgreSQL17.11. ไม่เปิดwebserver/TU API ไม่เก็บcookie/CSRF/sessiontokenในหลักฐาน

- **Automated API/DB integration:** Django test client(enforce_csrf_checks=True) → view/guard/service/ORM/PostgreSQLจริง. ไม่ใช่externalnetworkHTTPหรือhumanManualAPI/UI/UAT
- **Race:** TransactionTestCase/คนละconnection; coordinatorถือPartylock; barrierปล่อยworkerพร้อมกัน; observerเห็นpg_blocking_pidsก่อนปล่อยlock. APIrequestอาจreconnectจึงจับPIDในexecute_wrapperก่อนFORUPDATEจริง ไม่ใช้PIDก่อนrequestแทน
- **Manual service + psql:** ผู้ช่วยรันshellscriptที่เรียกserviceจริงและassertผลบนseedDB แล้วสั่งpsqlอ่านก่อน/หลังข้ามconnection. ไม่ใช่การกดAPIจากBrowser; duplicate_status409ในmanual-service.logคือPartyError.statusไม่ใช่HTTPresponse
- **Fault injection:** กรณีหนึ่งสร้างDatabaseErrorหลังUPDATEจริง; อีกกรณีinjectrating_count=-1จนPostgreSQLCHECKปฏิเสธจริง23514. แยกชนิดerrorชัด ไม่อ้างทั้งคู่เป็นconstraintfailure

Preconditionautomated: CompletedParty, Host/M/Peerมีmembership/profile, Review0/cache0; testcaseแยกข้อมูล. Caseหลายคะแนนตั้งcredit95เพื่อพิสูจน์ไม่เปลี่ยน ส่วนrace/rollbackใช้creditNULLและledger0. Manualใช้seed_sprint2CompletedParty/HostH/MemberM/cache0; แยกจากtestDBอัตโนมัติ

## 3. Test cases / Steps / Expected–Actual

| ID / Checklist / source | ขั้นตอน | Expected | Actual / Evidence |
| --- | --- | --- | --- |
| DB95-01 / IT-01 / duplicateAPI | POSTreview4สำเร็จ→SQLsnapshot→POSTTripleเดิมซ้ำ→SQL | 201แล้ว409REVIEW_EXISTS; reviewID/time/sum/count/creditเดิม ไม่เพิ่มแถว | PASS; `test_duplicate_api_leaves_review_id_timestamp_cache_and_credit_unchanged`, JSONLก่อน/หลังเท่ากัน |
| DB95-02 / IT-01 / duplicateRace | Host2workersPOSTreviewM4คู่เดียวPartyเดียว ถือPartylockไว้จนobserverเห็นworkerทั้ง2รอแล้วปล่อย | 201+409REVIEW_EXISTS; หนึ่งReview/cache4,count1/creditเดิม | PASS; `test_same_review_submitted_concurrently_is_stored_once`, rawPID126/125 blockerchain125→126→124(observer)ในtargetedรอบนี้ |
| DB95-03 / IT-01,03 / distinctRace | Host5และPeer2POSTให้Mพร้อมกันและobserverรอlockจริง | 201ทั้งคู่; cache/actualsum7,count2, avg3.5; ไม่มีlostupdate | PASS; `test_different_reviewers_do_not_lose_rating_cache_updates`, JSONLมี2responses/SQL |
| DB95-04 / IT-02 / afterBothWrites | SQLก่อน→POSTreview4→INSERTreviewจริง→UPDATEcacheจริงเป็น4/1→injectDatabaseError→SQLหลัง | HTTP500ไม่ส่งsuccess; rollbackReviewและcache; SQLbefore=after | PASS; `test_api_failure_after_both_writes_rolls_back_review_and_cache`, observedinsert1/cache4,1ก่อนfailure และหลังกลับ0/ไม่มีReview |
| DB95-05 / IT-02 / actualConstraint | SQLก่อน→POSTreview→INSERTจริง→injectcachecount=-1 | PostgreSQL23514 `user_profile_rating_count_gte_0`; API500; rollbackReviewที่INSERTแล้ว/cacheเหมือนก่อน | PASS; `test_actual_cache_constraint_violation_rolls_back_inserted_review`, JSONLsqlstate/constraint/insert_seen1 |
| DB95-06 / IT-03 / multiValues | SQLก่อน→Host5/Peer4/อีกPartyHost4→SQLหลัง→GETreviews | actual/cachesum13,count3; APIaverage4.33,total3; ratings5,4,4; credit95/ledger0และประวัติmembershipเดิม | PASS; `test_multiple_ratings_match_raw_rows_summary_and_credit_history`, response201ทั้ง3/summary4.33/SQLก่อนหลัง |
| DB95-07 / regression | rerunReviewsubmit/list/constraints/eligibility/history/deletionและraceเดิมรวมboundaryends_atหลังlock | ไม่regress; ไม่ยึดผลจากTask87แทนการรันใหม่ | PASS; targeted77testsเต็มในrawlog (4ใหม่+73เดิม) ไม่มีskipped |
| DB95-M01 / manualbaseline | migrate+seed→psqlwrapperอ่านMemberM | actual/cache0/averageNULL/noReview/creditNULL/ledger0 | PASS; manual-before.log |
| DB95-M02 / manualservice | shellscriptguardDBname+DEBUG→submit_reviewH→M5CompletedParty→ตรวจcache→submitซ้ำจับPartyError→psqlอ่านอีกconnection | oneReview5/cache5,count1,duplicateREVIEW_EXISTS/status409,creditNULLเดิม; psqlเห็นcommitเดียวกัน | PASS; manual-service.log/manual-after.log. เป็นservicecallไม่ใช่HTTP |
| DB95-G01 / guard | รันpsqlwrapperบนDBpostgresในprojectแยก | ปฏิเสธก่อนอ่านfixture/exit3 | PASS; sql-guard.log |

Targeted **77 tests ผ่าน ไม่มีskipped** ใน7.195s. หลักฐานใหม่6observationsคือ4testsใหม่+2racecases; caseboundaryเดิมผ่านแต่ไม่เพิ่มrawJSONแยก. แถวSQLผลลัพธ์หลายแถวไม่ใช่จำนวนเคส; ใช้case/testชื่อเต็มในการtrace

Fullverification **612discovered =611ผ่าน+1skipped** ใน54.308s. SkippedคือUS14unitplaceholderเดิม `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` ไม่ใช่Task95; policyมีมติแล้วแต่placeholderยังskip จึงไม่อ้างว่าเคสนั้นผ่านหรือpolicyยังไม่มี. Django check/migrationdry-run/Ruffผ่านทั้งหมด. ไม่รันmake smokeเพราะไม่แก้runtime/หน้าเว็บ

## 4. วิธีรันซ้ำ

ต้องมีDocker/.envlocalพร้อมใช้ จากrepoPowerShell ใช้DBชื่อเฉพาะงานไม่ชี้ฐานใช้งานจริง:

```powershell
$env:POSTGRES_DB='s2_task95_review'
$env:POSTGRES_HOST_PORT='15495'
$env:APP_PORT='18095'
docker compose -p s2-task95 up -d --wait database
docker compose -p s2-task95 run --rm -T -e POSTGRES_DB=s2_task95_review backend python backend/manage.py test conduct.test_review_database conduct.test_reviews_concurrency conduct.test_reviews conduct.test_review_list --noinput --verbosity 2
docker compose -p s2-task95 run --rm -T -e POSTGRES_DB=s2_task95_review backend sh -c 'python backend/manage.py migrate --noinput && python backend/manage.py seed_sprint2 --confirm-test-data'
docker cp database/seeds/us14_review_test_snapshot.sql s2-task95-database-1:/tmp/us14_review_test_snapshot.sql
docker cp database/seeds/us14_review_seed_snapshot.sql s2-task95-database-1:/tmp/us14_review_seed_snapshot.sql
docker compose -p s2-task95 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/us14_review_seed_snapshot.sql'
$task95Manual=Get-Content docs/evidence/task95/manual-service.py -Raw
docker compose -p s2-task95 run --rm -T -e POSTGRES_DB=s2_task95_review backend python backend/manage.py shell -c $task95Manual
docker compose -p s2-task95 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/us14_review_seed_snapshot.sql'
# Negative guard, expected psql exit3:
docker compose -p s2-task95 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d postgres -f /tmp/us14_review_seed_snapshot.sql'
docker compose -p s2-task95 run --rm -T -e POSTGRES_DB=s2_task95_review backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'
docker compose -p s2-task95 down
```

Manualscriptตรวจfreshzeroก่อนเขียนและguardDEBUG/DBprefix; ถ้ารันซ้ำหลังcommitต้องresetเฉพาะsyntheticfixturesบนdisposableDBก่อน หรือใช้DBใหม่ ไม่ลบReview/ซ่อมcacheบนข้อมูลจริง. Scriptเป็นsourceหลักฐานที่รันจริง ไม่ใช่ฟังก์ชันproduction

## 5. หลักฐาน / bug-retest / ข้อจำกัด

- [Test sourceใหม่](../backend/conduct/test_review_database.py) / [Race sourceที่ปรับ](../backend/conduct/test_reviews_concurrency.py)
- [Targeted77tests](evidence/task95/targeted-tests.log) / [SQL+responses+PIDs6observations](evidence/task95/observations.jsonl)
- [Setup/runtime](evidence/task95/setup.log) / [PostgreSQLversion](evidence/task95/runtime.log)
- [psqlก่อน](evidence/task95/manual-before.log) / [Manualservicescript](evidence/task95/manual-service.py) / [ผลservice](evidence/task95/manual-service.log) / [psqlหลัง](evidence/task95/manual-after.log) / [Guard](evidence/task95/sql-guard.log)
- [Fullverification](evidence/task95/verification.log) / [Commit/environment/sourcehashes](evidence/task95/source-manifest.json)

ไม่พบproductionbugจากเคสที่รัน จึงไม่มีproductionfix/retestของbugใหม่. ปรับtestharnessเพื่อบังคับ/สังเกตcontentionและrecordหลักฐาน ไม่เปลี่ยนendpoint/logic. ไม่อ้างloadtest/productionbenchmarkหรือhumanUI/UATจากชุดนี้. ไม่ปิดTask94ManualAPI/Task93UIแทน และไม่เปลี่ยนfeatureflagNo-show. ReviewของGearและการmergeยังรอจริงก่อนComplete ไม่ติ๊กpeerreviewแทนทีม
