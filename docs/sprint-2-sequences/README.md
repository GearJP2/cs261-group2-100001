# Sprint 2 — Sequence Diagrams

ปรับย้อนหลัง 2026-11-14 จาก main `e0edf10` · [หน้ารวม diagrams](../diagrams/README.md) · [ผล audit และข้อแตกต่าง](../diagrams/sequence-audit/audit.md)

| Story | สถานะใน baseline | Source / Preview |
|---|---|---|
| US2 Search | Proposed filters; GET parties มี open-party list สูงสุด 50 แล้ว | [Mermaid](us2.mmd) / [SVG](us2.svg) |
| US4 Leave | Service implemented; HTTP endpoint/UI pending | [Mermaid](us4.mmd) / [SVG](us4.svg) |
| US6 Members | API implemented; Host or active member; UI integration pending | [Mermaid](us6.mmd) / [SVG](us6.svg) |
| US10 Decision | Backend implemented; current/target UI แยกในภาพ | [Mermaid](us10.mmd) / [SVG](us10.svg) |
| US14 Reviews | Backend/migrations merged; UI pending | [Mermaid](us14.mmd) / [SVG](us14.svg) |
| US14 No-show | Approved policy; default-off endpoint; UI pending | [Mermaid](us14-no-show.mmd) / [SVG](us14-no-show.svg) |

ภาพใช้ API prefix `/api/v1` ตาม routes จริง. Error ก่อนเข้า service ไม่เริ่ม domain transaction; write errors ภายใน atomic transaction ต้อง rollback ทั้งชุด. State ของ Party อ่านตามเวลาปัจจุบันหลังได้ lock ไม่ใช้ค่าจาก browser

## งานอ้างอิง

ผลตรวจรับ Backend US10: [B-01 Pending](../us10-b-01-test-report.md), [B-02 Approve](../us10-b-02-test-report.md), [B-03 Reject](../us10-b-03-test-report.md) — รายงานระบุ source/tests และข้อจำกัดของแต่ละรอบ; ไม่ใช่ผล browser UAT

Sequence issues เดิม #113–#117; รอบตรวจและปรับนี้ #147. Policy ถอนตัว: [US4](../us4-leave-party-policy.md); policy เครดิตปัจจุบัน: [US14 approved](../us14-no-show-approved-policy.md). Diagram ไม่ใช่หลักฐานว่า frontend/การเชื่อมภายนอกผ่าน UAT แล้ว
