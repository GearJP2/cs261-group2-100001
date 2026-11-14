# Task44 — Sprint 2 scope, AC, API contract และ dependency

วันที่ตรวจ: **14 พฤศจิกายน 2026 (Asia/Bangkok)**

- งาน [Task44 / #60](https://github.com/GearJP2/cs261-group2-100001/issues/60), `S2-PLAN-01`
- คนหลัก/ผู้ตรวจรับแผนรวม: Gear (`GearJP2`); ผู้รวบรวม/คู่ช่วย: Gold (`gold555555`)
- Branch `docs/s2-planning-ac-contract-matrix`; main ที่อ่าน `f8eb427f9ad546d380afc805929af00cb85e0e19`
- **สถานะ: ส่งตรวจแผนรวม ไม่ใช่มติแทนทีม**. การ merge implementation ไม่เท่ากับ Story ผ่าน Manual UI/UAT และไม่ปิดงานเปิดอยู่จากการอ่านโค้ด
- ใช้วันที่/หลักฐานจริงข้างต้น ไม่ย้อนหลังบันทึกว่ามี Sprint Planning ครบตั้งแต่ต้น Sprint

## 1. เป้าหมายและขอบเขต Sprint

ต่อยอด US3 Pending ของ Sprint1 ให้ Host ตัดสินคำขอ (US10), ผู้มีสิทธิ์ดูสมาชิกปัจจุบัน (US6), สมาชิกถอนตัว (US4), ค้นหาปาร์ตี้ (US2), และรีวิว/ดาว/No-show ตามมติที่มีหลักฐาน (US14). ไม่เพิ่มระบบเพื่อน เชิญเพื่อน หรือแชท

Sprint2 ตามวันที่โกลให้: **21 ต.ค.–18 พ.ย. 2026** (ช่วง4สัปดาห์); Sprint1 คือ7–21ต.ค. ไม่เขียนSprint2เป็น2สัปดาห์แทนข้อมูลทีม. หากเกณฑ์รายวิชาต้องการต่างจากนี้ Gear/ทีมต้องบันทึกข้อสรุปจริงก่อนนำเสนอ

Story points ต้นทาง: US10=5, US6=2, US4=2, US2=3, US14=5 รวม17; เป็น estimateเดิมระดับStory **ไม่ใช่ชั่วโมง/velocityหรือestimateงานย่อยที่ทีมยืนยันแล้ว**. ownerในตารางงานมาจากGitHub; reviewerรายงานย่อย/estimateกำลังคนยังต้องให้ทีมเติม ไม่กำหนดแทนทีม. Trello due18พ.ย.23:59เป็นกำหนดส่ง ไม่ใช่วันที่ทำเสร็จจริง

## 2. หลักฐานยืนยัน / ข้อขัดแย้ง / Gate

| ID | ข้อเท็จจริงที่ตรวจพบ | ข้อเสนอ/สิ่งที่ต้องตัดสิน | ผู้รับคำถาม / ผลต่อการเริ่มงาน |
| --- | --- | --- | --- |
| PLAN-D01 | #55 และ #60 ยังระบุอ่าน `/join-requests` และ POST `/approve`,`/reject`; mainใช้ GET `/join-requests/pending` และ POST `/decision` body status. DesignTask47ตั้งใจไม่ตัดสินrouteการapproveแทนTask48 | **เสนอ reuse routeบนmain** แล้วแก้เอกสาร/Issueต้นทางให้ตรงหลังรับรอง หรือเลือกเปลี่ยนrouteพร้อมแผนcompatibility/caller/testsในงานแยก. เอกสารนี้ไม่อ้างว่าทีมเลือกแล้ว | Gear + P/Golf + ผู้ทำFE; Task48 #63/Task52 #67 ยังเปิด ห้ามปิดแทนเพียงเพราะserviceRejectมีอยู่ |
| PLAN-D02 | US6 backend/DBmergeแล้ว แต่ DesignTask58 #73 ยังเปิด; can_view_membersใช้Hostหรือactive member, listingใช้activeแถวจริง | เสนอรับcontractmainรวมกรณีHostไม่มีactive row: มีสิทธิ์อ่านแต่ไม่สังเคราะห์Hostในรายการ/count | Gear + Austin + FE; ไม่อ้างว่าทุกคนมีสิทธิ์อ่านตามถ้อยคำStoryเดิม |
| PLAN-D03 | US4 DesignPR136 GearAPPROVED/merge, servicePR139และAPI158merge; ยังไม่มีหลักฐานAustinreviewในDesignchecklist | reuseกติกาHostห้ามถอน, now<starts_at, retryคืนleft_atเดิม, softleave/Party-firstlock. ไม่ติ๊กAustinแทน | Gear/Golf; API/DBพร้อมทำtest แต่FE/ManualAPI/UIยังเป็นงานแยก |
| PLAN-D04 | US2 PR157 แก้ลิงก์Sequence/ACที่c8267b0แล้ว; Gear APPROVED14พ.ย.16:04:27 และMERGED16:04:42(Bangkok). Reviewยังระบุว่าAC mappingเป็นข้อเสนอรอทีมยืนยัน. GETบนbaseที่ตรวจยังไม่อ่านfilters/จำกัด50รายการ | ข้อสังเกตเรื่องลิงก์ปิดแล้ว ไม่ต้องแก้ซ้ำ. ข้อเสนอD01–D08: AND, starts-within[from,to), Bangkokday, state/default, stablepagination, Indoor/Outdoor, titleq ยังต้องมีหลักฐานรับรองsemantics/AC mappingก่อนเป็นcontractใช้งาน | Golf/Austin/Gear; Task78ตรวจของเดิม/เตรียมqueryได้ แต่การmergeเอกสารไม่ใช่หลักฐานรับรองsemanticsทั้งหมด; Task79/84ส่วนที่ขึ้นกับcontractยังรอข้อสรุปนี้ |
| PLAN-D05 | [No-show approved policy](us14-no-show-approved-policy.md) บันทึกGearเลือกกติกา13พ.ย. และpolicy.pyอ้างapprovedแล้ว. เอกสารD-01เก่ายังเก็บP-1..9เป็นข้อเสนอ | ใช้มติใหม่เป็นแหล่งหลักเรื่องNo-show ไม่กล่าวว่าpolicyทั้งหมดยังBlocked. flag=falseเป็นdeploymentdecisionแยก ไม่เปิดในงานplanning | Gear/Austin; updateข้อความเก่าด้วยหมายเหตุชี้มติใหม่. testsที่skipเดิมไม่ใช่หลักฐานว่ากติกายังไม่มี ต้องret ไปทดสอบก่อนรับงาน |
| PLAN-D06 | Storyต้นทางUS14ใช้คำว่า"ค่าเฉลี่ยเครดิต" และschemaเก่าบอกledgerdeltaอย่างเดียว; มติใหม่แยกดาวกับcreditและรับopeningbalance | ค่าเฉลี่ยดาว=sum/count; creditNULLเริ่มฐาน100เมื่อหักครั้งแรกแล้ว-5เป็น95; ledgerdelta=-5. ไม่ใช้ผลรวมdeltaแทนยอดโดยลืมopeningbalance | Gear/เจ้าของDB Gold+Golfตรวจอ้างอิงTask87/95; ไม่เปลี่ยนสูตรเอง |
| PLAN-D07 | OwnerหลักจากIssueมีแล้ว แต่ไม่มีestimateย่อย/หลักฐานมติรวมครบทุกข้อ; #60มีself-dependency S2-PLAN-01ซึ่งไม่ใช่gateที่ทำได้จริง | Task44ไม่มีprerequisiteตัวเอง; planning→design→DB/API→FE→test→integration/review. บันทึกestimate/reviewerและมติD01/D02/D04จริงก่อนอ้างTask44เสร็จ100% | Gear/ทีม; ไม่สร้างวันประชุม/ผู้อนุมัติหรือผลทดสอบย้อนหลัง |

สถานะIssue/PRข้างต้นเป็นsnapshotวันที่ตรวจ ไม่ใช่ข้อมูลสดตลอดเวลา. [PR157](https://github.com/GearJP2/cs261-group2-100001/pull/157) mergeแล้วที่c8267b0 แต่semantics/AC mappingยังรอรับรองตามreview. BranchTask44ยังยึดbasef8eb427เดิม จึงอ้างเอกสารUS2ผ่านPR/commitโดยไม่เพิ่มลิงก์localไปไฟล์ที่ไม่มีบนbaseนี้

## 3. AC matrix ที่วัดผลได้

รหัส `PLAN-USx-nn` เป็น **รหัสตรวจรับที่เสนอในTask44** ไม่อ้างว่าเป็นหมายเลขACเดิมบนTrello. Mappingใช้หัวข้อScenarioต้นทางใน [user-stories](user-stories.md) และpolicyที่ระบุ; reviewerต้องรับรองcrosswalkก่อนเปลี่ยนหมายเลขบนการ์ด. Expectedด้านล่างไม่ใช่Actualของการรันในงานเอกสารนี้

| ID / ต้นทาง | Given / When | Expectedที่วัดได้ | Test scope / หลักฐานอ้างอิง |
| --- | --- | --- | --- |
| PLAN-US10-01 / Scenarioอนุมัติ | HostเปิดPendinglist | เฉพาะPartyตน/statusPending, fields id/display_name/created_at, เรียงcreated_at,id; ไม่มีemail/login | API: [test_pending_requests](../backend/parties/test_pending_requests.py); ManualAPI #71 |
| PLAN-US10-02 / Scenarioอนุมัติ | HostapprovePendingก่อนเริ่มและมีที่ว่าง | requestApproved+active membershipcommitด้วยกัน; countไม่เกินcapacity; reactivationreuseแถว | DB [Task49](s2-us10-db-task49.md), [Task57](s2-us10-t-db-task57.md) |
| PLAN-US10-03 / Scenarioปฏิเสธ | HostrejectPendingก่อนเริ่ม/ไม่cancelled | requestRejected/decided_by/at; membership/countไม่เปลี่ยน | [test_approval](../backend/parties/test_approval.py); #67/#71 |
| PLAN-US10-04 / เพิ่มขอบเขตตรวจ | nonHost/requestข้ามParty/decideซ้ำ/full/start/cancel | 403/404/409ตามcontract ไม่มีpartialwrite; stateFullขัดapproveแต่ไม่ขัดreject | API #71, DB #72; [race source](../backend/parties/test_approval_concurrency.py) |
| PLAN-US10-05 / UIหลังตัดสิน | กดรับ/ปฏิเสธสำเร็จ/ล้มเหลว/กดซ้ำ | ป้องกันซ้ำระหว่างรอ; refreshrequest+countจากserver; ไม่แสดงsuccessจากnetworkerror | ManualUI #70; ไม่ใช้backendtestsแทนการกดจริง |
| PLAN-US6-01 / Scenarioแสดงสมาชิก | Hostหรือactive memberGETmembers | นับ/listเฉพาะleft_atNULL; Pending/Rejected/ผู้ถอนถูกตัด; Hostroleตามhost_id | [Task60](s2-us6-db-01-active-members.md), [Task66](s2-us6-t-db-task66.md) |
| PLAN-US6-02 / สิทธิ์/ข้อมูล | nonmember/ผู้ถอนGETmembers | 403ไม่เผยรายชื่อ; no-profileใช้fallbackไม่ใช้username/email; staffไม่ข้ามสิทธิ์ | [test_members](../backend/parties/test_members.py), ManualAPI #80 |
| PLAN-US6-03 / เรียงและcount | มีHostrowและสมาชิกร่วมเวลา | Hostก่อน แล้วjoined_at,id; member_count=lenรายการ; Hostไม่มีactive rowไม่สร้างแถวจำลอง | test_roles_and_count_match_the_list / test_host_without_active_row_is_not_synthesized_and_matches_party_detail |
| PLAN-US6-04 / refresh | approve/leavecommitแล้วโหลดใหม่ | activeรายการ/countตรงDBหลังcommit; ผู้ถอนmembers403ให้ล้างรายชื่อเก่า | #78/#79 และintegration #111 |
| PLAN-US4-01 / Scenarioถอนก่อนเริ่ม | active Mไม่ใช่Host, now<starts_at,ไม่cancelled → leave | 200/is_memberfalse/left_at; เก็บID/joined_at; countลด1/slotsเพิ่ม1ถ้าไม่มีwriterอื่น | [policy](us4-leave-party-policy.md), [APItests](../backend/parties/test_leave_api.py), #90 |
| PLAN-US4-02 / Scenarioห้ามหลังเริ่ม | firstleaveที่starts_atหรือหลัง/Cancelled | 409PARTY_STARTEDหรือPARTY_CANCELLED; ไม่mutate; Host403ก่อนstate | [Design API08–11](us4-leave-party-test-cases.md), #89 |
| PLAN-US4-03 / retry/race | retryขณะยังleft / 2leave / leaveแข่งapprove | retry200เวลาเดิมไม่write/คืนที่เพิ่ม; Partylockร่วมcountไม่เกินcap; failureหลังwriteทำให้rollback | #90 [PR159](https://github.com/GearJP2/cs261-group2-100001/pull/159) ส่งแล้ว ยังต้องreviewไม่อ้างmerge |
| PLAN-US4-04 / กลับเข้าร่วม | leave→ขอใหม่→approve | ก่อนapproveยังไม่active; reusemembership/request; retryคำสั่งเก่าข้ามรอบไม่รับรอง | DesignDB07; Task69test_rejoin_requires_approval_then_allows_new_leave_cycle |
| PLAN-US4-05 / UIยืนยัน | เปิดconfirmแล้วยกเลิก/ยืนยัน | cancelไม่ส่งPOST; หลังsuccessโหลดdetailล่าสุด; members403หลังleaveไม่ใช่leaveล้มเหลว | #88 ManualUI / #89 ManualAPI ไม่ใช้SQLแทน |
| PLAN-US2-01 / Scenarioค้นหาตามเงื่อนไข | q/sport/venue/type/ช่วงเวลา/stateพร้อมกัน | **ข้อเสนอรอreview:** ทุกfilterAND; qicontainsเฉพาะtitle; incompatibleคู่sport/venueได้รายการว่าง | PR157D01/D07/D08 → #93/#94/#98/#99 |
| PLAN-US2-02 / วันเวลา | dayDตามBangkokและรายการตรงขอบfrom/to | **ข้อเสนอ:** starts_at>=from และ<to, ไม่ใช่overlap; fromรวม/toไม่รวม; datetimeต้องoffset | PR157D02/D03 → testเวลา/SQL #99 |
| PLAN-US2-03 / state | ไม่ส่งstate/ส่งexplicit | **ข้อเสนอ:** defaultOpen; precedenceCancelled→Completed→InProgress→Full→Open; nowเดียว/request | PR157D04/D05; reuseget_party_state |
| PLAN-US2-04 / Scenarioไม่พบ | filterไม่มีผล/pageเกิน | **ข้อเสนอ:** 200data[]พร้อมpage/page_size/total; filterก่อนcount/page; sortstarts_at,idคงที่ | PR157D06; ManualAPI #98/SQL #99 |
| PLAN-US2-05 / validation | repeat/unknown/invalidquery/ช่วงfrom>=to | **ข้อเสนอ:** 400INVALID_INPUTพร้อมfieldsไม่เปลี่ยนDB; UIloading/empty/error/reset/staleresponseถูกต้อง | PR157testcases → #97/#98; ยังไม่ถือว่าระบบรองรับ |
| PLAN-US14-01 / Scenarioดาวรีวิว | Completedไม่cancelled, reviewer/revieweeเข้าร่วมถึงends_at,ไม่ใช่ตนเอง | 201review; ratingint1..5/commenttrimไม่ว่าง<=500; ผู้ถอนก่อนends_atไม่ผ่าน | C2/C3 [decisions](us14-d-01-decisions.md), #109/#110 |
| PLAN-US14-02 / unique/cache | รีวิวคู่เดิมPartyเดิมซ้ำ/พร้อมกัน/failure | หนึ่งreviewต่อparty/reviewer/reviewee; 409REVIEW_EXISTS; cacheกับreviewatomic; no-reviewaverage=null | C4/C6; [test_reviews_concurrency](../backend/conduct/test_reviews_concurrency.py), Task87/95 |
| PLAN-US14-03 / publicread | verifieduserอ่านรีวิวคนอื่น | 200summary+publicallowlist; ไม่ส่งemail/studentID/reviewerID/partyIDในรายการGET; page metadataในdata | C5; [test_review_list](../backend/conduct/test_review_list.py), #104/#109 |
| PLAN-US14-04 / No-show | flagtrue, Completedถึงends_at+7วันรวมปลาย; ผู้รายงานไม่ซ้ำถึงthreshold | deduction-5ครั้งเดียว/คน/Party; Nไม่รวมเป้าหมาย; N1→1 มิฉะนั้นmax(2,N//2+1); creditNULL100-5=95 | [มติใหม่ P1–P9](us14-no-show-approved-policy.md), [test_no_show_concurrency](../backend/conduct/test_no_show_concurrency.py) |
| PLAN-US14-05 / flag/privacy | flagfalseหรือcreditหลังdeduction | flagfalseendpoint404(ยกเว้นCSRFmiddlewareตอบก่อน); ไม่เปิดflagในplanning; profileแสดงcreditทันทีตามมติP6 ไม่มีfloor/appealในSprint2 | #105/#109; การมีpolicyไม่ใช่หลักฐานManualUI/APIผ่าน |

## 4. API/data contract baseline และตัวอย่าง

ทุกpathด้านล่างขึ้นต้น `/api/v1`. ผู้ใช้ต้องผ่านsession/universityguard; POSTต้องCSRF. Sharederrors: 401AUTH_REQUIRED, 403FORBIDDEN/ACCOUNT_INACTIVE/CSRF_FAILED, 405METHOD_NOT_ALLOWED. Inactive sessionอาจถูกModelBackendresolveanonymousได้401. `error.fields` มีเฉพาะvalidationที่ส่งมา. ไม่ส่งpassword/token/email/studentIDลงlog. ตัวเลขในJSONเป็นข้อมูลสมมติสำหรับอธิบายรูปแบบ ไม่ใช่ผลทดสอบ

### US10 — current main; route decisionยังต้องปิดPLAN-D01

| Request | สิทธิ์/ผล | Domainerrors |
| --- | --- | --- |
| GET `/parties/12/join-requests/pending` | Hostเท่านั้น; อ่านPendingได้ทุกstateParty, arrayสามfield | 404NOT_FOUND /403FORBIDDEN |
| POST `/parties/12/join-requests/8/decision` body `{"status":"Approved"}` หรือRejected | Hostเท่านั้น; 200 `data.id,status`; Party→Request→Membershiplock | 400INVALID_INPUT /404NOT_FOUND /409REQUEST_DECIDED,PARTY_CANCELLED,PARTY_STARTED,PARTY_FULL(approve),ALREADY_MEMBER(approve) |

```json
{"data":[{"id":8,"display_name":"สมาชิกทดสอบ","created_at":"2026-11-14T10:00:00+07:00"}]}
```
```json
{"data":{"id":8,"status":"Approved"}}
```
```json
{"error":{"code":"PARTY_FULL","message":"กิจกรรมนี้เต็มแล้ว"}}
```

ไม่เพิ่ม `/approve`,`/reject` aliasesในTask44. ต้องรับรองความต่างจาก#55/#60ก่อนเรียกbaselineนี้ว่ามติรวม

### US6 — current main

GET `/parties/12/members`, ไม่มีbody. Hostหรือactive member; 200 `data.members/member_count`. ไม่จำกัดเฉพาะOpen. nonmember403 /unknownParty404 /unsupportedmethod405. รายการเป็นactiveแถวจริง; Hostสิทธิ์อ่านไม่แปลว่าต้องมีrowสังเคราะห์

```json
{"data":{"members":[{"user_id":7,"display_name":"ผู้จัดกิจกรรม","role":"Host"}],"member_count":1}}
```

### US4 — merged Design/main

POST `/parties/12/leave`, emptybodyหรือ `{}` เท่านั้น. actorจากsession; unknownfields/user_id/left_atที่clientส่งมา400. Party404 → Host403HOST_CANNOT_LEAVE → no-membership403NOT_MEMBER → already-left200 → Cancelled409 → now>=starts_at409 → writeleft_at. Already-left200ได้แม้Partyเริ่ม/จบ/cancelภายหลัง

```json
{"data":{"party_id":12,"is_member":false,"left_at":"2026-11-14T10:00:00+07:00"}}
```

GETdetailหลังleaveอ่านcount/slotsจริง; GETmembersหลังleave403ต้องล้างUIเก่า. ไม่มีidempotencykeyข้ามรอบสมาชิกและไม่ลบประวัติ

### US2 — proposal from PR157, NOT implemented/accepted contract

GET `/parties?q=badminton&sport_id=1&venue_id=2&venue_type=Indoor&starts_from=2030-11-20T00:00:00%2B07:00&starts_to=2030-11-21T00:00:00%2B07:00&state=Open&page=1&page_size=20`

fieldsqmax100trim/titleicontains, IDspositive, typeIndoor/Outdoor, awareISOdatetime, stateenumหรือall, pagepositive/default1, page_size1..100/default20. Unknown/repeated/emptyvalueยกเว้นqเป็น400ตามข้อเสนอ. InvalidIDรูปแบบถูกแต่ไม่พบข้อมูลให้200empty. responseรายการreusePartyDetailallowlist; metadataนอกdataarrayตามPR157 ไม่เท่ากับreviewAPIที่metadataในdata

```json
{"data":[],"page":1,"page_size":20,"total":0}
```
```json
{"error":{"code":"INVALID_INPUT","message":"ตัวกรองค้นหาไม่ถูกต้อง","fields":{"starts_to":"ต้องอยู่หลัง starts_from"}}}
```

mainปัจจุบันไม่อ่านparametersข้างต้น แสดงเฉพาะfuture/notcancelled/notfullเรียงstarts_atlimit50. Task78ต้องตรวจschemaVenue.venue_typeที่ยังไม่มีและindexจากqueryจริง ไม่ตีความvenue_kindREAL/MOCKเป็นIndoor/Outdoor. ไม่เพิ่มindexหากไม่มีหลักฐานquery/EXPLAINที่เหมาะสม

### US14 — current main + approved No-show policy

| Request | Body/query | Success / Domainerrors |
| --- | --- | --- |
| POST `/parties/12/reviews` | `reviewee_id`, `rating`, `comment`เท่านั้น | 201data.review; 400INVALID_INPUT /403FORBIDDEN /404NOT_FOUND /409PARTY_NOT_COMPLETED,REVIEW_EXISTS |
| GET `/users/7/reviews` | page(default1),page_size(default20,max100) | 200data.user_id,average_rating,rating_count,reviews,page,page_size,total; 400INVALID_INPUT /404NOT_FOUND |
| POST `/parties/12/no-show-reports` | `reported_id`เท่านั้น | flagfalse404ก่อนviewguard/bodyparse(แต่CSRFmiddlewareอาจ403ก่อน); enabled201data.report; 409PARTY_NOT_COMPLETED,REPORT_WINDOW_CLOSED,REPORT_EXISTS; สิทธิ์/ข้อมูล400/403ตามD-01 |

```json
{"reviewee_id":7,"rating":5,"comment":"ร่วมกิจกรรมตรงเวลา"}
```
```json
{"data":{"review":{"id":31,"party_id":12,"reviewer":{"id":8,"display_name":"ผู้รีวิว"},"reviewee_id":7,"rating":5,"comment":"ร่วมกิจกรรมตรงเวลา","created_at":"2026-11-14T10:00:00+07:00"}}}
```
```json
{"data":{"user_id":7,"average_rating":null,"rating_count":0,"reviews":[],"page":1,"page_size":20,"total":0}}
```
```json
{"reported_id":7}
```
```json
{"data":{"report":{"id":9,"party_id":12,"reported_id":7,"created_at":"2026-11-14T10:00:00+07:00"}}}
```

GETreviewรายการส่งreviewid/rating/comment/reviewer.display_name/created_at ไม่ส่งreviewerid/partyid. POSTresponseให้ผู้ส่งเองมีIDsตามcontract ไม่เอาallowlistGETมาสรุปว่าห้ามIDsทุกresponse. คะแนนดาวกับconductcreditไม่คำนวณจากกัน. No-showpolicyใช้openingbalance+delta ไม่ใช่sumdeltaอย่างเดียว; ไม่มีfloor/appeal; creditprofileแสดงทันทีตามมติ. **ไม่เปิดNO_SHOW_ENABLEDในTask44**

## 5. งานจริง / owner / dependency และลำดับทำ

เลขด้านล่างเป็นIssueจริงที่ตรวจจากGitHub ไม่อนุมานจากTasknumber. ownerตามIssueวันที่ตรวจ; คนเลือกงานตามflowทีมยังเปลี่ยนได้ ต้องอัปเดตIssue/Trelloพร้อมกัน. reviewerที่ขอมาตรวจแผนรวมคือGear; estimateงานย่อยยังรอทีม ไม่ถือpointsเดิมแทนestimateย่อย

| กลุ่ม | Design → DB / API → FE → Tests | Ownerจุดส่งต่อ / เงื่อนไข |
| --- | --- | --- |
| Shared | Task44 #60 → Task45 #118; FixturesTask46 #61 (closed) | Gearplanning/QA, Goldfixtures; ไม่ให้#60ขึ้นกับตัวเอง |
| US10 | DesignTask47 #62/Task48 #63 → DBTask49 #64; API50 #65/51 #66/52 #67 → FE53 #68/54 #69 → UI55 #70/API56 #71/DB57 #72 | P(kxorukox)Design/API/ManualAPI, GoldDB, ratanaphong29FE/UI; GateD01ก่อนเปลี่ยนroute |
| US6 | Design58 #73/59 #74 → DB60 #75/API61 #76 → FE62 #77/63 #78 → UI64 #79/API65 #80/DB66 #81 | AustinDesign/API, GoldDB, RieroSFE/UI; policyread/publicfieldsต้องตรวจรับD02; FIxturesไม่แทนFE |
| US4 | Design67 #82/68 #83 → DB69 #84/API70 #85 → FE71 #86/72 #87 → UI73 #88/API74 #89/DB75 #90 | Golfpolicy/API/ManualAPI, GoldDB, ratanaphong29FE/UI; Design136/DB139/API158mergeแล้ว; DB75PR159รอreview |
| US2 | Design76 #91/77 #92 → DB78 #93/API79 #94 → FE80 #95/81 #96 → UI82 #97/API83 #98/DB84 #99 | Golfsemantics/API, GoldDB, RieroSFE/UI; **PR157แก้ลิงก์และmergeแล้ว เหลือgateรับรองsemantics/AC mappingในD04**. DB/APIประสานparallelได้หลังcontractยืนยัน; testsdesignก่อนได้แต่Actualรอimplementation |
| US14 | Design85 #100/86 #101 → DB87 #102/API88 #103/89 #104/90 #105 → FE91 #106/92 #107 → UI93 #108/API94 #109/DB95 #110 | Austinpolicy/API, GoldDB, ratanaphong29FE/UI; C1–6และNo-showpolicyมีหลักฐานแล้ว; confirmDBauditQ13แยกTask87; flagdeploymentตัดสินแยก |
| Integration | ทั้ง5storiesที่ส่งมอบจริง → Task96 #111 → Task97 #112 | Gearreview/demo/retrospective; งานค้างให้ระบุจริง ไม่ย้ายCompleteจากCIอย่างเดียว |

ลำดับใช้งานที่เสนอ: US10รับสมาชิก → US6เห็นสมาชิก → US4ถอนและคืนที่ → US2ค้นหาเข้าถึงParty → US14หลังจบ. เป็นลำดับdependency/การสาธิต ไม่ใช่บังคับให้ทุกคนรอเรียงทีละStory; งานDesign/fixtures/testsdesignทำparallelได้และใช้ของmainก่อนเพิ่ม

## 6. DoD และการส่งต่อทดสอบ

ก่อนเริ่มImplementรายStory: AC/contractที่กระทบงานนั้นยืนยันพร้อมลิงก์ผู้ตรวจ, owner/reviewer/estimateและdependencyชัด. ส่วนที่ยังไม่มีมติห้ามตีความว่าต้องรอทุกStoryพร้อมกันหรือให้เลือกกติกาเอง

การทดสอบทุกcaseต้องมี CaseID/AC, tester+วัน, commit+environment, Precondition/ข้อมูล, Steps/input, Expected, Actual, Pass/Fail/Blocked/Notrun, rawหลักฐาน, bug/retestเมื่อมี. แยก4ประเภทไม่ใช้แทนกัน:

- Unit: mock/stubแยกfunction/component; ห้ามเรียกDBจริงแล้วอ้างunit
- API integration/ManualHTTP: ระบุว่าDjangotestclientหรือnetworkHTTPจริง; request/response/auth/CSRF/errorและSQLeffectsตามscope
- Database: SQLก่อน/หลัง/rollback+constraint/query; raceต้องคนละconnectionพร้อมsynchronizationและหลักฐานlock ไม่ใช้snapshotอย่างเดียว
- ManualUI/UAT: ผู้ทดสอบกดจริงตามsteps/expected screenshots; automatedbackend/CIไม่พิสูจน์แทน

Flowทีม: ToDo → Doing(ผู้รับงานใส่ชื่อ) → Done(ส่งPRรอreview) → Completeเมื่อผ่านDoD/review/mergeและหลักฐานรับงานครบ. Testingใช้แสดงงานที่กำลังตรวจได้ตามflowทีม แต่CIpassอย่างเดียวไม่ทำให้ManualUIผ่าน. ให้เก็บbug/retestและวันที่เสร็จจริงแยกdue

## 7. Review checklist — ยังไม่ติ๊กแทนผู้ตรวจ

- [ ] GearรับรองPLAN-D01ว่าจะreusepending/decisionrouteหรือเปลี่ยนcontractด้วยงานแยก แล้วsync#55/#60/Task48
- [ ] Gear/AustinรับรองPLAN-D02ของUS6และปิดช่องว่างDesignTask58ด้วยหลักฐานจริง
- [ ] Golf/Austin/GearบันทึกการรับรองsemanticsD01–D08และAC mappingก่อนส่งต่อTask78/79 (PR157แก้ข้อสังเกตเรื่องลิงก์และmergeแล้ว ไม่ต้องแก้ลิงก์ซ้ำ)
- [ ] ผู้รับผิดชอบUS14รับทราบมติใหม่/featureflagและretเคสที่เคยskip ไม่อ้างpolicyยังไม่มี
- [ ] ทีมยืนยันACcrosswalk, owner/reviewer/estimateย่อยและSprintdateตามข้อ1
- [ ] Gearตรวจเอกสารฉบับรวม/บันทึกมติจริงก่อนปิดTask44; mergeเอกสารที่ยังมีpendingdecisionsไม่ทำให้pendingเหล่านั้นหายไป

งานรอบนี้เป็น**document/source audit** ไม่รันAPI/UI/PostgreSQLtestsใหม่ ไม่เอาlogTaskอื่นมาอ้างว่ารันทุกรายการใหม่. หลักฐานตรวจเอกสารและsnapshotอยู่ [Task44 audit](evidence/task44/audit.md). ไม่มีการแก้runtime/schemaหรืออนุมัติแทนทีม
