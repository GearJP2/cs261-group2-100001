# US4 — Leave party

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US4 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("3.2 Leave party"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D4[("D4 Parties, memberships and join requests")]
    U -->|"Party identifier, leave submission and session"| P
    P -->|"Leave result or rejection reason"| U
    D4 -->|"Party timing, cancellation and own membership"| P
    D1 -->|"Account and applicable identity data"| P
    D2 -->|"Session identity"| P
    P -->|"Membership left_at"| D4
```

Host ถอนตัวไม่ได้; สมาชิกถอนก่อนเริ่มได้โดย soft leave; retry ไม่เปลี่ยน left_at เดิม

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/parties/services.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
