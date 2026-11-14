# Task Backlog — UniSport Buddy

> **Sprint 2:** ใช้ [Task44 — scope/AC/API/dependency matrix](sprint-2-planning-contract.md) ตรวจงานปัจจุบันร่วมกับGitHub Issues. คำว่าbacklog/ยังไม่เลือกและassigneeในรายการเดิมด้านล่างเป็นแผนSprint1 ไม่ใช่คำตัดสินว่าUS10/US6/US4/US2/US14อยู่นอกSprint2. ข้อขัดแย้งrouteUS10และsemanticsUS2ยังต้องให้เจ้าของรับรองตามdecision log

รูปแบบงาน: `ชื่อ us-เลข [ประเภท] ชื่อหัวข้อ` ตามที่ทีมกำหนด ตามด้วยรายละเอียดและรหัส task เพื่อเชื่อม Issue/PR

- Story/Priority/Estimate: [User Stories](user-stories.md)
- ผู้รับผิดชอบและสถานะ Sprint ปัจจุบัน: [Sprint 1 Checklist](sprint-1-checklist.md)
- API contract, DB ขั้นต่ำ, transaction และ task ย่อยของ Sprint 1: [Technical Plan](sprint-1-technical-plan.md)

ชื่อหน้ารายการคือผู้รับผิดชอบหลัก ส่วนผู้ช่วยใช้ตาราง Sprint; กอล์ฟกับพีเป็นคู่ Backend, วีกับเนทดูหน้าเว็บ, โกลนำฐานข้อมูล, ออสตินดูหน้าสนาม/ทดสอบ และเกียร์ช่วยทุกส่วน งานนอก Sprint ใช้ “รอจัดทีม” เพื่อไม่ผูกคนล่วงหน้า

**Scope ที่เลือก:** US1/3/7/8/9 รวม 22 points งาน US อื่นด้านล่างอยู่ใน backlog เท่านั้น ทุก checkbox เริ่มยังไม่เสร็จ Endpoint ของงานนอก Sprint เป็นแบบเสนอ ไม่ใช่ contract ที่ทีมรับรองแล้ว

**กติกา Join ตาม task ฉบับที่แก้:** US3 → Pending โดยไม่เพิ่มสมาชิก; US10 → Approved จึงเพิ่มสมาชิก/ลดที่ว่าง; US13 ใช้ flow เดียวกัน จุดขัดกับ Scenario ต้นทางบันทึกใน User Stories แล้ว

การติ๊ก `[x]` หมายถึง task ผ่าน review และตรวจรับแล้ว ถ้า parent มี task ย่อยใน Technical Plan ให้ปิดเมื่อย่อยครบและเชื่อมจริงแล้ว กรอกสถานะ/กำหนดส่ง/Issue/PR ใน Sprint Checklist สำหรับงานที่เลือก อย่าเปลี่ยน scope เพียงเพราะพบงานในไฟล์นี้

## us-1 — เลือกใน Sprint 1

- [ ] **วี us-1 [Design] ออกแบบ Login และ Logout** — `US1-D`

  รายละเอียด: ทำ Figma หน้า Login/loading/error/Logout; เกียร์กับพีตรวจ provider/protocol ที่มหาวิทยาลัยอนุญาตและหลักฐานสิทธิ์นักศึกษา ก่อนสรุปว่าจะใช้ช่อง Username/Password หรือปุ่มไปหน้า SSO

- [ ] **พี us-1 [Backend] เชื่อมการยืนยันบัญชีและสร้าง Session** — `US1-B`

  รายละเอียด: ทำ login entry/callback ตาม protocol จริง, ตรวจตัวตนและสิทธิ์นักศึกษา, ผูก UniversityIdentity ด้วย unique provider/subject, สร้าง session และ GET /api/v1/me; POST /api/v1/auth/logout ยกเลิก server session; โกลทำ mapping/migration; ไม่เก็บรหัสผ่านมหาวิทยาลัย รายละเอียด AUTH-01–04 และ 11 task ย่อยอยู่ใน Technical Plan

- [ ] **วี us-1 [Frontend] พัฒนา Login และเชื่อม flow ยืนยันตัวตน** — `US1-F`

  รายละเอียด: เชื่อม contract ที่ยืนยันแล้ว แสดง error เมื่อข้อมูลผิด/ไม่มีสิทธิ์ ไปหน้าหลักเมื่อผ่าน และมีปุ่ม Logout; ใช้ session ร่วมกับทุกหน้า ไม่เก็บ credentials/token ใน localStorage

