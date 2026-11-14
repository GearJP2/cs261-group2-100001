# Task87 — Review schema, uniqueness และ query คะแนนดาว

วันที่ตรวจ: 14 พฤศจิกายน 2026 (Asia/Bangkok) · Owner Gold (`gold555555`) · คู่ช่วย Austin (`Siestashi`)

- [Issue #102](https://github.com/GearJP2/cs261-group2-100001/issues/102) / `S2-US14-DB-01` / US14 AC1–3ตามการ์ด
- Branch `chore/s2-us14-review-db-audit`; base main `86f2ca26c5f0b3c81973039d17552f95f4edb51c`
- Design: [รีวิว C1–C6](us14-d-01-decisions.md) และ [มติNo-showล่าสุด](us14-no-show-approved-policy.md). Task85 #100 และ APIส่งรีวิว #103 ปิดแล้ว; ไม่สมมติสูตรใหม่หรือเปิดfeatureflag

## 1. ตรวจของเดิม / reuse / ส่วนที่เพิ่ม

บนmainมี `conduct.PartyReview`, `accounts.UserProfile.rating_sum/rating_count`, migrations, `submit_review`, `average_rating`, `list_reviews` และtestsแล้ว. จึง **ไม่สร้างmodel/migration/index/serviceซ้ำ** และไม่แก้productionbehavior

| จุด | ของเดิมที่ใช้ | ผลตรวจ/หน้าที่ |
| --- | --- | --- |
| ความสัมพันธ์ | Review→Party/reviewer/reviewee; ORM `on_delete=PROTECT` ทั้ง3FK | ป้องกันORMลบรีวิวแล้วcacheไม่ลด; PostgreSQLFKจริงเป็นdeferredFKตามDjango ไม่อ้างว่าSQLมีPROTECTkeyword |
| Unique | `unique_party_review(party_id,reviewer_id,reviewee_id)` | กันduplicateแม้serviceตรวจพร้อมกัน; คนเดียวรีวิวคนเดิมต่างPartyได้ |
| CHECK | rating1..5, reviewer<>reviewee; profile sum/count>=0 | catalogติดตั้งและvalidatedจริง; commentrequired/max500/Completed/eligibilityเป็นservice/API ไม่ใช่DBCHECK |
| Migration | accounts0005หลัง0004_reject_blank_display_name; conduct0001พึ่งaccounts0005+parties0003; conduct0002สำหรับNo-show/ledger | migrateฐานว่างผ่าน; ไม่มีdriftหรือmigrationใหม่ |
| Transaction | `submit_review` atomic: PartyFORUPDATE → createReview(unique) → ProfileUPDATEด้วยF(sum+rating,count+1) | errorทำให้rollback; missingprofileไม่ทิ้งReview; cacheincrementไม่lostupdate. trustedreviewer/rating/commentต้องผ่านAPIvalidation |
| Readquery | `list_reviews` filterreviewee, count, select_relatedreviewerprofile, order-created_at,-pk, pagination; summaryจากcache | ใช้indexเดิม `(reviewee,created_at)`; คงtie-breakerpk. ไม่เพิ่มindexโดยไม่มีproductionqueryevidence |
| ดาว vs เครดิต | average_ratingอ่านsum/count; ไม่มีรีวิวคืนNone; ไม่เขียนcredit_score | No-show/ledgerแยก; ไม่เอาsumdeltaเครดิตมาเป็นคะแนนดาว |

เพิ่มเครื่องมือตรวจ3ไฟล์SQLและ2integrationtestsเฉพาะเครื่องมือ:

- [Cache audit SQL](../database/seeds/us14_review_cache_audit.sql): aggregateReviewก่อนjoinProfile, FULL OUTER JOINเพื่อเห็นreviewที่profileหาย, แสดงactual_sum/count/average, cached_sum/count, profile_exists, cache_matches, credit_score. **อ่านอย่างเดียวไม่ซ่อมอัตโนมัติ**
- [Schema audit SQL](../database/seeds/us14_review_schema_audit.sql): catalogFK/CHECK/UNIQUEและindexesจริง
- [Guarded SQL rehearsal](../database/seeds/us14_review_rehearsal.sql): syntheticfixture/ชื่อDBเฉพาะงาน; insert+cacheupdate/duplicate/drift/ROLLBACK
- [Tests](../backend/conduct/test_review_cache_audit.py): เรียกserviceเดิมแล้วexecuteauditSQLจริง; ตรวจmultiParty, ไม่เกิดledgerfanout, detectdriftและprofilemissingโดยไม่repair

SQLactual_averageเป็นnumericไม่ปัดเศษ; APIใช้Pythonround(...,2)เดิม. ใช้sum/countสำหรับreconciliation ไม่ใช้ค่าที่ปัดแล้วตัดสินcachematch และไม่อ้างว่าSQLroundกับPythonroundให้ผลเหมือนทุกboundary

## 2. Test scope / environment

ผู้ช่วยรันตามคำขอโกลบน **MOCK local fixtures** เท่านั้น. Python3.12.15/Django5.2.18/PostgreSQL17.11. Compose `s2-task87`, DB `s2_task87_review`, testDB `test_s2_task87_review`, hostDBport15487/APP_PORT18087 (ไม่ได้เปิดwebserver). ไม่มีTU API/cookie/token/รหัสผ่านในหลักฐาน

แยกชัดเจน:

1. Automated integration: 2testsใหม่ใช้ORM/service/SQL/PostgreSQLจริง; rerun73testsเดิมของreviewsubmit/list/constraints/race. Django test clientในtestsเดิมไม่ใช่externalnetworkHTTPหรือhumanManualAPI
2. ManualSQL: ผู้ช่วยสั่งpsqlจริงและอ่านตารางก่อน/หลัง/ROLLBACK; SQLwritesในrehearsalเป็นการจำลองdata ไม่ใช่การเรียกservice/API. Uniqueerrorเป็นPostgreSQL23505จริง
3. ไม่ใช่humanUI/UAT, productionload/EXPLAINbenchmark หรือTask95ส่งมอบครบ. Task95 #110 ยังต้องจัดtestscope/evidenceของตัวเอง โดยreuseของงานนี้ได้

## 3. Cases / ขั้นตอน / Expected–Actual

PreconditionAutomated: ReviewFixtureสร้างHost/M/Peer/Outsiderกับprofile; PartyCompletedและHost/M/Peerเป็นสมาชิก. Testsแยกfixtureและrollback/reset. Manualใช้seed_sprint2CompletedParty/HostH/MemberMและcache0ก่อนทำ

| Case / trace | ขั้นตอน | Expected | Actual / หลักฐาน |
| --- | --- | --- | --- |
| DB87-C01 schema | migrateฐานว่าง → psqlcatalog | FK3/uniqueTriple/CHECKrating+self+profilecacheติดตั้งvalidated, indexreviewee_createdมีจริง | PASS; catalog9constraintsรวมPK/FK/profilechecks และ6indexesรวมauto ใน `schema-audit.log` |
| DB87-Q01 zero | executeauditSQLก่อนreview | ทุกprofileactual_sum/count0, averageNULL, cachematchtrue | PASS; JSONLsql_beforeและmanualbaseline |
| DB87-Q02 aggregate | submit_reviewจริง3ครั้ง: H→M5/Peer→M4/อีกPartyH→M4; executeSQL | count3/sum13/avgประมาณ4.333; API4.33; cacheตรง | PASS; `test_reconcile_multiple_parties_without_ledger_fanout_or_credit_mutation` |
| DB87-Q03 fanout/credit | ตั้งcredit95และledger2แถวเป็นhistoricalfixtureก่อนsubmit3review; SQLไม่joinledger | ยังคงcount3ไม่เป็น6, credit95ไม่เปลี่ยน/ledger2แถวเดิม | PASS; JSONLledger_rows2/SQLcredit95. Ledger/ยอดเครดิตfixtureนี้ตั้งแยกเพื่อทดสอบfanoutเท่านั้น ไม่อ้างว่าเป็นการกระทบยอดNo-show |
| DB87-Q04 drift | serviceสร้างreview5 → จงใจแก้cached_sumเป็น6 → executeaudit | actual_sum5/cached6/cache_matchesfalse; ไม่ซ่อมกลับ | PASS; sourceassertยังcached6หลังaudit |
| DB87-Q05 missingprofile | directORMimportreviewให้userไม่มีprofile (ข้ามserviceguard) → audit | profile_existsfalse/actual_count1/cache_matchesfalse; ไม่สร้างprofileแทน | PASS; JSONL. เป็นจำลองข้อมูลimportผิด ไม่พบว่าปกติserviceเขียนแบบนี้ |
| DB87-S01 manualinsert | seedcache0 → BEGIN/Partylock → insertreview5+cacheupdate → audit | cached/actual5,count1, matchtrue, creditเดิม | PASS; `manual-sql.log` ตารางAFTER_VALID_INSERT |
| DB87-S02 duplicate | insertTripleเดิมอีกครั้งในsubtransaction | actualuniqueviolation23505/unique_party_review; ไม่เพิ่มแถวหรือcache | PASS; PostgreSQLNOTICEระบุconstraintจริงในmanual log |
| DB87-S03 drift/rollback | UPDATEsyntheticcache+1 → audit → ROLLBACK → audit | ระหว่างtransactioncached6/actual5/matchfalse; หลังROLLBACKทุกprofile0/matchtrue | PASS; ตารางINJECTED_DRIFTและAFTER_ROLLBACK |
| DB87-G01 guard | รันrehearsalบนDBชื่อpostgresในprojectแยก | ปฏิเสธก่อนwrite/psqlexit3 | PASS; `sql-guard.log` |
| DB87-R01 reuse | รันtestsเดิมsubmit/list/unique/rating/self/FKdeletion/cachefailure/concurrency | พฤติกรรมเดิมผ่าน ไม่อ้างsourceauditแทนผลรัน | PASS; targeted75testsรวม2ใหม่ ไม่มีskipped |

Test namesของ2ใหม่และSQLactualทุกค่าอยู่ [JSONL](evidence/task87/observations.jsonl). รายชื่อ73testsเดิมเต็มอยู่ [targeted log](evidence/task87/targeted-tests.log) รวม `ReviewDuplicateTests`, `ReviewConstraintTests`, `ReviewConcurrencyTests` และreadsummary/list. Raceเดิมเป็นconnectionจริงแต่Task87ไม่ได้เพิ่มobserverแบบTask57 จึงไม่อ้างว่ามีrawPID/blockerใหม่ของreviewraceในรายงานนี้

ผลTargeted **75ผ่าน ไม่มีskipped** (6.703s). Fullverification **610discovered =609ผ่าน+1skipped** (54.263s): skippedเป็นUS14unitplaceholder `test_no_show_and_credit_formula_blocked_until_policy_is_confirmed` ไม่ใช่Task87audit. Policyปัจจุบันยืนยันแล้วแต่placeholderยังมีskip; ไม่ถือว่าเคสนั้นผ่านหรือpolicyยังไม่มีเพราะข้อความเก่า. Django check/migrationdry-run/Ruffผ่านทั้งหมด; ไม่รันmake smokeเพราะไม่เปลี่ยนruntime/หน้าเว็บ

## 4. คำสั่งทำซ้ำ (PowerShell จากrepo)

ต้องมี`.env` localพร้อมใช้; ใช้ชื่อDBแยกไม่ชี้production. ไม่เผยค่าลับของenv

```powershell
$env:POSTGRES_DB='s2_task87_review'
$env:POSTGRES_HOST_PORT='15487'
$env:APP_PORT='18087'
docker compose -p s2-task87 up -d --wait database
docker compose -p s2-task87 run --rm -T -e POSTGRES_DB=s2_task87_review backend python backend/manage.py test conduct.test_review_cache_audit conduct.test_reviews conduct.test_reviews_concurrency conduct.test_review_list --noinput --verbosity 2
docker compose -p s2-task87 run --rm -T -e POSTGRES_DB=s2_task87_review backend sh -c 'python backend/manage.py migrate --noinput && python backend/manage.py seed_sprint2 --confirm-test-data'
docker cp database/seeds/us14_review_cache_audit.sql s2-task87-database-1:/tmp/us14_review_cache_audit.sql
docker cp database/seeds/us14_review_schema_audit.sql s2-task87-database-1:/tmp/us14_review_schema_audit.sql
docker cp database/seeds/us14_review_rehearsal.sql s2-task87-database-1:/tmp/us14_review_rehearsal.sql
docker compose -p s2-task87 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/us14_review_schema_audit.sql'
docker compose -p s2-task87 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/us14_review_rehearsal.sql'
# Guard check: expected exit3
docker compose -p s2-task87 exec -T database sh -c 'psql -U "$POSTGRES_USER" -d postgres -f /tmp/us14_review_rehearsal.sql'
docker compose -p s2-task87 run --rm -T -e POSTGRES_DB=s2_task87_review backend sh -c 'python backend/manage.py check && python backend/manage.py makemigrations --check --dry-run && ruff check backend scripts && ruff format --check backend scripts && python backend/manage.py test backend --top-level-directory backend --noinput --verbosity 1'
docker compose -p s2-task87 down
```

## 5. หลักฐาน / ความเสี่ยง / งานต่อ

- [Targeted75tests](evidence/task87/targeted-tests.log) / [AuditSQLobservations](evidence/task87/observations.jsonl)
- [Migrate/seed/runtime](evidence/task87/setup.log) / [PostgreSQLversion](evidence/task87/runtime.log)
- [Catalog9constraints/6indexes](evidence/task87/schema-audit.log) / [ManualSQLtables+23505](evidence/task87/manual-sql.log) / [Guardexit3](evidence/task87/sql-guard.log)
- [Fullverification](evidence/task87/verification.log) / [Sourcehashes/environment](evidence/task87/source-manifest.json)

Cacheเป็นapplication-maintained ไม่มีtriggerให้directSQL/ORMimportแก้ตามอัตโนมัติ. ใช้serviceสำหรับwriteปกติ; auditแจ้งdriftไม่เปลี่ยนข้อมูลเอง ถ้าพบข้อมูลจริงผิดต้องตรวจสาเหตุ/อนุมัติวิธีซ่อมแยก ไม่รันrehearsalกับฐานใช้งาน. Eligibility/commentvalidationไม่บังคับครบด้วยDBconstraints. SQLเต็มทุกprofileเหมาะauditไม่ใช่แทนAPIpaginatedlist และไม่อ้างproductionperformanceจากfixtureเล็ก

งานนี้แก้เอกสารUS14ในdatabase-by-storyให้ตรงmigration/mainและORMPROTECTจริง. ไม่เปลี่ยนสูตรดาว/credit, ไม่เปิดNO_SHOW_ENABLED, ไม่ปิดTask95/API/UI/No-showtestsแทนเพียงเพราะtargetedผ่าน. ไม่พบproductionbugจากเคสที่รันจึงไม่มีproductionfix/retestใหม่; จงใจinjectdriftเป็นการตรวจdetectorเท่านั้น. รอGearreview/mergeก่อนComplete ไม่ติ๊กreviewแทนทีม
