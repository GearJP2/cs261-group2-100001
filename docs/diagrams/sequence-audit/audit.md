# Sequence reconciliation — baseline e0edf10

วันที่ 2026-11-14 · Issue #147 · Scope: โค้ดที่ merge ใน main ณ baseline ไม่รวม PR ที่ยังเปิด

| US | สิ่งที่ตรวจพบ / ข้อสรุป | แหล่งยืนยัน |
|---|---|---|
| US1 | เพิ่ม login/eligibility/session/logout flow พร้อมกรณี TU ปฏิเสธและ timeout; ไม่อ้างการเชื่อมต่อจริงจากการวาดภาพ | accounts/views.py, services.py, decorators.py |
| US3 | เพิ่ม Pending/reopen/duplicate และ Party-first lock; แก้ความเข้าใจจาก scenario เก่าที่เพิ่มสมาชิกทันที โดยใช้กติกา Pending ที่ทีมตกลง | parties/services.py: submit_join_request; user-stories.md ส่วนข้อแตกต่าง |
| US7 | เพิ่ม create/edit/cancel และ atomic Host membership; การ cancel ซ้ำเก็บ timestamp เดิม | parties/services.py และ views.py |
| US8/9 | เพิ่ม read flow, guard, pagination และ no-store; ไม่มีการจองสนาม | accounts/views.py, venues/views.py |
| US2 | เก็บ proposed search diagram; แก้ README ที่เคยอ้างว่าไม่มี GET parties เพราะมี open-party list แล้ว แต่ filter ยังไม่ implement | parties/views.py: create_party_api |
| US4 | แทนภาพ proposed กว้าง ๆ ด้วย service จริง; already-left ตรวจ **ก่อน** cancellation/start; route/UI ยัง pending | leave_party, test_leave.py, PR #139 และ policy PR #136 |
| US6 | เอาป้าย API proposed ออก; ระบุ Host-or-active guard, actual active rows, fallback และ response fields; ไม่สังเคราะห์ Host row | party_members, can_view_members, member_data |
| US10 | แก้ membership get_or_create ในภาพเป็น lock-existing/create/reactivate ให้ตรง service; ไม่เปลี่ยน rule ที่ยืนยัน | decide_join_request |
| US14 reviews | เอาป้าย branches-only/migrations-not-merged ออก; คง validation/unique savepoint/F cache update | conduct/views.py, services.py, migrations |
| US14 No-show | เปลี่ยน proposal เป็น approved policy; คง default-off; เครดิตเริ่ม NULL ใช้ 100 แล้วหัก 5 ไม่มี opening ledger event | conduct/policy.py; us14-no-show-approved-policy.md; schema contract |

Sequence ของ US1/3/7/8/9 อยู่โฟลเดอร์นี้; US2/4/6/10/14 ใช้ source เดิมใน `docs/sprint-2-sequences` เพื่อลดสำเนาที่ขัดกัน

## ข้อจำกัด/ประเด็นที่คงไว้

- Diagram เป็นภาพอธิบาย ไม่แทน concurrency tests; SQL errors ต้อง rollback ตาม atomic boundary
- Policy US4 เดิมยังมี checklist Austin ไม่ติ๊ก แต่ PR #136 ได้อนุมัติ/merge โดย Gear; ไม่ติ๊กแทน Austin งานนี้ยึด policy ที่ implementation/test ใช้อยู่
- เอกสาร decision US14 เก่าอาจบันทึกข้อเสนอในอดีต; สำหรับเครดิตปัจจุบันใช้ approved-policy และ conduct/policy.py ไม่ตีความว่า draft เดิมยังเป็น blocker
- การ retry leave ข้ามรอบที่ถูก approve กลับแล้วไม่ใช่ idempotent ข้ามรอบ เป็นข้อจำกัดที่ policy ยอมรับไว้
- ไม่เติม US5/11/12/13 ซึ่งยังเป็น backlog ให้ดูเหมือนทำแล้ว; Search/UI/API ที่ pending มีป้ายชัดเจน
