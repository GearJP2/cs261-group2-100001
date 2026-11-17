import os,sys,json,uuid
from pathlib import Path
from datetime import timedelta
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from accounts.models import UserProfile
from accounts.test_support import force_university_login
from parties.models import Party,PartyMembership
from venues.models import Sport,Venue
from django.db import connection
from django.conf import settings
assert settings.DEBUG and connection.vendor == 'postgresql'
assert connection.settings_dict['NAME'].startswith('s2_task93_')
assert os.environ.get('TASK93_CONFIRM_TEST_DATABASE') == 'yes'
fixture_path = Path(os.environ['TASK93_FIXTURE_FILE'])
assert not fixture_path.exists(), 'Use a fresh private fixture path'
prefix='qa93_'+uuid.uuid4().hex[:8]
users={r:get_user_model().objects.create_user(prefix+'_'+r) for r in ('host','reviewer','target','peer','outsider','early')}
for r,u in users.items():UserProfile.objects.create(user=u,display_name=f'QA93 {r}')
sport=Sport.objects.create(name=prefix);venue=Venue.objects.create(name=prefix,location_text='Synthetic local QA')
now=timezone.now();parties={}
for label in ['main','second','future','cancelled','early']+[f'page{i}' for i in range(9)]:
 p=Party.objects.create(host=users['host'],sport=sport,venue=venue,title='QA93 '+label,capacity=10,starts_at=now-timedelta(hours=3),ends_at=now-timedelta(hours=2))
 for r in ('host','reviewer','target','peer','early'):
  PartyMembership.objects.create(party=p,user=users[r],left_at=p.ends_at-timedelta(seconds=1) if r=='early' else None)
 if label=='future':p.starts_at=now+timedelta(days=1);p.ends_at=p.starts_at+timedelta(hours=1);p.save()
 if label=='cancelled':p.cancelled_at=now;p.save()
 parties[label]=p.pk
cookies={}
for r,u in users.items():
 client=Client();force_university_login(client,u);cookies[r]=client.cookies['sessionid'].value
fixture={'users':{r:u.pk for r,u in users.items()},'parties':parties,'cookies':cookies,'prefix':prefix}
fixture_path.write_text(json.dumps(fixture))
fixture_path.chmod(0o600)
print('Created isolated synthetic fixture:',len(users),'users;',len(parties),'parties; session values not logged')
