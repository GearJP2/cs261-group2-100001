# Test Case / Execution template

ใช้ร่วมกับ [scope](README.md) และ [inventory](sprint-2-cases.csv). คัดลอกต่อ case+variant+execution เก็บ raw log แยก อย่าแก้หลักฐานเก่า

| Field | ค่าเมื่อเริ่มออกแบบ |
|---|---|
| TC ID / Variant | QA-USx-LAYER-nn / variant |
| Story / PLAN AC / Original ID | ระบุทั้งcrosswalkและรหัสเคสต้นทางถ้ามี |
| Purpose / Layer | พฤติกรรมเดียว; UNIT / UI / API / DB |
| Planned method | mock-only / human browser / manual networkHTTP / Django test client / SQL / synchronized PostgreSQL automation |
| Owner / Reviewer | คนรับงานจริง; ยังไม่อนุมัติจนมีหลักฐาน |
| Preconditions / Fixtures | Role aliases→PKจริง, Party state/cap/count, clock/timezone, flag, session/CSRF |
| Steps / Inputs | ลำดับที่ทำซ้ำได้, URL/method/body หรือexactcommand, expected variants |
| Expected | status/body/fields, before-after rowcounts/history, no-write/error; ระบุoracle |
| Actual | เว้นว่างจนรันจริง |
| Result | Not run |
| Evidence | เว้นว่าง; หลังรันใส่log/screenshot/response/SQL path+case+timestamp |
| Tester / Executed at | เว้นว่าง; คนหรือagentที่รันจริง+เวลาtimezone |
| Tested commit / Environment | เว้นว่าง; commitจริง, OS/Python/Django/Postgres/browser, Composeproject/DBnameไม่รวมsecret |
| Bug / Retest of | เว้นว่าง; หลังพบbugใส่issueและexecutionก่อนหน้า |

Result allowed: Not run / Pass / Fail / Blocked. Pass=observedครบexpected, Fail=observedผิดexpected, Blocked=prerequisiteขัดขวางพร้อมหลักฐานและdependency, Not run=ยังไม่รัน. หนึ่งexecutionห้ามใช้เลขtestsผ่านรวมแทนผลcaseเฉพาะ

ห้ามเก็บpassword, application key, session/CSRFcookie/token หรือข้อมูลนักศึกษาจริงในevidence. Maskข้อมูลก่อนแนบโดยระบุสิ่งที่mask; ใช้syntheticfixtures. สำหรับserver500ไม่อ้างว่ามีJSONerrorเสมอถ้าcontractไม่รับรอง

## Bug / retest record

บันทึก observed vs expected, minimal reproduction, fixture/commit/env, severityตามผลกระทบจริง, issue/PRแก้. Retestรันcase+variantเดิมบนcommitแก้ใหม่ แล้วแนบactual/evidenceใหม่พร้อมลิงก์executionที่Fail; Regressionที่ได้รับผลกระทบแยกexecution. อย่าปิดbugจากCIpassโดยยังไม่ตรวจtriggerเดิม
