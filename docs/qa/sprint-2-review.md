# Task97 — Sprint 2 review และผลส่งมอบ

จัดทำ 17 พฤศจิกายน 2026 ตามคำขอ Gear · Task97 / [#112](https://github.com/GearJP2/cs261-group2-100001/issues/112) · คนหลัก Gear, คู่ช่วย Gold. ผู้ช่วยรวบรวมหลักฐาน ไม่อ้างว่า Gold review แล้วหรือมีการประชุม Sprint Review/Retro เกิดขึ้นย้อนหลัง

Baseline ที่ตรวจ: main `4fda705c010977087ba5cb09834ce43b0fe56493` (merge PR186). Runtime/tooling fingerprints ตรงกับ Task96 ที่ทดสอบบน `d157487`. รอบ Task97 เป็น **document/evidence review ไม่รันระบบใหม่**

## ผลที่นำเสนอได้

Sprint 2 ครอบคลุม US10 ตัดสินคำขอ, US6 สมาชิก, US4 ถอนตัว, US2 ค้นหา และ US14 รีวิว/No-show. แผนเดิมระบุ21ต.ค.–18พ.ย.2026, estimateระดับStory17points; ไม่แปลงเป็นชั่วโมง/velocityหรืออ้างว่าทุกงานส่งตรงเวลา

| มุมที่ตรวจ | ผลจริง / ขอบเขต |
| --- | --- |
| GitHub delivery snapshot | Sprint2 issues59: ปิด58 เหลือTask97/#112. ทั้งrepo issues93: ปิด92. PR93: merge88, อีก5ปิดโดยไม่merge, ไม่มีPRเปิดก่อนสร้างPRของTask97. Snapshotนี้ไม่ใช่อัตราACผ่าน |
| Integrated execution | Task96 **19/19 PASS**, 0FAIL บนrevisionรวมเดียว พร้อมnativeChromium/HTTP/PostgreSQL และPartyชุดเดียว ไม่รวมผลต่างStoryมานับเป็นrunเดียว |
| Regression automation | Task96 backend**717 PASS/no skips**, frontend**40 PASS**, make smokeและCIผ่าน. 34methodsในselectedrace/DBsuitesมีPostgreSQLtransaction/concurrencyจริง ไม่ใช้sequentialSQLแทนraceproof |
| Planned coverage | Task45มี24PLAN AC/101cases. [Crosswalkล่าสุด](sprint-2-review-coverage.csv) เชื่อมครบ24PLAN IDsกับหลักฐาน แต่ไม่ได้พิสูจน์ว่า101cases/ทุกvariantถูกรันใหม่ครบ จึงไม่รายงาน100%ACPass |
| Not run | LiveTUauthentication, humanUAT/peer-signoff, productionload. การยืนยันsessionสังเคราะห์/me/logout/providerunavailableไม่ใช่TUloginsuccessจริง |
| Final acceptance | Task96/#111ปิดหลังGearmergePR186. Task97ฉบับนี้ยังรอreview/merge; คำว่าissueปิดหรือCIผ่านไม่ใช้แทนhumanUATหรือมติทีม |

[Machine-readable receipts และเวลารวบรวม](../evidence/task97-review/receipts.json) เก็บcensusจากGitHubครบทุกหน้า ไม่รวมPRในตัวนับissues. จำนวนอาจเปลี่ยนหลังsnapshot

## Story → Task → ผลทดสอบ/หลักฐาน

| Story | หลักฐานที่ตรวจรับแล้ว | สิ่งที่ยืนยัน / ขอบเขตที่ยังไม่อ้าง |
| --- | --- | --- |
| US10 | Task96 F03/F04/F05/F09; [Task55 Node report](../evidence/task55-ui.md); Task64 B06/PR184 | Pendingไม่กินที่, nativeApprove/reject/refreshและสิทธิ์ผ่านในTask96; race/guardอยู่backendsuite. Task55รายงานเก่าเป็นNode mocks; ไม่ยกระดับkeyboard/native double-clickทุกvariantเป็นPassจากflowพื้นฐาน |
| US6 | Task64/#79 PR184 [browser10](../evidence/task64-browser/README.md); Task65/#80 PR183 [HTTP13](../evidence/task65-http/README.md); Task96 F03/F04/F06 | Host/Member/nonmember/left/fallback/order/count/publicfields, refresh/clear403/404ผ่านตามcases. AvatarN/A: Memberscontractไม่มีรูป ไม่สร้างผลtestรูป |
| US4 | Task73/#88 PR181 [browser/API11](../evidence/task73-browser/README.md); Task96 F06–F09; backendrace/DB | Nativeconfirm/cancel/Escape/leave/retryและrejoin/historyตามรายงาน; Host/started/cancelledถูกปฏิเสธ; ไม่นำSQLsnapshotมาอ้างkeyboardproof |
| US2 | Task82/#97 PR185 [browser12](../evidence/task82-browser/README.md); Task96 F02/F05/F08 | ผสมfilters/chips/reset/page20+1, Bangkoktime, empty/error, delayedrealresponses, restrictedstates→Detail/nojoinผ่าน; exactmicrosecondboundariesใช้backendtests ไม่ใช่ความเร็วการคลิก |
| US14 | Task93/#108 PR180 [browser23](../evidence/task93-browser/README.md); Task94/#109 PR182 [HTTP24](../evidence/task94-noshow/README.md); Task96 F10–F16 | รีวิว/cache/unique/summary/privacyและNo-showflag/threshold/เครดิต95ครั้งเดียวไม่เปลี่ยนดาวผ่าน. ค่าเริ่มต้นflagปิดและรอบนี้ไม่เปลี่ยนdeploymentflag ไม่อ้างliveTU/humanUAT |

ตัวเลขStoryรายงานต่างrevision **ไม่บวกเข้ากับ19หรือ717**. ใช้เป็นsupportingreceiptsตามcommitในแต่ละรายงาน ส่วนหลักฐานข้ามStoryใหม่คือ[Task96](../evidence/task96-cross-story/README.md), [executionCSV](../evidence/task96-cross-story/execution.csv), [rawHTTP/SQL](../evidence/task96-cross-story/run/results.json)

## งานค้าง / ข้อจำกัด / ความพร้อมส่ง

| รายการ | สถานะจริง | วิธีจัดการ |
| --- | --- | --- |
| LiveTUlogin | Notrunในenvironmentทดสอบ ไม่มีTUkey/credentials | แสดงเฉพาะsessionfixturesและmissing-provider502ตามจริง; ทีมที่มีสิทธิ์ต้องรันprovideracceptanceแยกก่อนอ้างผ่าน |
| HumanUAT/การเดโมต่อผู้ตรวจ | ยังไม่มีreceiptว่าจัดpresentationหรือhumanUATแล้ว | [Demo runbook](sprint-2-demo-runbook.md) พร้อมใช้; artifactwalkthroughและautomatedreplayไม่เท่ากับการนำเสนอที่เกิดแล้ว |
| Productionload/device/accessibilityครบทุกแบบ | Notrun | ไม่อ้างรองรับproductionload/ทุกbrowserจากChromiumรอบนี้ |
| Task55 UIบางvariants | หลักฐานnativeApprove/rejectพื้นฐานเติมโดยTask96; keyboard/native double-clickครบทุกvariantยังไม่มีreceiptใหม่ในTask55 | ระบุช่องว่าง ไม่ถือว่าissue70ปิดแล้ว=manualscopeทุกข้อผ่าน |
| Task45 inventory101 | เป็นแผนเดิม, executionfieldsยังNotrunในแผนนั้น | ใช้crosswalk/reportจริงประกอบ ไม่bulkติ๊ก101PASSและไม่สรุปเปอร์เซ็นต์ที่ตรวจย้อนไม่ได้ |
| Frontenddelivery/คุณภาพ | Gearยืนยันล่าช้ากว่าเป้าสัปดาห์แรก งานกระจุกท้ายและยังไม่เรียบร้อย | [Retrospective](sprint-2-retrospective.md) บันทึกfeedbackจริงและข้อเสนอaction; ไม่อ้างว่างานทุกส่วนตรงเวลาเพราะปิดissueแล้ว |
| Task97 review/action adoption | ยังรอPRreview/mergeและการรับรองactionรอบถัดไป | Gearตรวจรายงาน/ข้อจำกัด; Goldเป็นคู่ช่วยตามissue ไม่ใส่ชื่อว่าreviewแล้วโดยไม่มีreceipt |

ไม่พบapplicationfailureในfinalTask96 scope; **ไม่เท่ากับยืนยันว่าไม่มีbugเหลือทั้งระบบ**. บั๊กCSRFที่พบระหว่างTask64ถูกแก้และretetstแล้วในPR184 พร้อม717-test regression. เก็บfailure/historicalreportsตามจริงไม่ลบผลเก่าหรือแก้expectedเพื่อให้ผ่าน

## Review / Retro และไฟล์นำเสนอ

- [Demo runbook6–8นาที](sprint-2-demo-runbook.md): ลำดับเล่า, ภาพ/rawdata, expected, fallbackเมื่อไม่มีTUprovider
- [RetrospectiveจากfeedbackGear](sprint-2-retrospective.md): สิ่งที่ดี/ปัญหา/ข้อเสนอactionและเกณฑ์วัด ไม่บันทึกประชุมหรือคำมั่นของเพื่อนย้อนหลัง
- [สรุปหนึ่งหน้า](../evidence/task97-review/summary.html) / [PNGสำหรับTrello](../evidence/task97-review/summary.png): เป็นภาพสรุปหลักฐาน ไม่ใช่screenshottestใหม่

## การตรวจเอกสารรอบนี้

ตรวจlocalrelative links/ภาพ, schemaและจำนวน24PLANcrosswalk,19executioncases,101plannedcases, census/pagination, sourcefingerprintsเทียบTask96และmerge/CIreceipts. ไม่รันbackend717/browserใหม่เพื่อแก้เอกสาร; ผลruntimeทั้งหมดอ้างcommitและenvironmentเดิมอย่างชัดเจน ผลตรวจเอกสารอยู่[validation.log](../evidence/task97-review/validation.log)