- [ ] **ออสติน us-1 [Testing] ทดสอบ Login และ Logout** — `US1-T`

  รายละเอียด: ทดสอบสอง Scenario ของทีมด้วยบัญชีถูก/ผิดและ UAT ร่วมกับผู้ตรวจรับ; เกียร์ช่วย session expiry/logout/ไม่มีสิทธิ์/ผล provider ปลอม; mock ผ่านไม่เท่ากับเชื่อมมหาวิทยาลัยจริงผ่าน

## us-2 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-2 [Design] ออกแบบ Home/Search และตัวกรอง** — `US2-D`

  รายละเอียด: ทำ Search bar, กีฬา, สนาม/ประเภทสถานที่ และวันเวลา พร้อม empty/loading/error; แยกกีฬา Badminton/Basketball ออกจาก Indoor/Outdoor และตกลงนิยามช่วงเวลาก่อนพัฒนา

- [ ] **รอจัดทีม us-2 [Backend] ทำ Query และ API ค้นหา Party** — `US2-B`

  รายละเอียด: เสนอ GET /api/v1/parties?q=...&sport_id=...&venue_id=...&venue_type=...&starts_from=...&starts_to=...&page=1&page_size=20; รวมตัวกรองแบบ AND ตรวจเวลาพร้อม offset และ whitelist การเรียงลำดับ; กำหนดก่อนว่าจะค้นเฉพาะ Open หรือสถานะอื่นด้วย; โกลช่วย index sport_id/starts_at และ field venue_type ถ้าเลือกใช้

- [ ] **รอจัดทีม us-2 [Frontend] เชื่อมผลค้นหาและตัวกรอง** — `US2-F`

  รายละเอียด: ส่ง query จากหน้าหลัก แสดงการ์ด Party และ pagination; แสดงไม่พบผลตามเงื่อนไข และเปิดรายละเอียดด้วย Party ID; ถ้าค้นขณะพิมพ์ต้องกัน response เก่าทับผลใหม่

- [ ] **รอจัดทีม us-2 [Testing] ทดสอบค้นหาและกรองกิจกรรม** — `US2-T`

  รายละเอียด: เตรียม Party หลายกีฬา/สถานที่/เวลา; ตรวจแต่ละ filter และหลายเงื่อนไขพร้อมกัน, ขอบเขตวันเวลา, ไม่พบผล, pagination และค่าพารามิเตอร์ผิด

## us-3 — เลือกใน Sprint 1

- [ ] **เนท us-3 [Design] ออกแบบปุ่มขอเข้าร่วมและสถานะ Pending** — `US3-D`

  รายละเอียด: ทำปุ่ม/Modal Loading/Pending/เป็นสมาชิกแล้ว/เต็ม/เริ่มแล้ว/ยกเลิก/Rejected ให้ตรง API-02 และ API-07; สำเร็จหมายถึงส่งคำขอ ไม่ใช่เป็นสมาชิกแล้ว

- [ ] **พี us-3 [Backend] ส่งคำขอ Pending และป้องกันคำขอซ้ำ** — `US3-B`

  รายละเอียด: ทำ POST /api/v1/parties/{id}/join-requests และ GET /api/v1/parties/{id}/join-requests/me; ล็อก Party ใน transaction ตรวจ session/state/capacity/member/คำขอเดิม; insert JoinRequest(Pending) โดยไม่เปลี่ยน Membership; โกลทำ unique(party_id,user_id)

- [ ] **เนท us-3 [Frontend] เชื่อมคำขอเข้าร่วมและคืนสถานะหลัง reload** — `US3-F`

  รายละเอียด: โหลด Party และคำขอของตน ปิดปุ่มระหว่างส่ง แสดง Pending เมื่อสำเร็จและหลังเปิดหน้าใหม่; error/network timeout ให้โหลดสถานะจริงก่อน retry ไม่หักที่ว่างเอง

