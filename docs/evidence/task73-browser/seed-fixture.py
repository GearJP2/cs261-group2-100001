import os,sys,json,uuid
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from accounts.models import UserProfile
from accounts.test_support import force_university_login
from parties.models import Party,PartyMembership,JoinRequest
from venues.models import Sport,Venue
assert settings.DEBUG and connection.vendor=='postgresql' and connection.settings_dict['NAME'].startswith('s2_task93_')
assert os.environ.get('TASK73_CONFIRM_TEST_DATABASE')=='yes'
output=Path(os.environ['TASK73_FIXTURE_FILE']);assert not output.exists()
prefix='qa73_'+uuid.uuid4().hex[:8];users={};cookies={}
for role in ('host','reviewer','outsider'):
 u=get_user_model().objects.create_user(prefix+'_'+role);UserProfile.objects.create(user=u,display_name='QA73 '+role);users[role]=u.pk
 c=Client();force_university_login(c,u);cookies[role]=c.cookies['sessionid'].value
sport=Sport.objects.create(name=prefix);venue=Venue.objects.create(name=prefix,location_text='Synthetic QA only');now=timezone.now();parties={}
for label in ('cancel','success','statechange','started','cancelled','pending'):
 p=Party.objects.create(host_id=users['host'],sport=sport,venue=venue,title='QA73 '+label,capacity=3,starts_at=now+timedelta(days=1),ends_at=now+timedelta(days=1,hours=1))
 PartyMembership.objects.create(party=p,user_id=users['host'])
 if label=='pending':JoinRequest.objects.create(party=p,user_id=users['reviewer'])
 else:
  PartyMembership.objects.create(party=p,user_id=users['reviewer']);JoinRequest.objects.create(party=p,user_id=users['reviewer'],status='Approved',decided_at=now,decided_by_id=users['host'])
 if label=='started':p.starts_at=now-timedelta(minutes=1);p.ends_at=now+timedelta(hours=1);p.save()
 if label=='cancelled':p.cancelled_at=now;p.save()
 parties[label]=p.pk
output.write_text(json.dumps({'users':users,'cookies':cookies,'leave_parties':parties}));output.chmod(0o600)
print('Seeded synthetic fixture; session values not logged')
