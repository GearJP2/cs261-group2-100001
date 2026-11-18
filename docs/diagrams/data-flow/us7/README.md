# US7 — Manage and view parties

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US7 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("3.3 / 2.3 Manage and view parties"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D3[("D3 Sports, venues and opening hours")]
    D4[("D4 Parties, memberships and join requests")]
    U -->|"Party details, create/edit/cancel submission or detail query, session"| P
    P -->|"Party detail, management result or validation error"| U
    D1 -->|"Host profile and verified identity"| P
    D3 -->|"Venue, sport and opening-hours constraints"| P
    D4 -->|"Party, membership and request records"| P
    D2 -->|"Session identity"| P
    P -->|"Created or updated Party; Host membership on creation"| D4
```

Create สร้าง Host membership; Edit/Cancel จำกัด Host; การอ่าน Detail ไม่เขียนข้อมูล โดยมุมมองนี้รวมทั้ง process 3.0 และ 2.0

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/parties/services.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
