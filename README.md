# UniSport Buddy — CS261

เว็บแอปพลิเคชันสำหรับหาเพื่อนออกกำลังกายและนัดหมายเล่นกีฬาในมหาวิทยาลัย พัฒนาเป็นโครงงานรายวิชา **CS261** ผู้ใช้สามารถสร้างกลุ่มกิจกรรม (Party) ระบุชนิดกีฬา สนาม วันเวลา และจำนวนคน เพื่อให้คนที่สนใจส่งคำขอเข้าร่วมและพูดคุยเตรียมตัวก่อนเล่นกีฬา

> **สถานะปัจจุบัน:** มี environment พัฒนาร่วมกันผ่าน Docker (Django + PostgreSQL), หน้าเริ่มต้น, health checks และ CI แล้ว ฟีเจอร์ตาม User Story รวมถึง Login มหาวิทยาลัยยังอยู่ระหว่างพัฒนา ดู [คู่มือ Development](docs/development.md) สำหรับวิธีรันและกติกาที่ทีมใช้ร่วมกัน

## เป้าหมายของโปรเจกต์

- ช่วยให้นักศึกษาหาเพื่อนที่สนใจกีฬาและว่างในช่วงเวลาเดียวกัน
- รวมข้อมูลนัดหมาย สถานที่ รายชื่อสมาชิก และจำนวนที่ว่างไว้ในที่เดียว
- จัดการการขอเข้าร่วม การอนุมัติ การถอนตัว และการยกเลิกกิจกรรมอย่างถูกต้อง
- มีพื้นที่สื่อสารภายใน Party พร้อมตรวจสอบสิทธิ์ผู้ใช้งาน

## ฟีเจอร์ที่วางแผนไว้

| ส่วนงาน | สิ่งที่ระบบจะทำ |
| --- | --- |
| บัญชีผู้ใช้และโปรไฟล์ | เข้าสู่ระบบผ่านช่องทางที่มหาวิทยาลัยอนุญาต แสดงโปรไฟล์และกีฬาที่สนใจ |
| ค้นหาและสร้าง Party | ค้นหาตามกีฬาและวันเวลา สร้างนัดพร้อมสถานที่ จำนวนคน และรายละเอียด |
| จัดการสมาชิก | ส่งคำขอเข้าร่วม ให้ Host อนุมัติหรือปฏิเสธ แสดงบทบาท Host/Member และถอนตัวก่อนกิจกรรมเริ่ม |
| จัดการกิจกรรม | Host แก้ไขหรือยกเลิก Party และผู้ใช้ดูรายการ Party ของตนเอง |
| ข้อมูลสนาม | แสดงสนามและเวลาเปิด–ปิด ตรวจสอบเวลานัดหมายก่อนสร้างหรือแก้ไข Party |
| แชทใน Party | สมาชิกปัจจุบันอ่านข้อความย้อนหลังและส่งข้อความแบบเรียลไทม์ |
| เพื่อนและคำเชิญ | ค้นหา เพิ่ม/ลบเพื่อน แนะนำผู้ใช้ และแชร์ลิงก์คำเชิญเข้าร่วม Party |
| รีวิวและความประพฤติ | รีวิวหลังจบกิจกรรม ให้ดาว และรายงานการไม่มาตามนัด โดยแยกคะแนนดาวออกจากเครดิตความประพฤติ |
| รายงานปัญหาและผู้ดูแล | รายงานผู้ใช้หรือ Party และให้ผู้ดูแลตรวจสอบและจัดการปัญหา |

ให้พัฒนากระบวนการสร้าง ค้นหา ขอเข้าร่วม อนุมัติ และถอนตัวให้ครบก่อน แล้วจัดลำดับฟีเจอร์อื่นในแต่ละ Sprint ตามเวลาที่มี

### กติกาสำคัญของ Party

อ้างอิงการทำงานร่วมกันของ `us-3`, `us-10` และ `us-13` ใน [รายการงาน User Story](user_story_tasks.txt):

