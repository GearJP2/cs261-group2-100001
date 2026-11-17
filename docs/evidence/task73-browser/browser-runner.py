import os,sys,json
from pathlib import Path
from datetime import timedelta
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.utils import timezone
assert settings.DEBUG and connection.vendor=='postgresql' and connection.settings_dict['NAME'].startswith('s2_task93_')
assert os.environ.get('TASK73_CONFIRM_TEST_DATABASE')=='yes'
import asyncio,subprocess,hashlib
from playwright.async_api import async_playwright, expect
from django.contrib.sessions.models import Session
OUT=Path(os.environ['TASK73_OUTPUT_DIR']);assert not OUT.exists();OUT.mkdir(parents=True)
BASE=os.environ.get('TASK73_BASE_URL','http://127.0.0.1:25880');url=urlparse(BASE)
assert url.scheme=='http' and url.hostname in {'localhost','127.0.0.1'} and not url.username and not url.password and url.path in {'','/'} and not url.query and not url.fragment
f=json.loads(Path(os.environ['TASK73_FIXTURE_FILE']).read_text());P=f['leave_parties'];U=f['users'];cases=[]
def sql():
 with connection.cursor() as c:
  c.execute('SELECT id,capacity,cancelled_at FROM parties_party WHERE id=ANY(%s) ORDER BY id',[list(P.values())]);p=c.fetchall()
  c.execute('SELECT party_id,user_id,joined_at,left_at FROM parties_partymembership WHERE party_id=ANY(%s) ORDER BY id',[list(P.values())]);m=c.fetchall()
  c.execute('SELECT party_id,user_id,status,decided_by_id FROM parties_joinrequest WHERE party_id=ANY(%s) ORDER BY id',[list(P.values())]);r=c.fetchall()
 return {'parties':p,'members':m,'requests':r}
