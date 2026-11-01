"""Issue #80 (S2-US6-T-API): members API unit tests; HTTP/SQL stay in test_members.py."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from .models import Party
from .views import active_memberships, can_view_members, member_data, party_detail, party_members

PARTY_ID = 12
HOST_ID = 1
MEMBER_ID = 2
SECOND_MEMBER_ID = 3
OUTSIDER_ID = 4


def fake_user(pk, display_name=None):
    """Build a user with private attributes that the serializer must never read."""
    user = SimpleNamespace(
        pk=pk,
        is_authenticated=True,
        is_active=True,
        email=f"private-{pk}@example.invalid",
        student_id=f"private-student-{pk}",
        username=f"private-login-{pk}",
        token=f"private-token-{pk}",
        credit_score=987650 + pk,
    )
    if display_name is not None:
        user.profile = SimpleNamespace(
            display_name=display_name,
            email=user.email,
            student_id=user.student_id,
            username=user.username,
            token=user.token,
            credit_score=user.credit_score,
        )
    return user


def private_values(user):
    return (user.email, user.student_id, user.username, user.token, str(user.credit_score))


def fake_row(user, left_at=None):
    return SimpleNamespace(user=user, user_id=user.pk, left_at=left_at)


def fake_queryset(rows=(), viewer_is_active=False):
    """Stand in for the filtered memberships read by the view and permission check."""
    queryset = MagicMock()
    queryset.select_related.return_value.order_by.return_value = list(rows)
    queryset.filter.return_value.exists.return_value = viewer_is_active
    return queryset


class MembersUnitTestCase(SimpleTestCase):
    """Run the real decorators; only their identity lookup and the ORM are mocked."""

    def setUp(self):
        self.host = fake_user(HOST_ID, "นามแฝงผู้จัด")
        self.member = fake_user(MEMBER_ID, "นามแฝงสมาชิก")
        self.second_member = fake_user(SECOND_MEMBER_ID)
        self.outsider = fake_user(OUTSIDER_ID, "นามแฝงคนนอก")
        self.party = SimpleNamespace(
            pk=PARTY_ID,
            host_id=HOST_ID,
            host=self.host,
            memberships=MagicMock(),
            join_requests=MagicMock(),
        )
        self.party_objects = self.start_patch("parties.views.Party.objects")
        self.party_lookup = self.party_objects.select_related.return_value.get
        self.party_lookup.return_value = self.party
        identity_model = self.start_patch("accounts.decorators.UniversityIdentity")
        identity_model.objects.filter.return_value.first.return_value = SimpleNamespace(pk=1)

    def start_patch(self, target):
        patcher = patch(target)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def call(self, user, *, view=party_members, method="get"):
        request = getattr(RequestFactory(), method)(f"/api/v1/parties/{PARTY_ID}/members")
        request.user = user
        request.session = {"university_identity_id": 1}
        return view(request, party_id=PARTY_ID)


class PermissionGuardTests(MembersUnitTestCase):
    def test_ut_us6_api_01_anonymous_gets_auth_required_before_party_lookup(self):
        response = self.call(AnonymousUser())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "AUTH_REQUIRED", "message": "กรุณาเข้าสู่ระบบ"}},
        )
        self.assertEqual(self.party_objects.mock_calls, [])

    def test_ut_us6_api_01_can_view_members_denies_non_host_non_member(self):
        queryset = fake_queryset(viewer_is_active=False)
        with patch("parties.views.active_memberships", return_value=queryset) as active:
            self.assertIs(can_view_members(self.party, self.outsider), False)
        active.assert_called_once_with(self.party)
        queryset.filter.assert_called_once_with(user=self.outsider)

    def test_ut_us6_api_01_can_view_members_allows_host_without_membership_read(self):
        with patch("parties.views.active_memberships") as active:
            self.assertIs(can_view_members(self.party, self.host), True)
        active.assert_not_called()

    def test_ut_us6_api_01_can_view_members_allows_active_member(self):
        queryset = fake_queryset(viewer_is_active=True)
        with patch("parties.views.active_memberships", return_value=queryset):
            self.assertIs(can_view_members(self.party, self.member), True)
        queryset.filter.assert_called_once_with(user=self.member)


class MemberSerializerTests(MembersUnitTestCase):
    def test_ut_us6_api_02_member_data_returns_only_allowlisted_fields(self):
        cases = (
            (self.host, {"user_id": HOST_ID, "display_name": "นามแฝงผู้จัด", "role": "Host"}),
            (self.member, {"user_id": MEMBER_ID, "display_name": "นามแฝงสมาชิก", "role": "Member"}),
        )
        for user, expected in cases:
            with self.subTest(user=user.pk):
                data = member_data(user, self.party)
                # assertEqual on the dict also proves that no extra keys are present.
                self.assertEqual(data, expected)
                for private in private_values(user):
                    self.assertNotIn(private, json.dumps(data, ensure_ascii=False))

    def test_ut_us6_api_02_missing_profile_uses_fallback_never_username(self):
        cases = (
            (fake_user(HOST_ID), "ผู้จัดกิจกรรม", "Host"),
            (fake_user(MEMBER_ID), "ผู้ใช้", "Member"),
        )
        for user, fallback, role in cases:
            with self.subTest(role=role):
                data = member_data(user, self.party)
                self.assertEqual(data, {"user_id": user.pk, "display_name": fallback, "role": role})
                self.assertNotIn(user.username, json.dumps(data, ensure_ascii=False))


class ActivePredicateTests(MembersUnitTestCase):
    def test_ut_us6_api_03_active_memberships_filters_on_left_at_null(self):
        party = MagicMock()
        result = active_memberships(party)
        party.memberships.filter.assert_called_once_with(left_at__isnull=True)
        self.assertIs(result, party.memberships.filter.return_value)

    def test_ut_us6_api_03_left_member_and_requesters_are_not_returned(self):
        # The fake applies the predicate it receives, so the view's real filter decides.
        left = fake_user(5, "นามแฝงคนถอนตัว")
        rows = [fake_row(self.host), fake_row(self.member), fake_row(left, left_at="2026-11-01")]
        requesters = [fake_user(6, "นามแฝงคนรออนุมัติ"), fake_user(7, "นามแฝงคนถูกปฏิเสธ")]
        self.party.join_requests.all.return_value = [fake_row(user) for user in requesters]

        def filter_memberships(**kwargs):
            self.assertEqual(kwargs, {"left_at__isnull": True})
            return fake_queryset(row for row in rows if row.left_at is None)

        self.party.memberships.filter.side_effect = filter_memberships
        response = self.call(self.host)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)["data"]
        self.assertEqual([row["user_id"] for row in data["members"]], [HOST_ID, MEMBER_ID])
        self.assertEqual(data["member_count"], 2)
        for name in ("นามแฝงคนถอนตัว", "นามแฝงคนรออนุมัติ", "นามแฝงคนถูกปฏิเสธ"):
            self.assertNotIn(name, json.dumps(data, ensure_ascii=False))
        # Pending/Rejected live in JoinRequest, which is never a source of members.
        self.assertEqual(self.party.join_requests.mock_calls, [])


class MemberMappingTests(MembersUnitTestCase):
    def read_as_member(self, rows):
        queryset = fake_queryset(rows, viewer_is_active=True)
        with patch("parties.views.active_memberships", return_value=queryset):
            response = self.call(self.member)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        return response, queryset

    def test_ut_us6_api_04_host_first_roles_count_and_envelope(self):
        # The Host row is deliberately second and must be neither misplaced nor repeated.
        rows = [fake_row(self.member), fake_row(self.host), fake_row(self.second_member)]
        response, queryset = self.read_as_member(rows)
        self.assertEqual(
            json.loads(response.content),
            {
                "data": {
                    "members": [
                        {"user_id": HOST_ID, "display_name": "นามแฝงผู้จัด", "role": "Host"},
                        {"user_id": MEMBER_ID, "display_name": "นามแฝงสมาชิก", "role": "Member"},
                        {"user_id": SECOND_MEMBER_ID, "display_name": "ผู้ใช้", "role": "Member"},
                    ],
                    "member_count": 3,
                }
            },
        )
        self.party_objects.select_related.assert_called_once_with("host__profile")
        self.party_lookup.assert_called_once_with(pk=PARTY_ID)
        queryset.select_related.assert_called_once_with("user__profile")
        queryset.select_related.return_value.order_by.assert_called_once_with("joined_at", "pk")

    def test_ut_us6_api_04_host_without_row_is_added_and_counted(self):
        response, _ = self.read_as_member([fake_row(self.member)])
        data = json.loads(response.content)["data"]
        self.assertEqual([row["role"] for row in data["members"]], ["Host", "Member"])
        self.assertEqual(data["member_count"], len(data["members"]))


class ErrorResponseTests(MembersUnitTestCase):
    def test_ut_us6_api_05_missing_party_matches_existing_not_found(self):
        self.party_lookup.side_effect = Party.DoesNotExist
        with patch("parties.views.active_memberships") as active:
            response = self.call(self.outsider)
            existing = self.call(self.outsider, view=party_detail)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.content),
            {"error": {"code": "NOT_FOUND", "message": "ไม่พบกิจกรรมที่ต้องการ"}},
        )
        self.assertEqual(json.loads(response.content), json.loads(existing.content))
        active.assert_not_called()

    def test_ut_us6_api_05_non_get_returns_405_before_party_lookup(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = self.call(self.host, method=method)
                self.assertEqual(response.status_code, 405)
                self.assertEqual(response["Allow"], "GET")
                self.assertEqual(
                    json.loads(response.content)["error"]["code"], "METHOD_NOT_ALLOWED"
                )
        self.assertEqual(self.party_objects.mock_calls, [])

    def test_ut_us6_api_05_forbidden_viewer_gets_403_without_member_data(self):
        queryset = fake_queryset([fake_row(self.host), fake_row(self.member)])
        with patch("parties.views.active_memberships", return_value=queryset):
            response = self.call(self.outsider)
        self.assertEqual(response.status_code, 403)
        payload = json.loads(response.content)
        self.assertEqual(set(payload), {"error"})
        self.assertEqual(set(payload["error"]), {"code", "message"})
        self.assertEqual(payload["error"]["code"], "FORBIDDEN")
        for name in ("นามแฝงผู้จัด", "นามแฝงสมาชิก"):
            self.assertNotIn(name, json.dumps(payload, ensure_ascii=False))
        queryset.select_related.assert_not_called()
