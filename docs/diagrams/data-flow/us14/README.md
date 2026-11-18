# US14 — Reviews and no-show reports

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US14 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("4.0 Reviews and no-show reports"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D4[("D4 Parties, memberships and join requests")]
    D5[("D5 Reviews, no-show reports and credit events")]
    U -->|"Party/reviewee identifiers, rating/comment, report or reviews query, session"| P
    P -->|"Review list, rating summary, submission result or error"| U
    D1 -->|"Profile, identity, rating aggregates and credit balance"| P
    D4 -->|"Party timing and eligible participation"| P
    D5 -->|"Existing reviews, reports and credit events"| P
    D2 -->|"Session identity"| P
    P -->|"Review or no-show report; credit event when threshold is met"| D5
    P -->|"Rating aggregates or credit balance"| D1
```

Review กับ No-show เป็นคนละ flow ภายใน US14: review เปลี่ยน rating_sum/rating_count; no-show หัก credit เมื่อครบ threshold โดยไม่เปลี่ยนดาว และต้องเปิด NO_SHOW_ENABLED ก่อน (ค่าเริ่มต้น false)

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/conduct/services.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
