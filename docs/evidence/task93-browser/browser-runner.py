import asyncio,json,os,sys,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import connection
from playwright.async_api import async_playwright
BASE = os.environ.get('TASK93_BASE_URL', 'http://127.0.0.1:25880')
parsed = urlparse(BASE)
assert parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'}
assert not parsed.username and not parsed.password and parsed.path in {'', '/'}
assert not parsed.query and not parsed.fragment
OUT = Path(os.environ['TASK93_OUTPUT_DIR'])
assert not OUT.exists(), 'Use a fresh evidence directory'
OUT.mkdir(parents=True)
f=json.loads(Path(os.environ['TASK93_FIXTURE_FILE']).read_text());U=f['users'];P=f['parties']
from django.conf import settings
assert settings.DEBUG and connection.vendor == 'postgresql'
assert connection.settings_dict['NAME'].startswith('s2_task93_')
assert os.environ.get('TASK93_CONFIRM_TEST_DATABASE') == 'yes'
def sql():
 with connection.cursor() as c:
  c.execute('SELECT party_id,reviewer_id,reviewee_id,rating,comment FROM conduct_partyreview WHERE party_id = ANY(%s) ORDER BY id',[list(P.values())]);reviews=c.fetchall()
  c.execute('SELECT user_id,rating_sum,rating_count,credit_score FROM accounts_userprofile WHERE user_id = ANY(%s) ORDER BY user_id',[list(U.values())]);profiles=c.fetchall()
 return {'reviews':reviews,'profiles':profiles}
report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'started_at':datetime.now(timezone.utc).isoformat(),'kind':'Chromium + actual Django HTTP API + isolated PostgreSQL; synthetic verified sessions, not live TU login or human UAT','fixture_users':U,'fixture_parties':P,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['frontend/static/js/myparty-review.js','frontend/static/js/profile-reviews.js','frontend/templates/partials/review_history_content.html','backend/conduct/services.py','backend/conduct/views.py']},'cases':[]}
def record(case,expected,actual,before=None,after=None):
 item={'id':case,'expected':expected,'actual':actual,'result':'Pass'}
 if before is not None:item.update(sql_before=before,sql_after=after)
 report['cases'].append(item);(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));print('PASS',case,flush=True)
