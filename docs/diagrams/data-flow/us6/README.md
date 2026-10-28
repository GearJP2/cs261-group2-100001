# US6 — View party members

[สารบัญ DFD](../README.md) · baseline `6eb6d35` · จัดทำย้อนหลัง 18 พฤศจิกายน 2026

## Data Flow Diagram Context

[Source](context.mmd)

```mermaid
flowchart LR
    E["E1 Student / Browser"]:::entity
    P0("0 — View party members"):::process
    E -->|"Party identifier and session"| P0
    P0 -->|"Member list, Host badge, count or access error"| E
    classDef entity fill:#fff4cc,stroke:#55a5b1,color:#243746
    classDef process fill:#eef7f8,stroke:#55a5b1,color:#243746
    classDef store fill:#e8ddf5,stroke:#9475bc,color:#243746
```

ผู้ใช้ส่ง Party identifier and session ระบบส่งกลับ Member list, Host badge, count or access error Process 0 รวมการตรวจสิทธิ์และข้อมูลภายในทั้งหมด จึงไม่แสดง data store ใน Context ไม่มีการเรียก TU API ใหม่ใน US นี้

## Data Flow Diagram Level 1

[Source](level-1.mmd)

```mermaid
flowchart TB
    E["E1 Student / Browser"]:::entity
    P1("1.0 — Check Session / Identity"):::process
    P2("2.0 — Resolve Party / Authorise"):::process
    P3("3.0 — Read Active Members"):::process
    P4("4.0 — Format Response / Error"):::process
    E -->|"Party identifier and session"| P1
    P1 -->|"Authenticated request data"| P2
    P2 -->|"Validated scope and request data"| P3
    P3 -->|"Result data or domain error"| P4
    P4 -->|"Member list, Host badge, count or access error"| E
    P1 -.->|"Authentication or input error"| P4
    P2 -.->|"Permission or validation error"| P4
    D1[["D1 — Accounts, identities, profiles and interests"]]:::store
    D2[["D2 — Django sessions"]]:::store
    D4[["D4 — Parties, memberships and join requests"]]:::store
    D1 -->|"Account / identity data"| P1
    D1 -->|"Display names and profile fallback data"| P3
    D4 -->|"Party Host and active memberships"| P3
    D4 -->|"Party and participation data for permission checks"| P2
    D2 -->|"Session identity"| P1
    classDef entity fill:#fff4cc,stroke:#55a5b1,color:#243746
    classDef process fill:#eef7f8,stroke:#55a5b1,color:#243746
    classDef store fill:#e8ddf5,stroke:#9475bc,color:#243746
```

### ขอบเขตและข้อกำกับ

เฉพาะ Host หรือ active Member ดูได้; Pending/Rejected/ผู้ถอน ไม่มีสิทธิ์จาก JoinRequest เพียงอย่างเดียว ไม่เขียนข้อมูล domain

ลูกศรแสดงข้อมูล ไม่ใช่การเรียกตามเวลา เส้นประแสดง error data ที่นำไปรวมเป็นผลตอบกลับ กระบวนการย่อย 1.0–4.0 เป็นเลขภายใน US นี้ ส่วน D1–D5 ใช้ความหมายเดียวกับ [data dictionary](../README.md#data-dictionary-และที่มาจากโค้ด) ของระบบ ไม่ใช่ห้าฐานข้อมูล

การอ่าน session และ identity รวมงาน middleware/decorator; กระบวนการอ่านและเขียนในภาพเป็น logical process ไม่ใช่ชื่อฟังก์ชันหนึ่งต่อหนึ่ง ผลสำเร็จและข้อผิดพลาดรวมอยู่ใน response เดียวกันทั้งสองระดับ รูป store ใช้สัญลักษณ์ Mermaid ประยุกต์

อ้างอิง [implementation](../../../../backend/parties/views.py) และ [authentication](../../../../backend/accounts/views.py) ภาพนี้ไม่แทนผลทดสอบ
