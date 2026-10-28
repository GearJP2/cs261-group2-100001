# US9 — Browse venues and sports

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US9 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("2.5 Browse venues and sports"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D3[("D3 Sports, venues and opening hours")]
    U -->|"Sport or venue filters, venue identifier and session"| P
    P -->|"Sports, venues, opening hours or validation error"| U
    D3 -->|"Sport, venue associations and opening hours"| P
    D1 -->|"Account and applicable identity data"| P
    D2 -->|"Session identity"| P
```

API ตรวจ verified university user; ข้อมูลอ้างอิงถูก seed/import นอก user-facing flow นี้

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/venues/views.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