- [ ] **ออสติน us-3 [Testing] ทดสอบคำขอซ้ำและกฎ Pending** — `US3-T`

  รายละเอียด: ส่งพร้อมกันจาก user เดียวต้องมีคำขอหนึ่งแถว; คนละ user ขอเมื่อเหลือหนึ่งที่ได้หลาย Pending โดยสมาชิก/ที่ว่างคงเดิม; ตรวจเต็ม/เริ่ม/ยกเลิก/member เดิม/login/สิทธิ์; concurrency แย่งอนุมัติที่ว่างสุดท้ายอยู่ US10

## us-4 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-4 [Design] ออกแบบถอนตัวและหน้าต่างยืนยัน** — `US4-D`

  รายละเอียด: มีปุ่มถอนตัวและ Confirm/Cancel พร้อมเหตุผลเมื่อกิจกรรมเริ่ม/จบแล้ว; ตกลงว่า Host ต้องใช้ยกเลิก Party แทนการถอนตัวหรือไม่

- [ ] **รอจัดทีม us-4 [Backend] ถอนสมาชิกและคืนที่ว่างใน transaction** — `US4-B`

  รายละเอียด: เสนอ POST /api/v1/parties/{id}/leave; user จาก session, ล็อก Party, ตรวจ active membership/เวลา แล้ว set left_at เพียงครั้งเดียว; ที่ว่างคำนวณจากสมาชิก active; เมื่อมีแชทต้องเพิกถอนสิทธิ์การเชื่อมต่อด้วย

- [ ] **รอจัดทีม us-4 [Frontend] เชื่อมถอนตัวและอัปเดตหน้า Party** — `US4-F`

  รายละเอียด: เรียก API หลังยืนยัน ปิดปุ่มกันซ้ำ โหลด member_count/remaining_slots ใหม่และอัปเดตรายการของตน; ถ้ามีแชทแล้วให้ซ่อนส่วนที่หมดสิทธิ์

- [ ] **รอจัดทีม us-4 [Testing] ทดสอบเวลาถอนตัวและการคืนที่ว่าง** — `US4-T`

  รายละเอียด: ก่อนเริ่มสำเร็จ, เริ่ม/จบแล้วไม่ได้, Cancel ไม่ยิง API, ถอนซ้ำไม่คืนซ้ำ, non-member ทำไม่ได้ และถอนแข่งกับอนุมัติยังไม่เกิน capacity

## us-5 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-5 [Design] ออกแบบ Recommended Users** — `US5-D`

  รายละเอียด: ทำการ์ดชื่อ/รูปที่มี/กีฬาที่สนใจ พร้อม loading/empty/error และลิงก์โปรไฟล์; ปุ่ม Invite ทำเมื่อเชื่อม US13 ไม่เพิ่มระบบเชิญซ้ำ

- [ ] **รอจัดทีม us-5 [Backend] คัดเลือกและส่งผู้ใช้ที่แนะนำ** — `US5-B`

  รายละเอียด: เสนอ GET /api/v1/users/recommendations?page=1&page_size=20; ใช้ UserSportInterest หรือประวัติ PartyMembership ที่ร่วมกันตามกฎทีม; ไม่แนะนำตัวเอง/ซ้ำ/inactive และส่งเฉพาะ public fields

- [ ] **รอจัดทีม us-5 [Frontend] แสดงคำแนะนำและเปิดโปรไฟล์** — `US5-F`

  รายละเอียด: เชื่อม API แสดงการ์ดและสถานะไม่มีข้อมูล เปิด US8 ได้; ถ้ารับปุ่มเชิญให้ส่งต่อ flow US13 หลังมี Party/สิทธิ์เชิญที่ถูกต้อง

- [ ] **รอจัดทีม us-5 [Testing] ทดสอบความเกี่ยวข้องของผู้ใช้ที่แนะนำ** — `US5-T`

  รายละเอียด: ตรวจ shared interest/เคยเล่นร่วมกันตามกฎ, ไม่แนะนำตัวเองหรือซ้ำ, ข้อมูลว่าง/inactive และ response ไม่เปิดเผยข้อมูลลับ

## us-6 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-6 [Design] ออกแบบรายชื่อและป้าย Host/Member** — `US6-D`

  รายละเอียด: ทำส่วนรายชื่อในหน้ารายละเอียด Party แสดงชื่อ/รูปที่มี/บทบาทชัดเจน; กดชื่อเปิด US8 ได้เมื่อมี feature

