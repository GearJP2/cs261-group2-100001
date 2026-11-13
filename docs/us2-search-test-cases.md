# US2 — Search test cases สำหรับ Design #91

อ้างอิง [semantics และ contract](us2-search-design.md) ทุกเคส **Not run**; คนหลัก Golf ผู้ตรวจที่รอ Austin
AC mapping ใช้ [sequence checklist](sprint-2-sequences/README.md#us2--ค้นหา) เป็น working mapping: AC1 AND, AC2 sport/venue type แยกกัน, AC3 เวลา, AC4 UI states, AC5 state/Detail ต้องยืนยันกับ Story ต้นทางก่อนปิดงาน

## Fixtures / วิธีตรวจ

reset ข้อมูลแต่ละเคส ใช้ now คงที่ N; มี Party ทุก state, หลายกีฬาและสนามที่รองรับหลายกีฬา, สนาม Indoor/Outdoor/null, active Host/Member รวมทั้ง Pending/Rejected/left ที่ต้องไม่นับ
เวลาทดสอบใช้ N=2030-11-19T12:00:00+07:00 และช่วง A=2030-11-20T00:00:00+07:00 ถึง B=2030-11-21T00:00:00+07:00; ใส่ Party ที่ A−1 microsecond, A, B−1 microsecond และ B พร้อม Party เริ่มก่อน A แต่ ends_at หลัง A
จัดข้อมูล >100 รายการ มีหลาย Party ที่ starts_at เท่ากันเพื่อพิสูจน์ pagination/tie order; session ผ่าน university guard เว้น auth cases
D07 ยังไม่มี field จริง ต้องเตรียม migration/fixtures หลังมติยืนยัน ไม่ใช้ข้อมูล REAL/MOCK หรือเดาจากชื่อสนาม

| ID | AC | ขั้นตอน | ผลคาดหวัง |
| --- | --- | --- | --- |
| S01 | 1 | GET ไม่ส่ง query | 200 เฉพาะ Open, page1 size20, total นับก่อนแบ่งหน้า |
| S02 | 1,2 | sport_id/venue_id/venue_type แยกตัวและรวมกัน | ผลแต่ละตัวถูกต้อง; รวมแล้วตรงทุกเงื่อนไข AND ไม่ใช่ OR |
| S03 | 1,2 | sport กับ venue ที่ไม่รองรับกัน; IDs รูปแบบถูกแต่ไม่มีจริง | 200 data=[] ไม่เปลี่ยน filter และไม่คืน 404 |
| S04 | 2 | สนามเดียวรองรับหลายกีฬา และหลายสนามมีกีฬาเดียวกัน | sport filter ไม่เท่ากับ venue/type filter; ไม่ duplicate Party หรือคูณ active count |
| S05 | 2 | venue_type Indoor/Outdoor และไม่กรอง | enum ตรงประเภทจริง; null ไม่ตรงสอง enum แต่แสดงได้เมื่อไม่กรอง type |
| S06 | 3 | starts_from=A, starts_before=B | รวมเริ่มที่ A/B−1 microsecond; ไม่รวม A−1 microsecond/B; กิจกรรมที่ overlap แต่เริ่มก่อน A ไม่เข้า |
| S07 | 3 | ส่งขอบล่างอย่างเดียว/ขอบบนอย่างเดียว | ใช้ >= ขอบล่าง หรือ < ขอบบน ตามลำดับ |
| S08 | 3 | ส่งวันจาก UI และ instant เดียวกันใน +07:00/Z | ช่วงเท่ากัน ผลเหมือนกัน; UI ใช้วัน Bangkok แม้ browser timezone ต่างกัน |
| S09 | 3 | ช่วงเท่ากัน/กลับด้าน/date-only/ไม่มี offset/วันที่ไม่มีจริง | 400 INVALID_INPUT พร้อม fields ไม่ใช่รายการว่าง |
| S10 | 5 | state แต่ละค่าและ all โดยใช้ fixture ทุกสถานะ | เฉพาะ state นั้น; all ยังใช้ AND filters อื่น; state/count ตรง Detail ที่ now เดียวกัน |
| S11 | 5 | เวลา ณ starts_at/ends_at; cancelled ที่เลย ends_at | InProgress/Completed ตามลำดับ; cancelled ชนะเวลาเสมอ |
| S12 | 5 | Full, Pending/Rejected/left และ Host | Full คิดจาก active รวม Host เท่านั้น; ไม่เอา request หรือ left มานับ |
| S13 | 1 | q แบบต่าง case/substring/มีช่องว่างหัวท้าย/ภาษาไทย | trim แล้ว title icontains; ไม่ค้น description/ชื่อกีฬา/ชื่อสนามโดยอัตโนมัติ; รวม AND กับ sport |
| S14 | 1 | q ว่าง/ยาว100/ยาว101 หลัง trim | ว่างไม่กรอง, 100 ผ่าน, 101 ได้400 |
| S15 | 1 | page/page_size ปกติและ starts_at tie | ลำดับ starts_at,id; หน้าไม่ซ้ำ/หายเมื่อข้อมูลคงที่; total เดิมทุกหน้า |
| S16 | 1 | page เกินจำนวนหน้า/ไม่พบเลย | 200 data=[]; total เป็นจำนวนจริงหรือ 0 ตามกรณี |
| S17 | 1,2 | ID/page เป็น0/ลบ/ทศนิยม/ข้อความ, size101, enum case ผิด | 400 พร้อม fields ทุกกรณี; ไม่ clamp/ละเลยผิดเงียบ ๆ |
| S18 | 1 | unknown key/repeated key/empty value ที่ไม่ใช่ q | 400 พร้อม key ที่ผิด; empty q ยังคง no-op |
| S19 | 1,5 | anonymous/expired/inactive/identity ไม่ผ่าน | 401/403 ตาม guard; inactive ผ่าน session อาจ401 แยก direct guard ได้403 |
| S20 | 1 | GET ไม่มี CSRF; method อื่น; POST สร้าง Party เดิม | GET ที่มี session ใช้ได้; method อื่นได้405 Allow GET,POST เมื่อผ่าน guard/CSRF; POST คง contract เดิม |
| S21 | 1,5 | ตรวจ fields/privacy/header และ venue inactive | response มี data/page/page_size/total และ PartyData เดิม ไม่มีข้อมูลลับ; no-store; ไม่ซ่อน Party ของสนาม inactive โดยกฎใหม่ |
| S22 | 5 | สมาชิกถอน/Host approve/แก้เวลา Party ระหว่าง requests | refresh เห็น state/count จริง; GET ไม่ mutate/จองที่; join ยังตรวจ server อีกครั้ง |
| S23 | 4 | เปลี่ยน filters, sport, reset และไปหน้าใหม่ | ล้าง venue ที่ใช้ไม่ได้; filter/reset กลับ page1; reset คืน default Open; controls/URL ตรงกัน |
| S24 | 4 | response/error คำค้นเก่ามาถึงหลังคำค้นใหม่หรือ reset | ทั้ง stale result และ stale error ถูกละเลย |
| S25 | 4 | loading/empty/validation/network/5xx | มี state แยก; empty มี reset; error มีแก้ไข/retry ไม่แสดงผลเก่าว่าตรงคำค้นใหม่ |
| S26 | 4,5 | เปิดการ์ด Full/Started/Cancelled แล้วเข้า Detail | badge/ปุ่มตรง state; ไม่เปิด join อัตโนมัติ; Detail ตรวจข้อมูลปัจจุบัน |

S01–S22 ทดสอบ HTTP + PostgreSQL query integration ตามความเหมาะสม โดย CSRF tests เปิด checks จริง; S23–S26 เป็น browser tests
ตรวจ time boundary ด้วย controlled time ไม่ใช้ sleep; การเปลี่ยนข้อมูลข้ามหน้าไม่รับประกัน snapshot ตาม contract จึงไม่อ้างว่า offset pagination ป้องกันข้อมูลเปลี่ยนได้

## Checklist ก่อนส่งต่อ

- [ ] Austin ยืนยัน D01–D08 และ expected ของ S01–S26
- [ ] ยืนยัน AC numbering และ S2-PLAN-01 พร้อมหลักฐาน
- [ ] แนบ UI และตรวจชื่อ controls/query/timezone/reset/stale responses
- [ ] เตรียม venue_type migration และ fixtures ที่ได้รับการยืนยันก่อนรัน S05
- [ ] หลัง implement บันทึก environment, case ID, actual result, Pass/Fail และหลักฐานในงาน #98

ยังไม่มีผล runtime/browser/CI การออกแบบเคสไม่ใช่ผลทดสอบผ่านและไม่ใช่ review แทน Austin