1. การขอเข้าร่วมสร้างคำขอสถานะ `Pending` และ **ยังไม่ลดจำนวนที่ว่าง**
2. เมื่อ Host อนุมัติเป็น `Approved` จึงเพิ่มสมาชิกและลดจำนวนที่ว่าง โดยต้องตรวจสอบความจุอีกครั้ง
3. การปฏิเสธเป็น `Rejected` ไม่เพิ่มสมาชิกหรือเปลี่ยนจำนวนที่ว่าง
4. ผู้เข้าร่วมผ่านลิงก์คำเชิญต้องส่งคำขอและรออนุมัติเช่นเดียวกัน
5. การถอนตัวทำได้ก่อนกิจกรรมเริ่ม และต้องคืนที่ว่างเพียงครั้งเดียว
6. ต้องป้องกันสมาชิกซ้ำและการอนุมัติเกินความจุ แม้มีคำขอพร้อมกัน
7. ตรวจสิทธิ์ที่ Backend เสมอ รวมถึงสิทธิ์ Host และสิทธิ์อ่าน/ส่งแชทของสมาชิกปัจจุบัน

รายละเอียดส่วนนี้ใช้กติกาจากรายการงานล่าสุด ซึ่งปรับจากขั้นตอนเข้าร่วมโดยตรงใน Proposal เดิม ควรปรับเอกสาร Requirement และ Acceptance Criteria ให้ตรงกันเมื่อเริ่มงานที่เกี่ยวข้อง

## เทคโนโลยีที่เสนอ

Environment พัฒนาปัจจุบันใช้ Python 3.12, Django 5.2 และ PostgreSQL 17 ตามแนวทาง Python ของทีม ดูเวอร์ชัน dependency ที่ล็อกไว้ใน [requirements.txt](backend/requirements.txt) และข้อตกลงใน [Technical Plan](docs/sprint-1-technical-plan.md) ส่วน Redis/Channels จะเพิ่มเมื่อเริ่มงานแชท

| ส่วน | เทคโนโลยี |
| --- | --- |
| Backend | Python และ Django |
| หน้าเว็บ | Django Templates, HTML และ CSS แบบ Responsive |
| ฐานข้อมูล | PostgreSQL, Django ORM และ migrations |
| แชท | Django Channels, WebSocket และ Redis ผ่าน `channels_redis` |
| Application server | ASGI server เช่น Daphne |
| การยืนยันตัวตน | Django session ร่วมกับช่องทางบัญชีมหาวิทยาลัยที่ได้รับอนุญาต |

ต้องยืนยันกับอาจารย์เรื่องการใช้ JavaScript ฝั่งเบราว์เซอร์สำหรับการโต้ตอบและ WebSocket รวมถึงตรวจสอบช่องทางเชื่อมบัญชีมหาวิทยาลัยก่อนสรุปแบบระบบ ประวัติแชทจะเก็บใน PostgreSQL ส่วน Redis ใช้กระจายเหตุการณ์

## เอกสารใน Repository

คู่มือเริ่มงานทีม: [Branch ของแต่ละ task ใน Sprint 1](docs/sprint-1-branches.md) พร้อมผู้รับผิดชอบ คำสั่ง checkout/switch และลำดับ dependency