- [ ] **รอจัดทีม us-6 [Backend] อ่านสมาชิกปัจจุบันพร้อมบทบาท** — `US6-B`

  รายละเอียด: เสนอ GET /api/v1/parties/{id}/members แบบแบ่งหน้า; query Membership left_at IS NULL, role จาก host_id; ไม่รวม Pending/Rejected; ตกลงสิทธิ์อ่านก่อน implement

- [ ] **รอจัดทีม us-6 [Frontend] เชื่อม Member List และอัปเดตหลังเปลี่ยนสมาชิก** — `US6-F`

  รายละเอียด: แสดงรายชื่อและบทบาทจาก API โหลดใหม่หลัง US10 อนุมัติ/US4 ถอนตัว; ไม่ถือ Pending เป็น Member

- [ ] **รอจัดทีม us-6 [Testing] ทดสอบรายชื่อครบและบทบาทถูกต้อง** — `US6-T`

  รายละเอียด: ตรวจ Host 1 คน/สมาชิกปัจจุบันครบ, ไม่มี Pending/Rejected/left member, pagination และอัปเดตหลังอนุมัติ/ถอนตัว รวมสิทธิ์และ public fields

## us-7 — เลือกใน Sprint 1

- [ ] **วี us-7 [Design] ออกแบบ Edit/Cancel Party และ API Contract** — `US7-D`

  รายละเอียด: ทำ Figma ฟอร์มแก้ไข/Confirm Cancel; กอล์ฟกำหนด PATCH /api/v1/parties/{id} และ POST /api/v1/parties/{id}/cancel พร้อม allowed fields/error ตาม API-08/09

- [ ] **กอล์ฟ us-7 [Backend] ตรวจ Host และบันทึกแก้ไข/ยกเลิก Party** — `US7-B`

  รายละเอียด: ล็อก Party และตรวจผู้กระทำจาก session; PATCH รวมค่ากับของเดิมแล้วตรวจ US9 schedule, field allowlist และ capacity ไม่ต่ำกว่าสมาชิก; Cancel set cancelled_at หยุดรับคำขอ, ยิงซ้ำคืนค่าเดิม; ไม่ลบประวัติ

- [ ] **วี us-7 [Frontend] พัฒนาฟอร์มและเชื่อม Edit/Cancel API** — `US7-F`

  รายละเอียด: โหลดค่าจาก API-02 ใช้ส่วนเลือกสนาม US9, แสดง validation error, ซ่อนเครื่องมือเมื่อไม่ใช่ Host; Cancel ต้องยืนยันและอัปเดตสถานะจาก Backend

- [ ] **ออสติน us-7 [Testing] ทดสอบการแก้ไข ยกเลิก และ Authorization** — `US7-T`

  รายละเอียด: Host ทำได้/Member เรียก API ตรงไม่ได้, ข้อมูลผิด/เวลาไม่เปิด/ลด capacity ไม่ผ่าน, ยกเลิกซ้ำไม่เปลี่ยนซ้ำ และ US3 ขอหลังยกเลิกไม่ได้; ทดสอบ race cancel/join/edit ตาม Technical Plan

## us-8 — เลือกใน Sprint 1

- [ ] **เนท us-8 [Design] ออกแบบ Profile Schema และหน้าจอ** — `US8-D`

  รายละเอียด: กำหนดชื่อ กีฬาที่สนใจ และเครดิตที่แสดงได้; Figma พร้อม null credit/no interests/not found; โกลกับพีตรวจ schema/allowlist

- [ ] **พี us-8 [Backend] ดึง Public Profile ตาม User ID** — `US8-B`

  รายละเอียด: ทำ GET /api/v1/users/{id}/profile (API-10), query UserProfile/UserSportInterest และส่งเฉพาะ public fields; ตรวจ session/404; ไม่คำนวณดาวหรือหักเครดิตใน Story นี้

- [ ] **เนท us-8 [Frontend] เชื่อม API และแสดงโปรไฟล์** — `US8-F`

  รายละเอียด: หน้า /users/{id} เปิดจากชื่อ Host ในหน้ารายละเอียดได้โดยไม่ต้องรอ US6; render ชื่อ กีฬา เครดิต พร้อม loading/error/not found

