# Task44 document/source audit — 14 November 2026

ผู้ตรวจรวบรวม: ผู้ช่วยตามคำขอGold; ผู้รับรองแผนรวมที่ขอreview: GearJP2 (ยังไม่อ้างอนุมัติ)

## วิธีตรวจ

1. `git status -sb` ตรวจcleanworkingtree; fetchorigin; สร้างbranchจากIssue60ด้วย `gh issue develop 60 --name docs/s2-planning-ac-contract-matrix --base main` แล้วcheckout. baseคือ `f8eb427f9ad546d380afc805929af00cb85e0e19`
2. อ่านIssue60/55/100 และIssueTask44–102จริงผ่านgh. แยกIssueopen/closedออกจากimplementationที่mergeและผลManualtestซึ่งต้องมีหลักฐานแยก
3. อ่านlocalmainroutes/views/services/model/testsและdocspolicy; อ่านUS2proposalด้วย `git show origin/docs/s2-us2-d-01-search-semantics:docs/us2-search-design.md` ที่b469908. อ่านreviewPR157ไม่สรุปว่าCIpassแปลว่ารับcontractแล้ว
4. เทียบACที่วัดได้กับrequest/response/permissions/state/time/queryและtestsource. สร้างรหัสPLANใหม่ชัดเจน ไม่สมมติว่าเท่ากับหมายเลขบนTrello
5. เก็บdecisionlogและdependencyพร้อมเลขIssueจริง; ไม่เพิ่มstory/estimate/reviewerapprovalหรือdeploymentflagแทนทีม
6. ตรวจJSONexamples, localfilelinks, ACIDsและความครบ5storiesด้วยscriptเอกสาร; ผลจริงอยู่ `document-checks.log`. `git diff --check` ตรวจsource/docsที่แก้

## Expected / Actual

| ตรวจ | Expected | Actual |
| --- | --- | --- |
| Scope | ครบUS10/6/4/2/14 ไม่มีchat/friendที่ผู้ใช้ยังไม่เลือก | มี5Story/24รหัสPLAN, ระบุout-of-scopeชัด |
| Endpointtrace | ข้อความในแผนตรงกับrouteจริงหรือระบุconflict | US10#55/#60ขัดmain → PLAN-D01; ไม่แก้routeเอง |
| State/rights | วัดcount/membership/auth/timeได้ ไม่แค่"ทดสอบระบบ" | matrixมีGiven/When/Expectedและtestscope; US6active/US4retryชัด |
| US2readiness | ไม่อ้างว่าproposalใช้ได้แล้ว | PR157b469908CHANGES_REQUESTEDเรื่องanchorและยังรอsemanticsreview; Task78เตรียมauditได้แต่filterimplementationรอgate |
| US14policy | ใช้มติล่าสุดไม่ใช้บันทึกเก่าทับ | ชี้มติGear13พ.ย.P1–9/flagfalse; ใส่หมายเหตุบนD-01เดิม; testsเคยskipต้องretestเองไม่แปลงเป็นPASS |
| Tasktrace | เลขIssueมีจริง/ไม่selfdependency | mapTasks44–97กับ#60–112และQA#118; #60เริ่มได้ไม่ขึ้นกับตัวเอง |
| Estimates/dates | ไม่สร้างข้อมูลยืนยันทีม | pointsต้นทางรวม17ระบุเป็นestimateเดิม; taskestimates/reviewerรอทีม; Sprint21ต.ค.–18พ.ย.คือ4สัปดาห์ไม่เขียนเป็น2 |
| Approval | มีreviewจริงจึงรับรองได้ | US4PR136GearAPPROVED13พ.ย.; matrixรวมยังรอGear; ไม่ติ๊กComplete/ปิดIssue60แทน |

## Snapshot หลักฐานภายนอกที่อ่าน

- Issue60 OPEN: Gearหลัก/Goldช่วย; AC/contract/dependencyรวมยังไม่มีcommentลงมติ
- Issue55 OPEN: GETjoin-requests และ POSTapprove/rejectในbody; sourceactualเป็นpending/decision
- PR136 MERGED, GearJP2APPROVED `2026-11-13T11:39:26Z` (18:39:26Bangkok); ยืนยันเฉพาะDesignUS4
- PR139/158 MERGED: US4service/API. PR159 OPEN: Task75SQL/raceส่งตรวจ ไม่อ้างmerge
- PR157 OPEN/CHANGES_REQUESTED, head `b46990864092116349ce3e819ae9d4230e7c2c6f`; reviewGearระบุแก้anchorและsemanticsรอตรวจ
- Issue100 CLOSED; `docs/us14-no-show-approved-policy.md` บันทึกGearเลือกpolicy13พ.ย.; `backend/conduct/policy.py` และsettingsสอดคล้องว่าapprovedpolicyแต่flagfalse

Snapshotข้างต้นเป็นผลread-onlyขณะตรวจ ไม่ใช่การwatchสถานะตลอดเวลา. Rawsourceอยู่GitHubmainตามbasecommitและPRที่ลิงก์ในmatrix; ไม่เก็บcredentials/secretenvironment

## สิ่งที่ไม่ได้ตรวจในรอบนี้

ไม่มีruntime/schemachange จึงไม่รันDB/API/UI/UATหรือmakeverify/makesmokeใหม่. Documentchecksไม่พิสูจน์behaviorหรือManualtests. การรับรองACcrosswalk/routeUS10/policyreadUS6/semanticsUS2/estimatesและreviewerต้องเป็นมติจริงของผู้รับผิดชอบ ไม่ใช่การอนุมัติอัตโนมัติจากเอกสารนี้
