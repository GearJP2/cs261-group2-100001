import json
from django.conf import settings
from django.db import connection
from django.contrib.auth import get_user_model
from parties.models import Party
from parties.services import PartyError
from conduct.services import submit_review
from conduct.models import PartyReview
from accounts.models import UserProfile
assert settings.DEBUG and connection.settings_dict['NAME'].startswith('s2_task95_')
users=get_user_model()
h=users.objects.get(username='s2data_h')
m=users.objects.get(username='s2data_m')
p=Party.objects.get(title='[S2-DATA] Completed',host=h,description='Synthetic S2-DATA fixture; rerunning seed_sprint2 resets this party.')
assert not PartyReview.objects.filter(reviewee=m).exists()
before=UserProfile.objects.filter(user=m).values('rating_sum','rating_count','credit_score').get()
assert (before['rating_sum'],before['rating_count'])==(0,0)
r=submit_review(party_id=p.pk,reviewer=h,reviewee_id=m.pk,rating=5,comment='Synthetic Task95 manual service')
after=UserProfile.objects.filter(user=m).values('rating_sum','rating_count','credit_score').get()
assert (after['rating_sum'],after['rating_count'])==(5,1)
try:
    submit_review(party_id=p.pk,reviewer=h,reviewee_id=m.pk,rating=5,comment='Synthetic duplicate')
except PartyError as error:
    assert (error.code,error.status)==('REVIEW_EXISTS',409)
else:
    raise AssertionError('Duplicate accepted')
assert UserProfile.objects.filter(user=m).values('rating_sum','rating_count','credit_score').get()==after
assert after['credit_score']==before['credit_score']
assert PartyReview.objects.filter(reviewee=m).count()==1
print(json.dumps({'manual_service':'PASS','review_id':r.pk,'before':before,'after':after,'duplicate_error':'REVIEW_EXISTS','duplicate_status':409},default=str))