- [ ] **วี us-8 [Testing] ทดสอบ API และหน้าโปรไฟล์** — `US8-T`

  รายละเอียด: ตรวจหลาย user ID, ชื่อ/กีฬา/เครดิตตรงคน, null/no interests, ไม่ login/ไม่พบผู้ใช้ และ field ที่ส่งไม่มี password/session/token/ข้อมูลส่วนตัวลับ

## us-9 — เลือกใน Sprint 1

- [ ] **ออสติน us-9 [Design] ออกแบบหน้าสนามและส่วนเลือกสนาม** — `US9-D`

  รายละเอียด: Figma เลือกกีฬา/สนาม แสดงวันเวลาเปิด–ปิด และคำเตือน; เปลี่ยนกีฬาแล้วล้างสนามที่ไม่ตรง

- [ ] **โกล us-9 [Database] สร้างตารางกีฬา สนาม และเวลาเปิด–ปิด** — `US9-B1`

  รายละเอียด: สร้าง/ใช้ Sport ร่วมกัน, Venue(id,name,location_text,is_active), VenueSport unique(venue,sport), VenueOpeningHour(venue,weekday,opens_at,closes_at); check weekday 0–6 และ opens_at<closes_at, migration/seed; ไม่ทำ DB แยกจาก Party

- [ ] **กอล์ฟ us-9 [Backend] แสดงสนามและตรวจช่วงเวลานัดหมาย** — `US9-B2`

  รายละเอียด: ทำ GET /api/v1/sports, /venues?sport_id=... และ /venues/{id}/opening-hours (API-03–05); service validate_party_schedule ใช้ร่วมสร้าง/แก้ Party ตรวจกีฬา สนาม active และช่วงเริ่มถึงจบอยู่ในเวลาเปิดตามกติกาที่ทีมรับรอง

- [ ] **ออสติน us-9 [Frontend] เชื่อมสนามและเวลาเปิดกับฟอร์มนัดหมาย** — `US9-F`

  รายละเอียด: เชื่อม API ตามกีฬา→สนาม→เวลาเปิด ทำ component ใช้ใน US7 และหน้าสร้าง Party; กันเลือกช่วงปิดและแสดง Backend error; ส่วนหน้าสร้างยังรอ Story ที่ทีมต้องกำหนด

- [ ] **เกียร์ us-9 [Testing] ทดสอบเวลาเปิด สนาม และการเรียก API ตรง** — `US9-T`

  รายละเอียด: กีฬา/สนามสัมพันธ์ถูกต้อง, นัดในช่วงเปิดผ่าน, วันปิด/ก่อนเปิด/หลังปิด/คร่อมช่วงพักไม่ผ่าน; ทดสอบเวลา boundary/timezone ตาม contract และเชื่อมทั้งการสร้าง/แก้เมื่อมีเจ้าของงานครบ

## us-10 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-10 [Design] ออกแบบรายชื่อ Pending และปุ่ม Approve/Reject** — `US10-D`

  รายละเอียด: แสดงเฉพาะ Host มี loading/empty/error และผลตัดสิน; ถ้าทีมรับเข้า Sprint ใช้วีตามข้อเสนอ Technical Plan

- [ ] **รอจัดทีม us-10 [Backend] ดึงคำขอเข้าร่วมเฉพาะ Host** — `US10-B1`

  รายละเอียด: เสนอ GET /api/v1/parties/{id}/join-requests?status=Pending&page=1&page_size=20 (OPT-API-11); ใช้ JoinRequest ชุดเดียวกับ US3 ไม่สร้าง request table ซ้ำ

- [ ] **รอจัดทีม us-10 [Backend] อนุมัติหรือปฏิเสธใน transaction** — `US10-B2`

  รายละเอียด: เสนอ POST /api/v1/parties/{id}/join-requests/{request_id}/decision body decision Approved/Rejected (OPT-API-12); ล็อก Party ก่อน Request ตรวจสิทธิ์/status/เวลา/ที่ว่าง/สมาชิกซ้ำ; Approved เพิ่ม membership และบันทึกคำตัดสินพร้อมกัน; Rejected ไม่เปลี่ยนสมาชิก

- [ ] **รอจัดทีม us-10 [Frontend] เชื่อม Approve/Reject และอัปเดตข้อมูล** — `US10-F`

  รายละเอียด: ปิดปุ่มระหว่างส่ง แสดง error จาก Backend แล้วโหลดคำขอ/member_count/remaining_slots ใหม่; ไม่ลดที่ว่างเองก่อนสำเร็จ