เอกสารออนไลน์ของทีม: [Google Docs](https://docs.google.com/document/d/1JvytQ4TXrWQEqkzPk6YXl5Ci0BnJPsIEcSdWhq6n2AY/edit?usp=sharing)

| เอกสาร | ใช้สำหรับ |
| --- | --- |
| [Sprint 2 Sequence Diagrams](docs/sprint-2-sequences/README.md) | US10/6/4/2/14 พร้อม SVG, Mermaid source, AC และ Test Case mapping |
| [Proposal v1.2 — Python](Project_Proposal_UniSport_Buddy_v1.2_Python.docx) | ภาพรวม เป้าหมาย ขอบเขต และแผนพัฒนาฉบับ Python |
| [Technical Constraints — Python](Technical_Constraints_UniSport_Buddy_Python.md) | ข้อกำหนดด้านเทคนิค สิทธิ์ แชท และเป้าหมายการทดสอบ |
| [User Story Tasks](user_story_tasks.txt) | รายละเอียดงาน Design, Backend, Frontend และ Testing พร้อมผู้รับผิดชอบที่ระบุไว้ |
| [Proposal v1.1](Project_Proposal_UniSport_Buddy_v1.1.docx) | ข้อเสนอรุ่นก่อนสำหรับดูที่มา |
| [Technical Constraints รุ่นเดิม](Technical_Constraints_UniSport_Buddy.md) | แนวทาง React/Node.js รุ่นก่อน ใช้ประกอบการเปรียบเทียบ |

เอกสารอาจยังมีรายละเอียดไม่ตรงกัน ให้ระบุข้อสรุปที่ทีมตกลงใน Issue และอัปเดตเอกสารที่เกี่ยวข้องใน Pull Request เดียวกัน

## เริ่มต้นทำงาน

1. Clone repository จาก URL ของโปรเจกต์ และเข้าโฟลเดอร์ `cs261`
2. อ่าน Proposal, Technical Constraints ฉบับ Python และ User Story ที่จะรับผิดชอบ
3. สร้างหรือรับ Issue ระบุขอบเขตงานและเงื่อนไขที่ใช้ตรวจรับให้ชัดเจน
4. อัปเดต `main` แล้วแตก branch ตามแนวทางด้านล่าง

### รันและทดสอบในเครื่อง

ต้องมีเพียง Git และ Docker Desktop หรือ Docker Engine ที่กำลังทำงาน พร้อม Docker Compose v2 เท่านั้น ไม่ต้องติดตั้ง Python, PostgreSQL หรือ Node.js เพิ่ม สำหรับ Windows แนะนำใช้ WSL2, เปิด Docker Desktop integration ให้ distro ที่ใช้ และเก็บ repository ไว้ใน filesystem ของ WSL

Clone repository และเตรียม environment จาก root ของ project:

```bash
git clone https://github.com/GearJP2/cs261-group2-100001.git cs261
cd cs261
git switch main
git pull --ff-only origin main
make init
```

`make init` สร้าง `.env` จาก `.env.example` เฉพาะเมื่อยังไม่มีไฟล์ และไม่คัดลอกทับค่าที่มีอยู่ หากใช้ Linux/WSL และค่าจาก `id -u` หรือ `id -g` ไม่ใช่ `1000` ให้แก้ `LOCAL_UID` และ `LOCAL_GID` ใน `.env` ให้ตรงก่อน build เพื่อให้ไฟล์ที่ container สร้างเป็นของ user ปัจจุบัน

หากต้องทดสอบการเข้าสู่ระบบด้วยบัญชี TU จริง ให้เพิ่ม key ที่ทีมได้รับลง `.env` (ห้าม commit ไฟล์นี้):

```env
TU_APPLICATION_KEY=<key ของทีม>
```

เริ่มระบบและตรวจสอบ:

```bash
make up
make verify
make smoke
```

เปิด <http://localhost:8000/>; PostgreSQL สำหรับเครื่องมือ DB อยู่ที่ `localhost:5433` โดยใช้ค่าจาก `.env` ตรวจ log ด้วย `make logs` และดูสถานะด้วย `make ps` การหยุดตามปกติใช้ `make down` ซึ่งยังเก็บข้อมูลในฐานข้อมูลไว้

#### ข้อมูลสนาม Sprint 1

เมื่อรัน `make up` ใน development ระบบจะเพิ่มหรือคืนค่าข้อมูลสนาม กีฬา และเวลาเปิด–ปิดของ Sprint 1 ให้อัตโนมัติ ข้อมูลนี้เป็น catalog ของระบบ ไม่ใช่ข้อมูลที่ผู้ใช้ต้องกรอก และการเปิดระบบซ้ำจะไม่สร้างรายการซ้ำ

หากต้องการข้อมูล Party ตัวอย่างเพิ่ม ให้รัน:

```bash
make seed
```

#### ล้างเฉพาะข้อมูลกิจกรรม

หากต้องการล้างห้องที่ผู้ใช้สร้างและข้อมูลสมาชิก/คำขอเข้าร่วมทั้งหมด แต่เก็บบัญชีผู้ใช้ สนาม กีฬา และเวลาเปิด–ปิดไว้ ให้รัน:

```bash
docker compose exec -T backend python backend/manage.py shell -c "from parties.models import Party; Party.objects.all().delete()"
```

`PartyMembership` และ `JoinRequest` ที่ผูกกับห้องจะถูกลบตามไปด้วยโดยอัตโนมัติ

#### ล้างฐานข้อมูล local ทั้งหมด

เมื่อต้องการลบข้อมูลที่ทดสอบทั้งหมด เช่น users, admin, Party, คำขอเข้าร่วม และสนาม ให้ลบ PostgreSQL volume แล้วเปิดระบบใหม่:

```bash
docker compose down --volumes --remove-orphans
make up
```

คำสั่งนี้ลบข้อมูล local ถาวร แต่ไม่ลบ source code หรือ Docker image. หลัง `make up` ระบบจะสร้างฐานข้อมูลใหม่ ใช้ migrations ที่ commit ไว้ และคืน catalog สนามให้อัตโนมัติ

ดูวิธีใช้ Docker โดยไม่มี Make, migrations, การอัปเดต dependency และการทำงานแต่ละส่วนใน [คู่มือ Development](docs/development.md)

หลัง PR environment merge ให้ทุก task branch รัน `git fetch origin` และ `git merge origin/main` เพื่อใช้ environment ชุดเดียวกัน ก่อน merge สามารถทดลองที่ `chore/base-01-project-setup` ได้

## แนวทางทำงานร่วมกัน

แนวทางต่อไปนี้เป็นข้อตกลงตั้งต้นสำหรับทีม โดยใช้ `main` เป็น branch รวมงาน และใช้ branch อายุสั้นแยกตามงาน

### 1. วางแผนและติดตามงาน

- ทำงานเป็น Sprint ประมาณ 2 สัปดาห์ และปรับกำหนดส่งตามปฏิทินรายวิชา
- แต่ละ Issue ระบุ User Story, ผู้รับผิดชอบ, สิ่งที่จะทำ และ Acceptance Criteria
- ใช้สถานะบนบอร์ดงาน: `Todo` → `In Progress` → `In Review` → `Done`
- แบ่งงานให้เล็กพอที่จะตรวจและทดสอบได้ หากงานหลายคนใช้ข้อมูลหรือ API ร่วมกัน ให้ตกลงรูปแบบข้อมูลและสิทธิ์ก่อนลงมือ
- ใช้รหัส User Story จากรายการงาน เช่น `us-10` โดยแยกจากเลข GitHub Issue เช่น `#23` ให้ชัดเจน

### 2. การแตก Branch

ตั้งชื่อเป็นภาษาอังกฤษตัวพิมพ์เล็ก คั่นคำด้วย `-` และใช้รูปแบบ:

```text
<type>/<story-or-issue>-<short-description>
```

| ประเภท | ใช้เมื่อ | ตัวอย่าง |
| --- | --- | --- |
| `feat` | เพิ่มฟีเจอร์ | `feat/us-10-approve-party-request` |
| `fix` | แก้บั๊ก | `fix/us-3-duplicate-request` |
| `docs` | แก้เอกสาร | `docs/update-readme` |
| `refactor` | ปรับโครงสร้างโดยไม่เปลี่ยนพฤติกรรม | `refactor/party-permission-checks` |
| `test` | เพิ่มหรือปรับการทดสอบ | `test/us-10-last-slot` |
| `chore` | ตั้งค่าเครื่องมือหรือดูแลงานทั่วไป | `chore/project-setup` |

หากไม่มี Story หรือ Issue ที่เกี่ยวข้อง สามารถละรหัสได้ เช่น `docs/update-readme` หนึ่ง branch ควรมีเป้าหมายเดียว และ **ไม่ push งานโดยตรงเข้า `main`**

ตัวอย่างเริ่มงาน โดยตรวจว่าบันทึกงานค้างใน branch ปัจจุบันเรียบร้อยก่อน:

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c feat/us-10-approve-party-request
```

หากระหว่างทำงานมีการอัปเดต `main` ให้รวมเข้ามาใน branch ของตนเอง แก้ conflict และทดสอบอีกครั้ง:

```bash
git fetch origin
git merge origin/main
```

ไม่ force push ไปยัง `main` หรือ branch ที่ใช้ร่วมกับคนอื่น

### 3. Commit Convention

ใช้รูปแบบ Conventional Commits:

```text
<type>(<scope>): <description>
```

- `type` ใช้ `feat`, `fix`, `docs`, `refactor`, `test` หรือ `chore` ตามตารางด้านบน และใช้ `ci` สำหรับการตั้งค่า CI
- `scope` ระบุส่วนที่แก้ เช่น `party`, `auth`, `chat`, `profile` โดยละได้เมื่อเป็นงานภาพรวม
- `description` เขียนสั้นและบอกสิ่งที่เปลี่ยน ใช้ภาษาไทยหรืออังกฤษได้ หลีกเลี่ยงข้อความกว้าง ๆ เช่น `update` หรือ `แก้งาน`
- หนึ่ง commit ควรเป็นการเปลี่ยนแปลงเรื่องเดียวที่อธิบายได้ และไม่รวมไฟล์ที่ไม่เกี่ยวข้อง
- ถ้าเปลี่ยน API หรือพฤติกรรมที่ทำให้ส่วนเดิมใช้ต่อไม่ได้ ให้ใส่ `!` ก่อน `:` และอธิบายผลกระทบในรายละเอียด commit

ตัวอย่าง:

```text
feat(party): add host approval for join requests
fix(party): prevent approval when the last slot is taken
docs: เพิ่มขั้นตอนเริ่มต้นพัฒนา
test(chat): cover access after leaving a party
chore: initialize Django project
feat(party)!: change join response to pending request
```

ก่อน commit ให้ตรวจ diff และเลือก stage เฉพาะไฟล์ของงานนั้น:

```bash
git diff
git add <file-path>
git diff --cached
git commit -m "feat(party): add host approval for join requests"
git push -u origin feat/us-10-approve-party-request
```

แทน `<file-path>` ด้วยไฟล์ที่ต้องการ commit และอย่า commit `.env`, credentials, virtual environment หรือไฟล์ที่สร้างอัตโนมัติโดยไม่จำเป็น

### 4. Pull Request และ Code Review

1. เปิด Pull Request (PR) จาก branch ของงานเข้าสู่ `main` ใช้ชื่อ PR ตามรูปแบบ commit
2. ระบุสิ่งที่เปลี่ยน เหตุผล Story/Issue ที่เกี่ยวข้อง และวิธีพร้อมผลการทดสอบ หากแก้ UI ให้แนบภาพก่อน/หลังตามความเหมาะสม
3. ขอให้เพื่อนร่วมทีมอย่างน้อย 1 คนตรวจ โดยเน้นพฤติกรรมตาม Acceptance Criteria สิทธิ์ผู้ใช้ และผลกระทบต่อส่วนอื่น
4. แก้ข้อเสนอแนะและ conflict ให้เรียบร้อย ตรวจให้การทดสอบที่เกี่ยวข้องผ่าน รวมถึง CI เมื่อมีการตั้งค่าแล้ว
5. ใช้ **Squash and merge** โดยตั้งชื่อ commit ที่รวมแล้วตาม Commit Convention จากนั้นลบ branch ที่ merge แล้วและอัปเดตสถานะงาน

รูปแบบคำอธิบาย PR ที่ใช้ได้:

```markdown
## สิ่งที่เปลี่ยนและเหตุผล
- ...

## งานที่เกี่ยวข้อง
- User Story: us-10
- Closes #23

## การทดสอบ
- ขั้นตอน/คำสั่ง: ...
- ผลที่ได้: ...

## ผลกระทบหรือสิ่งที่ต้องทำเพิ่ม
- เช่น migration, environment variable ใหม่ หรือข้อจำกัดที่ยังพบ
```

เปลี่ยนรหัส Story และเลข Issue ให้ตรงกับงานจริง ใช้ `Closes #...` เฉพาะเมื่อ PR ทำ Issue นั้นเสร็จครบแล้ว หากยังเป็นงานบางส่วนให้ใช้ `Refs #...`

### 5. เกณฑ์ก่อนถือว่างานเสร็จ (Definition of Done)

- ทำงานตรง Acceptance Criteria และตรวจกรณีสำเร็จ ข้อมูลผิดพลาด และผู้ใช้ไม่มีสิทธิ์ตามส่วนที่แก้
- งานเกี่ยวกับจำนวนสมาชิกต้องตรวจคำขอซ้ำและการทำงานพร้อมกัน โดยเฉพาะเมื่อเหลือที่ว่างสุดท้าย
- งานแชทต้องตรวจการเข้าถึงข้าม Party และการหมดสิทธิ์หลังถอนตัวหรือถูกระงับ
- หากแก้โครงสร้างฐานข้อมูล มี migration และอธิบายวิธีนำไปใช้
- อัปเดตเอกสารหรือคำสั่งใช้งานเมื่อพฤติกรรมเปลี่ยน พร้อมระบุผลทดสอบจริงและข้อจำกัดที่ยังพบ
- ผ่าน review และ merge เข้า `main` แล้ว จึงย้ายงานเป็น `Done`

มี CI ตรวจ environment ใน `.github/workflows/ci.yml` แล้ว ส่วนกติกา review และการห้าม push เข้า `main` ยังต้องตรวจการตั้งค่า branch protection ของ repository แยกต่างหาก
