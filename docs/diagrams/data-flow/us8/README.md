# US8 — View profile

[กลับสารบัญ DFD](../README.md) · [Mermaid source](flow.mmd)

มุมมองข้อมูลเฉพาะ US8 จาก baseline `6eb6d35` จัดทำย้อนหลังวันที่ 18 พฤศจิกายน 2026 ใช้ D1–D5 ชุดเดียวกับภาพรวม ไม่ใช่ฐานข้อมูลใหม่หรือแผนภาพลำดับขั้นตอน

```mermaid
flowchart LR
    U["User: role permitted by this story"]
    P(("2.4 View profile"))
    D1[("D1 Accounts, identities, profiles and interests")]
    D2[("D2 Django sessions")]
    D3[("D3 Sports, venues and opening hours")]
    U -->|"Profile identifier and session"| P
    P -->|"Display name, interests, credit and rating summary or error"| U
    D1 -->|"Profile, interests, credit and rating aggregates"| P
    D3 -->|"Sport names"| P
    D2 -->|"Session identity"| P
```

ชื่อ public profile หมายถึงข้อมูลที่เปิดให้ผู้ใช้ที่ผ่าน authentication อ่าน ไม่ใช่ endpoint ที่ anonymous อ่านได้; ไม่มีการแก้ไข profile ใน US นี้

D1/D2 รวมข้อมูลตรวจสิทธิ์จาก middleware/decorator; ระดับสิทธิ์จริงต่างกันตาม endpoint ไม่ได้หมายถึงทุก flow ต้องยืนยัน TU ใหม่ ไม่มีการอ่าน store โดยตรงจาก browser ข้อผิดพลาดอยู่ในผลลัพธ์กลับผู้ใช้

อ้างอิง [implementation](../../../../backend/accounts/views.py), [routes และสิทธิ์ของบัญชี](../../../../backend/accounts/views.py) และ [data dictionary / ข้อจำกัด](../README.md#data-dictionary-และที่มาจากโค้ด) ภาพนี้เป็นเอกสาร ไม่ใช่หลักฐานว่ารันทดสอบใหม่