- [ ] **รอจัดทีม us-10 [Testing] ทดสอบสิทธิ์และอนุมัติที่ว่างสุดท้ายพร้อมกัน** — `US10-T`

  รายละเอียด: อนุมัติ/ปฏิเสธสำเร็จ, non-host/request ข้าม Party/ตัดสินซ้ำไม่ได้, เต็ม/เริ่ม/ยกเลิกอนุมัติไม่ได้; ใช้ PostgreSQL หลาย connection อนุมัติสองคำขอเมื่อเหลือหนึ่งที่แล้วมีสมาชิกเพิ่มได้เพียงหนึ่งคน

## us-11 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-11 [Design] ออกแบบค้นหาผู้ใช้ คำขอเพื่อน และ Friend List** — `US11-D`

  รายละเอียด: ออกแบบสถานะ Pending/Friend/ไม่มีคำขอ; โกลช่วยกำหนด friend request และ friendship พร้อม unique คู่ผู้ใช้และนโยบายคำขอสวนกัน/Reject

- [ ] **รอจัดทีม us-11 [Backend] สร้าง API ค้นหา ส่ง และตอบรับเพื่อน** — `US11-B`

  รายละเอียด: เสนอ GET /api/v1/users?q=..., POST /friend-requests, GET /friend-requests, PUT /friend-requests/{id} body Accepted/Rejected, GET /friends; ตรวจผู้รับเป็นคนตัดสิน ห้ามตัวเอง/ซ้ำ; Accepted บันทึกความสัมพันธ์หนึ่งคู่ที่อ่านได้ทั้งสองฝ่ายใน transaction

- [ ] **รอจัดทีม us-11 [Frontend] เชื่อม Add Friend และ Friend List** — `US11-F`

  รายละเอียด: ทำค้นหา ปุ่มส่ง แสดง Pending รายการรับคำขอ และ Accept/Reject; success โหลดความสัมพันธ์ล่าสุดของทั้งหน้าที่เกี่ยวข้อง

- [ ] **รอจัดทีม us-11 [Testing] ทดสอบคำขอและความสัมพันธ์เพื่อน** — `US11-T`

  รายละเอียด: ค้นหา/ส่ง/ยอมรับแสดงทั้งสองฝ่าย/ปฏิเสธไม่เพิ่มเพื่อน, ห้ามตัวเอง/ส่งซ้ำ/ตอบแทนผู้อื่น และทดสอบคำขอพร้อมกันตามนโยบาย DB

## us-12 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-12 [Design] ออกแบบ Unfriend และ Confirm/Cancel** — `US12-D`

  รายละเอียด: ใช้ Friend List ของ US11 ออกแบบปุ่มลบและยืนยัน; ใช้ schema friendship เดิม

- [ ] **รอจัดทีม us-12 [Backend] ลบความสัมพันธ์เพื่อนด้วยสิทธิ์ของผู้ใช้** — `US12-B`

  รายละเอียด: เสนอ DELETE /api/v1/friends/{friend_user_id}; ตรวจ friendship ที่มี current user เป็นฝ่ายหนึ่ง, ลบความสัมพันธ์ร่วมทั้งสองฝั่ง และกำหนดพฤติกรรมยิงซ้ำใน contract

- [ ] **รอจัดทีม us-12 [Frontend] เชื่อม Remove Friend** — `US12-F`

  รายละเอียด: ยิง DELETE เมื่อยืนยันเท่านั้น ลบรายชื่อหลังสำเร็จ; Cancel คงข้อมูล; error ให้คงหรือ reload ข้อมูลจริง

- [ ] **รอจัดทีม us-12 [Testing] ทดสอบการลบและสิทธิ์** — `US12-T`

  รายละเอียด: ลบแล้วหายทั้งสองฝ่าย, Cancel ไม่เปลี่ยนข้อมูล, non-party ลบไม่ได้, ส่งซ้ำตาม contract และไม่กระทบ friendship คู่อื่น

