# Sprint 2 demo runbook — Task97

ผู้ดำเนินที่เสนอ: Gear. เอกสารพร้อมใช้ แต่**ยังไม่บันทึกว่ามีการนำเสนอต่ออาจารย์หรือhumanUATแล้ว**. ใช้main `4fda705` ซึ่งรวมTask96; runtimefingerprintsตรงกับrunบน`d157487`

## เลือกรูปแบบและเตรียมก่อนนำเสนอ

**รูปแบบพร้อมใช้ทันที: evidence walkthrough6–8นาที** เปิดภาพ/รายงาน/HTTP/SQLที่บันทึกจริงในTask96. พูดว่าเป็นผลautomatedrehearsal ไม่แกล้งคลิกภาพนิ่งหรืออ้างเป็นliveTUlogin

ถ้าต้องการ**automated replay** ให้ใช้[คำสั่งและguardในTask96](../evidence/task96-cross-story/README.md#reproduction--isolation): dedicatedComposeproject `s2-task96-cross`, DBprefix `s2_task96_`, ports25896/25496, test-onlyenv, Playwright/Chromium. ใช้outputใหม่ทุกครั้ง ห้ามชี้DBทีม; runnerสลับNo-showเฉพาะtestbackendและคืนfalse. Scriptเป็นheadlessautomation ไม่ใช่การให้ผู้เข้าชมloginด้วยTUจริง

ก่อนเริ่มตรวจว่าลิงก์ต่อไปนี้เปิดได้: [summaryPNG](../evidence/task97-review/summary.png), [expected/actualCSV](../evidence/task96-cross-story/execution.csv), [rawHTTP/SQL](../evidence/task96-cross-story/run/results.json), [717-test log](../evidence/task96-cross-story/verify.log). ใช้rolealiases/ข้อมูลสังเคราะห์ ไม่แสดงcookies/TUkey/credentials

## ลำดับนำเสนอ

| เวลาโดยประมาณ | สิ่งที่แสดง / คำอธิบาย | Expectedที่พิสูจน์ได้ / หลักฐาน |
| --- | --- | --- |
| 0:00–0:45 | เป้าหมาย5Storiesและrevisionรวมเดียว | 19cross-storyscenarios; ตัวเลข717/40เป็นautomationคนละชั้น ไม่บวกรวมเป็นจำนวนmanualcases |
| 0:45–1:30 | ค้นหา→Detail→Pending | [ภาพPending](../evidence/task96-cross-story/run/pending-no-seat.png), F02: HTTP201, SQLHostcount1/ที่ว่าง2 ไม่กินที่ก่อนapprove |
| 1:30–2:30 | Hostapprove/reject→Members | F03–F05: Approveเพิ่มสมาชิก, Rejectไม่เพิ่ม, countเต็ม3และoutsiderjoin409; ดูHTTPและSQLที่IDsเดียวกัน |
| 2:30–3:30 | Leave→คืนที่→กลับเข้าร่วม | [ภาพLeave](../evidence/task96-cross-story/run/leave-restores-slot.png), F06–F08: softleave/403ล้างprivate, retryไม่แก้ซ้ำ, rejoinอนุมัติใหม่/reusemembershipID |
| 3:30–4:30 | หลังจบจึงreviewและดูProfile | [review](../evidence/task96-cross-story/run/completed-review.png), [profile](../evidence/task96-cross-story/run/profile-review-summary.png), F10–F13: ก่อนจบ409, หลังfixturetransition201/cache5/1, duplicate409, profile5.0 |
| 4:30–5:15 | No-showแยกจากดาว | F14–F16: off404, testflagเปิด→สองreporters→เครดิต95ครั้งเดียว, ดาวไม่เปลี่ยน, คืนflagfalse. ส่วนนี้แสดงAPI/SQL ไม่อ้างว่ามีNo-showUI |
| 5:15–6:00 | Regression/raceและข้อจำกัด | R01/R02/R03: sessionguards/create-edit-cancel/logout; 717testsรวมactualPostgreSQLraces, liveTU/humanUAT/loadNotrun |
| 6:00–7:00 | Reviewและretrospective | [Retrospective](sprint-2-retrospective.md): Frontendช้ากว่าเป้าสัปดาห์แรก/งานกระจุกท้าย/ต้องเก็บคุณภาพ ส่วนอื่นGearประเมินโอเค; actionยังรอทีมรับรอง |
| 7:00–8:00 | คำถาม/จุดที่ผู้ตรวจอยากดู | เปิดcase IDและSQLbefore-afterที่ขอ ไม่สรุปทุก101plannedcasesผ่านจากCI |

## ข้อความเปิดและข้อจำกัดที่ต้องพูด

> รอบนี้สาธิตหลักฐานที่รันจริงบนระบบรวมของ Sprint2 ใช้บัญชีทดสอบสังเคราะห์เพื่อแยกบทบาทHost/Member/ผู้ไม่มีสิทธิ์ การยืนยันตัวตนกับTUจริงยังไม่ได้รันในenvironmentนี้ ทุกผลมีcommitและHTTP/SQLอ้างอิง

ก่อนแสดงreviewให้อธิบายว่าrunnerเปลี่ยนเวลาของsyntheticPartyให้Completedเพื่อจำลองเวลาที่ผ่านไป ไม่ได้รอวันจริงและไม่ได้ทดสอบAPIแก้เวลาหลังจบ. ภาพหน้าจอเป็นหลักฐานประกอบ ต้องเปิดexpected/actualและnetwork/SQLด้วย

## Fallbackและหลักฐานหลังนำเสนอ

- ถ้าไม่มีTUprovider: ใช้evidencewalkthroughและระบุliveTUNotrun ไม่เปลี่ยนเป็น“loginมหาวิทยาลัยผ่าน”
- ถ้าreplayรันไม่จบ: เก็บfailurelog/commit/envและรายงานFail/Notrunตามจริง ใช้รายงานรอบเดิมที่ระบุcommitเป็นfallback ไม่แก้ผลรอบใหม่ให้ผ่าน
- หลังเดโมจริงจึงเติมวัน/ผู้ดำเนิน/ผู้ตรวจ/ผลรับงานและคำถามจากผู้ตรวจในissue112. ปัจจุบันยังไม่กรอกชื่อผู้เข้าชมหรือผลhumanUATย้อนหลัง
- รอบนี้ไม่มีคำสั่งdeploy/productionflag; cleanupเฉพาะtestprojectตามTask96เมื่อเสร็จ
