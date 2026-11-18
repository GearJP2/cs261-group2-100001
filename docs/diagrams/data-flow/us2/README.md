# US2 — Search parties

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US2 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("2.1 Search parties"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D3[("D3 Sports, venues and opening hours")]
    D4[("D4 Parties, memberships and join requests")]
    U -->|"Search text, filters, pagination and session"| P
    P -->|"Matching parties, pagination or validation error"| U
    D3 -->|"Sports and venues"| P
    D4 -->|"Party records and active membership counts"| P
    D1 -->|"Account and applicable identity data"| P
    D2 -->|"Session identity"| P
```

ค้นหาและกรองข้อมูลไม่เปลี่ยน Party หรือที่นั่ง; ผลลัพธ์ไม่มีข้อมูลสมาชิกส่วนตัว

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/parties/search.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