## us-13 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-13 [Design] ออกแบบ Invite Link และหน้าเปิดคำเชิญ** — `US13-D`

  รายละเอียด: ทำ Copy Link/Toast และหน้ารายละเอียดหลังเปิดลิงก์ มี login แล้วกลับหน้า Party; ขอบเขตแรกเลือกลิงก์ ส่วนค้น Friend List เป็นงานเพิ่มหากรับเข้ามา

- [ ] **รอจัดทีม us-13 [Backend] สร้างและตรวจ Invite Link** — `US13-B`

  รายละเอียด: เสนอ POST /api/v1/parties/{id}/invite-links สำหรับ Host/active Member, GET /api/v1/invites/{token} ตามสิทธิ์ที่กำหนด; เก็บ token digest/expiry/creator/party ตามนโยบายทีม; ลิงก์ไม่ให้สิทธิ์สมาชิกอัตโนมัติ ใช้ US3 สร้าง Pending

- [ ] **รอจัดทีม us-13 [Frontend] เชื่อมคัดลอกและเปิดลิงก์** — `US13-F`

  รายละเอียด: เชื่อมสร้างลิงก์/Clipboard, แสดงสถานะคัดลอกสำเร็จหรือผิดพลาด; เปิดแล้ว login ถ้าจำเป็น ไปหน้า Party และให้กดส่งคำขอ Pending ตาม US3

- [ ] **รอจัดทีม us-13 [Testing] ทดสอบลิงก์และการขอเข้าร่วม** — `US13-T`

  รายละเอียด: สิทธิ์สร้างลิงก์, copy/open/login redirect, token ผิด/หมดอายุ, Party เต็ม/เริ่ม/ยกเลิก/ขอซ้ำ; ไม่เพิ่มสมาชิกโดยข้าม US10

## us-14 — Backlog — ยังไม่เลือกเข้า Sprint 1

- [ ] **รอจัดทีม us-14 [Design] ออกแบบรีวิว ดาว และ No-show พร้อมกติกาคะแนน** — `US14-D`

  รายละเอียด: ทำ Figma 1–5 ดาว/ข้อความ/รายงาน; ระบุ eligible reviewers, ฐานนับเกณฑ์รายงาน, จำนวนเครดิตหัก, สูตร average_rating และ field conduct_credit แยกกันก่อนลงมือ

- [ ] **รอจัดทีม us-14 [Backend] บันทึกรีวิวและรายงานโดยไม่คำนวณซ้ำ** — `US14-B`

  รายละเอียด: เสนอ POST /api/v1/parties/{id}/reviews และ /no-show-reports; ตรวจ Completed/สมาชิกกิจกรรมเดียวกัน/ห้ามตัวเอง/ซ้ำ; DB unique review/report ต่อ party/reviewer/target และ unique penalty ต่อ party/target; คำนวณดาวและหักเครดิตใน transaction โดยกัน threshold race

- [ ] **รอจัดทีม us-14 [Frontend] เชื่อมให้คะแนนและรายงานหลังจบ** — `US14-F`

  รายละเอียด: แสดง form หลัง Completed ส่งข้อมูลแล้วแสดงผลจริง โหลดโปรไฟล์คะแนนดาว/เครดิตจาก Backend; ป้องกันกดซ้ำและแสดง error เมื่อไม่มีสิทธิ์

- [ ] **รอจัดทีม us-14 [Testing] ทดสอบรีวิวและการหักเครดิต** — `US14-T`

  รายละเอียด: ทดสอบดาวเฉลี่ย, ก่อนจบ/ตัวเอง/ข้าม Party/ส่งซ้ำไม่ผ่าน, รายงานจากสมาชิกไม่ซ้ำต่ำกว่า/ถึงเกณฑ์ และ threshold พร้อมกันหักได้ครั้งเดียวต่อ target ต่อกิจกรรม

## งานร่วมที่ต้องทำคู่กับ Story

Setup, ERD/schema, seed, error contract, Party state service และ integration ใช้รหัส BASE/INT ใน Sprint Checklist โดยไม่บวก points สมมติให้ Story เอง Story สร้าง Party ยังขาดจากรายการ US1–14 ให้ทีมกำหนดรหัสและ AC ก่อนเลือกเข้า Sprint

เวลาส่ง task ให้แนบ migration/API request-response/ภาพ UI/คำสั่งทดสอบตามประเภทงาน พร้อม PR และผลจริง ก่อนเปลี่ยนสถานะเป็น Done
