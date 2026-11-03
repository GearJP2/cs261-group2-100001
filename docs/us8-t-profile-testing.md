# US8-T-01 — ตรวจรับ Public User Profile

> ผลเพิ่มเติมวันที่ 21 ต.ค. 2026: ตรวจ Browser บน main `b6d4bd0` แล้ว ดูหัวข้อท้ายรายงาน
> ข้อความ “ยังรอ US8-F” ด้านล่างเป็นประวัติการตรวจวันที่ 18 ต.ค. ไม่ใช่สถานะล่าสุด

อ้างอิง [Issue #23](https://github.com/GearJP2/cs261/issues/23), [API-10 contract](us8-b-api.md) และ [Technical Plan](sprint-1-technical-plan.md) หัวข้อ 8

**ขอบเขตรอบนี้: Backend พร้อมรีวิว; Frontend/E2E ยังรอ US8-F** เริ่มบน `test/us-8-t-profile` จาก `main` commit `6bffd59` หลัง PR #39 ไม่แก้ API, schema, migration หรือ authentication policy ไม่ต้องรอ seed BASE-03 เพราะ tests สร้างข้อมูลใน test database แยกเอง

## ชุดตรวจ Backend

ไม่คัดลอก 9 tests ที่ US8-B มีแล้ว เพิ่ม acceptance regression 8 tests ใน `backend/accounts/test_profile_acceptance.py`

| เกณฑ์ตรวจ | หลักฐาน | สถานะ |
| --- | --- | --- |
| อ่านตนเอง/ผู้อื่นตาม User ID ไม่ใช่ Profile ID | `test_profile_api.py` | ผ่าน |
| สลับหลาย target และหลาย viewer, ชื่อเหมือนกันก็ไม่ปะปน | acceptance: `test_repeated_reads_across_targets_and_viewers_do_not_mix_profile_data` | ผ่าน |
| ไม่มี interests เป็น `[]`, credit เป็น `null` หรือ 0 ตามข้อมูลจริง | ชุดเดิมและ acceptance matrix | ผ่าน |
| User ไม่มีอยู่/ไม่มี Profile เป็น JSON 404 และ GET ไม่สร้าง Profile | ชุดเดิม | ผ่าน |
| ไม่มี session / inactive session / logout แล้วอ่านไม่ได้ | ชุดเดิม | ผ่าน |
| Session หมดอายุ / ถูกลบฝั่ง server ใช้ cookie เก่าอ่านไม่ได้ | acceptance: expired/server-revoked | ผ่าน |
| shared guard ปฏิเสธ authenticated inactive user เป็น 403 ก่อน query | acceptance: guard unit seam | ผ่าน |
| response keys ตรง allowlist ทั้งระดับ Profile และกีฬา | ชุดเดิม exact response และ acceptance matrix | ผ่าน |
| ไม่รั่วค่า username/email/password hash/provider/subject/session key | acceptance: private sentinel values | ผ่าน |
| อ่านหลังเปลี่ยนชื่อ/เครดิต/กีฬาได้ค่าล่าสุด | acceptance: fresh values | ผ่าน |
| GET ผ่านเมื่อเปิด CSRF enforcement; unsafe write ไม่มี token ถูกปฏิเสธและเครดิตไม่เปลี่ยน | acceptance: CSRF | ผ่าน |
| success/error เป็น JSON และ cache private/no-store; error ไม่ echo query | acceptance: response headers/error | ผ่าน |
| Query ไม่เปลี่ยน target/แก้ข้อมูล และ method อื่นแก้ Profile ไม่ได้ | ชุดเดิม | ผ่าน |

**ข้อจำกัดการยืนยันตัวตน:** tests ใช้ `force_login` ของ local Django accounts ไม่ได้ยืนยัน provider มหาวิทยาลัยหรือสิทธิ์นักศึกษาจริง ปัจจุบัน ModelBackend อ่าน inactive session เป็น anonymous จึงตอบ 401; กรณี 403 ใช้ RequestFactory ส่ง authenticated inactive user เข้า guard โดยตรงเพื่อทดสอบอีก branch ไม่ถือว่า HTTP session จริงตอบ 403

Cache headers เป็นหลักฐานของ HTTP contract เท่านั้น ไม่ได้พิสูจน์การล้าง state ใน Frontend หรือ browser back cache

## คำสั่งตรวจซ้ำ

```bash
docker compose run --rm -T backend python backend/manage.py test accounts.test_profile_api accounts.test_profile_acceptance --noinput --verbosity 2
make verify
```

ชุดโปรไฟล์รวม **17 tests** (เดิม 9 + เพิ่ม 8) รันบน PostgreSQL ไม่ใช้ข้อมูลมหาวิทยาลัยจริง ไม่เขียนข้อมูลลงฐานพัฒนา และไม่ต้องรัน seed ก่อน

ผลตรวจ local วันที่ 18 ตุลาคม 2569: ชุดโปรไฟล์ 17 tests ผ่าน; ชุดตรวจเทียบเท่า `make verify` ผ่าน Django system check, migration drift (No changes detected), Ruff lint/format และ regression ทั้งโปรเจกต์ **82 tests** บน PostgreSQL 17/Python 3.12 ไม่ใช่ผล CI หรือ Frontend UAT และไม่รวม tests ของ US9-B1/BASE-03 ที่ยังอยู่คนละ branch

## รอ US8-F: รายการตรวจหน้าเว็บ/E2E

รายการต่อไปนี้ยังไม่ผ่านการตรวจในรอบนี้ เพราะ branch ฐานยังไม่มีหน้า HTML `/users/{id}` และลิงก์จาก Host ที่เชื่อมครบ

- [ ] Login แล้วเปิด Party Detail และกดชื่อ Host ไป Profile ของ User ID ที่ถูกต้อง
- [ ] เปิด Profile ของผู้ใช้หลายคนต่อกัน; ชื่อ/กีฬา/เครดิตตรง API และไม่ค้างค่าคนก่อน
- [ ] แสดงกรณีไม่มี interests และ credit=null โดยไม่แต่งคะแนน; ค่า 0 ไม่หาย
- [ ] แสดง not found เมื่อ API ตอบ 404 และ error/retry เมื่อ network ล้มเหลว
- [ ] เมื่อ session หมดอายุ/logout/inactive ให้หยุดแสดงสถานะว่า login ใช้งานได้; redirect/return URL ตามข้อสรุป US1 โดยไม่รับ URL ภายนอก
- [ ] ตรวจ browser network/UI ว่าไม่แสดงข้อมูลลับ และไม่เก็บ session/token ใน localStorage

ใช้หลายบัญชี/fixture ที่ทีมอนุมัติเมื่อทดสอบ UI จริง และแนบผลพร้อม browser/วันที่/commit ลง PR

## ส่งรีวิว

PR รอบ Backend ให้ใช้ **`Refs #23`** และระบุว่ายังรอรายการ Frontend ข้างต้น ไม่ใช้ `Closes #23` จนกว่าจะตรวจ scope ทั้ง Issue ครบ งานย่อย Backend ที่พร้อมรีวิวสามารถอยู่ Testing ได้ แต่ไม่ถือว่า US8-T ทั้งงาน Done

## เพิ่มผล Browser — 21 ต.ค. 2026

โกลตรวจเพิ่มเติมบน branch `codex/us8-us7-browser-evidence` จาก main `b6d4bd0`;
Chrome ใน Codex in-app browser / Windows, PostgreSQL 17, Django 5.2.18, Python 3.12
ใช้ Docker project `cs261-evidence` และฐาน `evidence_browser` แยกจากข้อมูลพัฒนา
Login ผ่านฟอร์มจริง แต่จำลองเฉพาะ TU response ใน test harness จึงไม่ใช่ผล provider จริง

| กรณี | ผลจริง | ผล |
| --- | --- | --- |
| Login viewer → Home → Party → กดชื่อ Host | เปิด `/users/1/` ของ Host ถูกคน มีชื่อ กีฬา และ 75 คะแนน | Pass |
| สลับ target 1 → 3 → 4 → 1 | ชื่อ/คะแนน/กีฬาไม่ค้างจากคนก่อน | Pass |
| ไม่มี interests / credit=null | แสดง “ยังไม่ได้ระบุกีฬาที่สนใจ” และ “ไม่มีคะแนน” | Pass |
| credit=0 | แสดง “0 คะแนน” | Pass |
| User id ไม่มีอยู่ | หน้า “ไม่พบผู้ใช้”, HTTP log เป็น 404 | Pass |
| Session หมดอายุ | ปฏิเสธด้วย 401 AUTH_REQUIRED ไม่ส่ง HTML โปรไฟล์ | Pass ตาม guard |
| Logout จาก UI แล้วเปิดโปรไฟล์เดิม | 401 AUTH_REQUIRED | Pass |
| Viewer ถูกปิดใช้งานขณะถือ cookie เดิม | 401 AUTH_REQUIRED ตาม ModelBackend ไม่ใช่ 403 ทุกกรณี | Pass |
| Field ส่วนตัว | 17 API acceptance tests และ HTML tests ผ่าน; หน้า Browser แสดงเฉพาะ public fields | Pass ตามขอบเขตที่ตรวจ |

### หลักฐาน

- [ภาพ Host profile](evidence/browser-2026-10-21/us8-host-profile.jpg)
- [ข้อมูลว่าง](evidence/browser-2026-10-21/us8-empty-profile.jpg), [คะแนน 0](evidence/browser-2026-10-21/us8-zero-profile.jpg)
- [404](evidence/browser-2026-10-21/us8-not-found.jpg), [session หมดอายุ](evidence/browser-2026-10-21/us8-expired-session.jpg)
- [หลัง Logout](evidence/browser-2026-10-21/us8-after-logout.jpg), [inactive](evidence/browser-2026-10-21/us8-inactive-viewer.jpg)
- [Environment, harness, ข้อจำกัด และวิธีตรวจซ้ำ](evidence/browser-2026-10-21/README.md)
- [HTTP log](evidence/browser-2026-10-21/http-log.txt), [ผล Browser รายกรณี](evidence/browser-2026-10-21/browser-results.json)

รัน Backend/HTML regression พร้อม US7 บน main ฐานก่อน patch เวลา Edit:

```bash
docker compose -p cs261-evidence exec -T backend python backend/manage.py test accounts.test_profile_api accounts.test_profile_acceptance core.test_public_profile_page parties.test_us7_acceptance parties.test_creation parties.test_creation_api parties.test_editing parties.test_editing_api parties.test_editing_concurrency parties.test_cancellation parties.test_cancellation_api parties.test_management_api --noinput --verbosity 1
```

ผล **86 tests ผ่าน ไม่มี skip ใน 5.467 วินาที**; log อยู่ [backend-tests.txt](evidence/browser-2026-10-21/backend-tests.txt)
หลังแก้ JavaScript ของ US7 รัน `node --check frontend/static/js/app.js` ผ่าน และตรวจ Browser Edit ซ้ำ

### ข้อจำกัดและการส่งต่อ

- หน้า Profile ปัจจุบัน render HTML จาก Backend โดยตรง จึงไม่ทดสอบการ retry ของ client-side Profile API ที่หน้านี้ไม่ได้เรียก
- Session หมดอายุ/logout/inactive แสดง JSON 401 ตาม guard ไม่ redirect Login อัตโนมัติ:
  บันทึกเป็นข้อจำกัด UX ให้เจ้าของ UI ทบทวน ไม่อ้างว่าผ่านเงื่อนไข redirect ที่ยังไม่ได้ implement
- ไม่จำลอง network outage ของ navigation และไม่ได้อ่าน Browser storage ด้วย DevTools;
  ตรวจ source `app.js` ไม่พบ localStorage/sessionStorage และใช้ automated private-field tests แยก
- ผลชุดนี้ไม่ยืนยัน TU จริง, ทุก Browser หรือ Browser back-cache
- พร้อมให้รีวิวหลักฐานที่เพิ่ม; ยังไม่อ้างว่ารายงานรอบนี้ commit/push/merge หรือได้รับการตรวจรับโดยทีมแล้ว