async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path=os.environ['TASK93_CHROME'],args=['--no-sandbox'])
  report['browser']=browser.version
  async def context(role):
   c=await browser.new_context(viewport={'width':1280,'height':900});await c.add_cookies([{'name':'sessionid','value':f['cookies'][role],'domain':'127.0.0.1','path':'/'}]);return c
  ctx=await context('reviewer');page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));posts=[]
  page.on('request',lambda r:posts.append(r.url) if r.method=='POST' and '/reviews' in r.url else None)
  async def post(c,party,payload,csrf=True):
   r=await c.request.get(BASE+'/api/v1/auth/csrf');token=(await r.json())['data']['csrf_token'];headers={'X-CSRFToken':token} if csrf else {}
   r=await c.request.post(BASE+f'/api/v1/parties/{party}/reviews',data=payload,headers=headers);return r.status,await r.json()
  await page.goto(BASE+'/my-parties/');await page.locator('[data-myparty-tab="history"]').click()
  assert await page.locator(f'#review-dialog-{P["future"]}').count()==0 and await page.locator(f'#review-dialog-{P["cancelled"]}').count()==0
  d=page.locator(f'#review-dialog-{P["main"]}');opener=page.locator(f'[data-open-review="review-dialog-{P["main"]}"]');await opener.click()
  values=await d.locator('select option').evaluate_all('(els)=>els.map(e=>e.value)');assert str(U['reviewer']) not in values and str(U['early']) not in values and str(U['target']) in values
  assert await d.locator('[data-review-close]').evaluate('(e)=>e===document.activeElement')
  for _ in range(12):
   await page.keyboard.press('Tab')
   assert await page.evaluate('document.activeElement === document.body || Boolean(document.activeElement.closest("dialog[open]"))')
  await page.keyboard.press('Escape');assert not await d.is_visible();assert await opener.evaluate('(e)=>e===document.activeElement')
  record('B01-eligibility-keyboard','exclude self/early/future/cancelled; Tab avoids background controls; Escape returns focus',{'eligible_target_values':values,'native_dialog_focus_escape':'Pass (body/browser chrome focus allowed; background page controls excluded)'})
  await opener.click();await d.locator('select').select_option(str(U['target']));await d.locator('textarea').fill('Valid comment without rating');before=await asyncio.to_thread(sql);n=len(posts);await d.locator('[type="submit"]').click();assert len(posts)==n and await asyncio.to_thread(sql)==before
  await d.locator('[name="rating"][value="5"]').check();await d.locator('textarea').fill('   ');await d.locator('[type="submit"]').click();assert len(posts)==n and await asyncio.to_thread(sql)==before
  assert await d.locator('textarea').evaluate('(e)=>e.validationMessage')
  record('B02-native-required-whitespace','missing rating/blank comment block POST and preserve DB',{'review_posts':len(posts)-n,'database_unchanged':True},before,await asyncio.to_thread(sql))
  await d.locator('textarea').fill('x'*501);value=await d.locator('textarea').input_value();assert len(value)==500
  record('B03-native-maxlength','textarea limits entry to500 characters',{'length':len(value)})
  comment='<img src=x onerror="window.qaXss=true"> Great teammate'
  await d.locator('textarea').fill('  '+comment+'  ')
  async def delay(route):await asyncio.sleep(.3);await route.continue_()
  await page.route(f'**/parties/{P["main"]}/reviews',delay)
  before=await asyncio.to_thread(sql);n=len(posts)
  async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith(f'/parties/{P["main"]}/reviews')) as pending:
   await d.locator('[type="submit"]').click();assert await d.locator('[type="submit"]').is_disabled() and await d.locator('[data-review-close]').is_disabled();await d.locator('form').evaluate('(form)=>form.requestSubmit()')
  resp=await pending.value;assert resp.status==201
  await d.locator('[data-review-message]').filter(has_text='บันทึกรีวิวเรียบร้อยแล้ว').wait_for();assert len(posts)-n==1
  after=await asyncio.to_thread(sql);assert len(after['reviews'])==len(before['reviews'])+1
  target=next(r for r in after['profiles'] if r[0]==U['target']);assert target[1:]==(5,1,None)
  assert await d.locator(f'option[value="{U["target"]}"]').is_disabled()
  await page.screenshot(path=str(OUT/'review-saved.png'),full_page=True);await page.unroute(f'**/parties/{P["main"]}/reviews');await d.locator('[data-review-close]').click()
  await page.reload();await page.locator('[data-myparty-tab="history"]').click();assert await d.locator(f'option[value="{U["target"]}"]').is_disabled()
  record('B04-real201-double-submit-reload','one POST/one row, rating_sum5/count1/credit unchanged; reviewed target persists',{'http':201,'native_posts':len(posts)-n,'cache':target},before,after)
  await page.goto(BASE+f'/users/{U["target"]}/');await page.locator('[data-review-summary]').filter(has_text='5.0').wait_for();assert await page.locator('.review-comment').text_content()==comment;assert not await page.locator('.review-comment img').count();assert not await page.evaluate('Boolean(window.qaXss)');assert 'ไม่มีคะแนน' in await page.locator('[aria-labelledby="credit-title"]').inner_text()
  record('B05-profile-live-summary-xss','profile loads saved review via real API; average5.0,count1; HTML inert and credit separate',{'summary':await page.locator('[data-review-summary]').inner_text(),'review_count':await page.locator('[data-review-count]').inner_text(),'html_executed':False})
  # Boundary rating1 through the native browser form on another Party.
  await page.goto(BASE+'/my-parties/');await page.locator('[data-myparty-tab="history"]').click();await page.locator(f'[data-open-review="review-dialog-{P["second"]}"]').click();second=page.locator(f'#review-dialog-{P["second"]}')
  await second.locator('select').select_option(str(U['target']));await second.locator('[name="rating"][value="1"]').check();await second.locator('textarea').fill('Rating one boundary')
  async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith(f'/parties/{P["second"]}/reviews')) as pending:await second.locator('[type="submit"]').click()
  assert (await pending.value).status==201;await second.locator('[data-review-message]').filter(has_text='บันทึกรีวิวเรียบร้อยแล้ว').wait_for();await second.locator('[data-review-close]').click()
  await page.goto(BASE+f'/users/{U["target"]}/');await page.locator('[data-review-summary]').filter(has_text='3.0').wait_for()
  record('B06-rating1-and-live-average','rating1 accepted on anotherParty; profile average(5+1)/2=3.0',{'summary':await page.locator('[data-review-summary]').inner_text()})
  await page.goto(BASE+'/my-parties/');await page.locator('[data-myparty-tab="history"]').click();await opener.click();await d.locator('select').select_option(str(U['peer']));await d.locator('[name="rating"][value="4"]').check();await d.locator('textarea').fill('Stale browser form')
  status,_=await post(ctx,P['main'],{'reviewee_id':U['peer'],'rating':4,'comment':'Concurrent review from another tab'});assert status==201;before=await asyncio.to_thread(sql)
  async with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith(f'/parties/{P["main"]}/reviews')) as pending:await d.locator('[type="submit"]').click()
  assert (await pending.value).status==409;await d.locator('[data-review-message]').filter(has_text='รีวิว').wait_for();assert await d.locator(f'option[value="{U["peer"]}"]').is_disabled();after=await asyncio.to_thread(sql);assert before==after;await d.locator('[data-review-close]').click()
  record('B07-real409-conflict','stale form receives real409, target disabled, DB/cache unchanged',{'http':409,'message':await d.locator('[data-review-message]').text_content()},before,after)
  # HTTP validation/permission/CSRF requests use real middleware, not route.fulfill or mocks.
  bad_payloads=[('rating0',{'rating':0}),('rating6',{'rating':6}),('rating-bool',{'rating':True}),('comment501',{'comment':'x'*501}),('self',{'reviewee_id':U['reviewer']}),('early-target',{'reviewee_id':U['early']})]
  for name,changes in bad_payloads:
   before=await asyncio.to_thread(sql);status,body=await post(ctx,P['main'],{'reviewee_id':U['target'],'rating':3,'comment':'Invalid check',**changes});after=await asyncio.to_thread(sql);assert status==400 and before==after
   record('A-'+name,'400; no mutation',{'http':status,'error':body.get('error')},before,after)
  for name,party,expected in [('future',P['future'],409),('cancelled',P['cancelled'],409),('unknown-party',2147483646,404)]:
   before=await asyncio.to_thread(sql);status,body=await post(ctx,party,{'reviewee_id':U['target'],'rating':3,'comment':'State check'});after=await asyncio.to_thread(sql);assert status==expected and before==after
   record('A-'+name,f'{expected}; no mutation',{'http':status,'error':body.get('error')},before,after)
  before=await asyncio.to_thread(sql);status,body=await post(ctx,P['main'],{'reviewee_id':U['target'],'rating':3,'comment':'No CSRF'},csrf=False);after=await asyncio.to_thread(sql);assert status==403 and before==after
  record('A-csrf','403 CSRF_FAILED, no mutation',{'http':status,'error':body.get('error')},before,after)
  for role in ('outsider','early'):
   c=await context(role);p=await c.new_page();await p.goto(BASE+'/my-parties/');await p.locator('[data-myparty-tab="history"]').click();assert await p.locator('[data-review-dialog]').count()==0
   before=await asyncio.to_thread(sql);status,body=await post(c,P['main'],{'reviewee_id':U['target'],'rating':3,'comment':'Forbidden check'});after=await asyncio.to_thread(sql);assert status==403 and before==after
   record('A-'+role,'no eligible history; POST403, no mutation',{'http':status,'history_dialogs':0,'error':body.get('error')},before,after);await c.close()
  anonymous=await browser.new_context();r=await anonymous.request.get(BASE+f'/api/v1/users/{U["target"]}/reviews');assert r.status==401;record('A-anonymous-list','401 without verified session',{'http':r.status});await anonymous.close()
  # Add real API reviews to exercise profile pagination against persisted rows.
  for key in [f'page{i}' for i in range(9)]:
   status,body=await post(ctx,P[key],{'reviewee_id':U['target'],'rating':4,'comment':f'Pagination fixture {key}'});assert status==201,(key,status,body)
  await page.goto(BASE+f'/users/{U["target"]}/');await page.locator('[data-review-summary]').filter(has_text='3.8').wait_for();await page.locator('[data-review-count]').filter(has_text='11 รีวิว').wait_for();assert await page.locator('.review-item').count()==10
  r=await ctx.request.get(BASE+f'/api/v1/users/{U["target"]}/reviews?page=1&page_size=10');data=(await r.json())['data'];assert data['rating_count']==11 and data['average_rating']==3.82 and data['total']==11
  for review in data['reviews']:assert set(review)=={'id','rating','comment','reviewer','created_at'} and set(review['reviewer'])=={'display_name'}
  await page.locator('[data-review-next]').click();await page.locator('[data-review-page-label]').filter(has_text='หน้า 2 จาก 2').wait_for();assert await page.locator('.review-item').count()==1;assert await page.locator('[data-review-next]').is_disabled();await page.screenshot(path=str(OUT/'profile-page2.png'),full_page=True)
  await page.locator('[data-review-prev]').click();await page.locator('[data-review-page-label]').filter(has_text='หน้า 1 จาก 2').wait_for();assert await page.locator('.review-item').count()==10;await page.screenshot(path=str(OUT/'profile-page1.png'),full_page=True)
  after=await asyncio.to_thread(sql);target=next(r for r in after['profiles'] if r[0]==U['target']);assert target[1:]==(42,11,None)
  record('B08-live-pagination-public-fields','11 reviews; pages10+1; average3.82(API)/3.8(UI); public allowlist; credit unchanged',{'api_average':data['average_rating'],'total':data['total'],'pages':[10,1],'cache':target},None,None)
  await page.goto(BASE+f'/users/{U["outsider"]}/');await page.locator('[data-review-status]').filter(has_text='ยังไม่มีรีวิว').wait_for();assert 'ยังไม่มีคะแนนรีวิว' in await page.locator('[data-review-summary]').inner_text();assert await page.locator('[data-review-pagination]').is_hidden();assert await page.locator('[data-review-error]').is_hidden()
  record('B09-profile-empty','no reviews shows empty/null summary and hides error/pagination',{'summary':await page.locator('[data-review-summary]').inner_text()})
  # Change account inside the same browser storage context, then read SSR state.
  await ctx.clear_cookies();await ctx.add_cookies([{'name':'sessionid','value':f['cookies']['host'],'domain':'127.0.0.1','path':'/'}]);await page.goto(BASE+'/my-parties/');await page.locator('[data-myparty-tab="history"]').click();assert not await d.locator(f'option[value="{U["target"]}"]').is_disabled()
  record('B10-account-isolation','reviewed status scoped to reviewer, even in same browser context',{'host_target_still_reviewable':True})
  assert not errors,errors
  report.update(finished_at=datetime.now(timezone.utc).isoformat(),summary={'Pass':len(report['cases']),'Fail':0},page_errors=errors,final_sql=await asyncio.to_thread(sql),not_run=['Live TU login','Human UAT/sign-off','No-show API','Full cross-story Sprint2 browser flow'])
  (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));await ctx.close();await browser.close();print('DONE',report['summary'],flush=True)
try:asyncio.run(main())
except Exception as e:
 report.update(failure={'type':type(e).__name__,'message':str(e)},finished_at=datetime.now(timezone.utc).isoformat());(OUT/'failed-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));raise
