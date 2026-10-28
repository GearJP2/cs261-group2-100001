# US10 — Approve or reject requests

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US10 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("3.4 Approve or reject requests"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D4[("D4 Parties, memberships and join requests")]
    U -->|"Party identifier, pending query or request decision, session"| P
    P -->|"Pending applicants, decision result or error"| U
    D1 -->|"Applicant display names and verified Host identity"| P
    D4 -->|"Party Host, state, pending requests and membership count"| P
    D2 -->|"Session identity"| P
    P -->|"Request decision; created or reactivated membership on approval"| D4
```

เฉพาะ Host ตัดสิน Pending ได้; Approve ตรวจที่ว่างและเพิ่มสมาชิกใน transaction เดียว; Reject ไม่เพิ่มสมาชิก

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/parties/services.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