def save(name,expected,actual,before,after):
 cases.append({'id':name,'expected':expected,'actual':actual,'before':before,'after':after,'result':'Pass'});print('PASS',name,flush=True)
 (OUT/'results.json').write_text(json.dumps({'tested_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'kind':'real Chromium + Django HTTP + isolated PostgreSQL, synthetic university sessions','cases':cases},ensure_ascii=False,indent=2,default=str))
async def main():
 async with async_playwright() as pw:
  b=await pw.chromium.launch(executable_path=os.environ['TASK73_CHROME'],args=['--no-sandbox'])
  async def ctx(role):
   c=await b.new_context(viewport={'width':1280,'height':900});await c.add_cookies([{'name':'sessionid','value':f['cookies'][role],'domain':'127.0.0.1','path':'/'}]);return c
  async def post(c,path,payload={},csrf=True):
   r=await c.request.get(BASE+'/api/v1/auth/csrf');token=(await r.json())['data']['csrf_token'];r=await c.request.post(BASE+'/api/v1'+path,data=payload,headers={'X-CSRFToken':token} if csrf else {});return r.status,await r.json()
  r=await ctx('reviewer');h=await ctx('host');x=await ctx('outsider');page=await r.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));posts=[];page.on('request',lambda q:posts.append(q.url) if q.method=='POST' and q.url.endswith('/leave') else None)
  await page.goto(BASE+'/my-parties/');await page.locator('[data-myparty-tab="joined"]').click()
  for k in ('started','cancelled','pending'):assert await page.locator(f'[data-leave-party="{P[k]}"]').is_disabled()
  hp=await h.new_page();await hp.goto(BASE+'/my-parties/');await hp.locator('[data-myparty-tab="joined"]').click();assert await hp.locator(f'[data-leave-party="{P["success"]}"]').is_disabled()
  before=await asyncio.to_thread(sql);btn=page.locator(f'[data-leave-party="{P["cancel"]}"]');await btn.click();await page.locator('[data-leave-close]').click();await btn.click();await page.keyboard.press('Escape');assert not await page.locator('#leave-dialog').is_visible();assert not posts;assert before==await asyncio.to_thread(sql)
  save('B01-native-cancel-and-eligibility','Host/started/cancelled/Pending disabled; cancel/Escape send zero POST, no domain mutation',{'posts':len(posts),'disabled_roles_states':'Pass'},before,await asyncio.to_thread(sql))
  before=await asyncio.to_thread(sql);btn=page.locator(f'[data-leave-party="{P["success"]}"]');await btn.click()
  async def delay(route):await asyncio.sleep(.3);await route.continue_()
  await page.route(f'**/parties/{P["success"]}/leave',delay)
  async with page.expect_response(lambda z:z.request.method=='POST' and z.url.endswith(f'/parties/{P["success"]}/leave')) as wait:
   await page.locator('[data-leave-confirm]').click();assert await page.locator('[data-leave-confirm]').is_disabled();await page.keyboard.press('Escape');assert await page.locator('#leave-dialog').is_visible();await page.locator('#leave-dialog form').evaluate('(f)=>f.requestSubmit()')
  resp=await wait.value;body=await resp.json();assert resp.status==200
  await page.locator('[data-leave-message]').filter(has_text='สมาชิกปัจจุบัน 1 คน ที่ว่าง 2 ที่').wait_for();assert len(posts)==1 and not await btn.count();after=await asyncio.to_thread(sql);assert before['parties']==after['parties'] and before['requests']==after['requests'];changed=[(a,z) for a,z in zip(before['members'],after['members']) if a!=z];assert len(changed)==1 and changed[0][0][0]==P['success'] and changed[0][0][1]==U['reviewer'] and changed[0][0][3] is None and changed[0][1][3] is not None
  await page.screenshot(path=str(OUT/'leave-saved.png'),full_page=True);await page.locator('[data-leave-close]').click();await expect(page.locator('#joined-heading')).to_be_focused();await page.reload();await page.locator('[data-myparty-tab="joined"]').click();assert not await btn.count();await page.unroute(f'**/parties/{P["success"]}/leave')
  save('B02-native-confirm-double-submit-reload','one realPOST200; softleft once; requests/capacity/history unchanged; count1/slots2; focus/reload correct',{'posts':len(posts),'http':resp.status,'response':body},before,after)
  before=await asyncio.to_thread(sql);status,again=await post(r,f'/parties/{P["success"]}/leave');after=await asyncio.to_thread(sql);assert status==200 and again==body and before==after
  save('A01-idempotent-retry','repeat realAPI200 sameleft_at; no mutation',{'http':status,'same_response':True},before,after)
  # Cancel after the page has rendered, using the Host API rather than a fake 409.
  status,_=await post(h,f'/parties/{P["statechange"]}/cancel');assert status==200
  before=await asyncio.to_thread(sql);await page.locator(f'[data-leave-party="{P["statechange"]}"]').click()
  async with page.expect_response(lambda z:z.request.method=='POST' and z.url.endswith(f'/parties/{P["statechange"]}/leave')) as wait:await page.locator('[data-leave-confirm]').click()
  resp=await wait.value;assert resp.status==409;await page.locator('[data-leave-refresh]').wait_for(state='visible');assert 'สำเร็จ' not in await page.locator('[data-leave-message]').inner_text();assert before==await asyncio.to_thread(sql);await page.locator('[data-leave-refresh]').click();await page.wait_for_load_state('domcontentloaded');await page.locator('[data-myparty-tab="joined"]').click();assert await page.locator(f'[data-leave-party="{P["statechange"]}"]').is_disabled()
  save('B03-live-state-change409','realcancel→leave409, no leave mutation, reload shows disabled state',{'http':409,'reload_disabled':True},before,await asyncio.to_thread(sql))
  for name,c,key,status_expected,payload,csrf in [('nonmember',x,'cancel',403,{},True),('host',h,'cancel',403,{},True),('pending',r,'pending',403,{},True),('started',r,'started',409,{},True),('forged-actor',r,'cancel',400,{'user_id':U['outsider']},True),('missing-csrf',r,'cancel',403,{},False)]:
   before=await asyncio.to_thread(sql);status,result=await post(c,f'/parties/{P[key]}/leave',payload,csrf);after=await asyncio.to_thread(sql);assert status==status_expected and before==after,(name,status,result)
   save('A-'+name,f'{status_expected}; no domain mutation',{'http':status,'error':result.get('error')},before,after)
  # Expire the actual Django session after UI load; POST must fail through real middleware.
  await page.goto(BASE+'/my-parties/');await page.wait_for_load_state('networkidle');await page.locator('[data-myparty-tab="joined"]').click();await page.locator(f'[data-leave-party="{P["cancel"]}"]').click();before=await asyncio.to_thread(sql)
  def expire():Session.objects.filter(session_key=f['cookies']['reviewer']).update(expire_date=timezone.now()-timedelta(seconds=1))
  await asyncio.to_thread(expire)
  async with page.expect_response(lambda z:z.request.method=='POST' and z.url.endswith(f'/parties/{P["cancel"]}/leave')) as wait:await page.locator('[data-leave-confirm]').click()
  assert (await wait.value).status==401;await page.wait_for_url('**/login/');assert not await page.locator('[data-joined-party]').count();assert before==await asyncio.to_thread(sql);await page.screenshot(path=str(OUT/'expired-session-login.png'),full_page=True)
  save('B04-real-session-expiry401','realDBsessionexpiry→POST401/login; privatecardsgone; domain unchanged',{'http':401,'location':'/login/'},before,await asyncio.to_thread(sql))
  assert not errors,errors
  report=json.loads((OUT/'results.json').read_text());report.update(summary={'Pass':len(cases),'Fail':0},page_errors=errors,browser=b.version,not_run=['Live TU login','Human UAT/sign-off','Production load']);(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print('DONE',report['summary'],flush=True);await b.close()
asyncio.run(main())
