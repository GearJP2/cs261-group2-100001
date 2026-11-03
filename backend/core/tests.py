import json
from unittest.mock import patch

from accounts.test_support import force_university_login
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import OperationalError
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from .api import json_error, require_authenticated_api


class ApiHelperTests(TestCase):
    def test_json_error_supports_field_errors(self):
        response = json_error("INVALID_INPUT", "ข้อมูลไม่ถูกต้อง", 400, fields={"title": "กรุณาระบุชื่อ"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content),
            {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "ข้อมูลไม่ถูกต้อง",
                    "fields": {"title": "กรุณาระบุชื่อ"},
                }
            },
        )

    def test_guard_denies_anonymous_and_inactive_users_before_calling_view(self):
        @require_authenticated_api
        def protected(request):
            self.fail("Denied requests must not reach the view")

        for user, status, code in (
            (AnonymousUser(), 401, "AUTH_REQUIRED"),
            (get_user_model()(is_active=False), 403, "ACCOUNT_INACTIVE"),
        ):
            with self.subTest(code=code):
                request = RequestFactory().get("/api/v1/example")
                request.user = user
                response = protected(request)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response["Content-Type"], "application/json")
                error = json.loads(response.content)["error"]
                self.assertEqual(error["code"], code)
                self.assertEqual(set(error), {"code", "message"})

    def test_guard_allows_verified_user_and_preserves_view_arguments(self):
        @require_authenticated_api
        def protected(request, party_id):
            return JsonResponse({"data": {"id": party_id, "user_id": request.user.pk}})

        request = RequestFactory().get("/api/v1/example?user_id=999")
        request.user = get_user_model().objects.create_user("guard-user")
        identity = force_university_login(self.client, request.user)
        request.session = self.client.session
        response = protected(request, party_id=12)
        self.assertEqual(protected.__name__, "protected")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content), {"data": {"id": 12, "user_id": request.user.pk}}
        )
        self.assertEqual(request.university_identity, identity)

    def test_guard_denies_local_login_without_university_identity(self):
        @require_authenticated_api
        def protected(request):
            self.fail("Local-only sessions must not reach the view")

        request = RequestFactory().get("/api/v1/example")
        request.user = get_user_model().objects.create_user("local-only")
        self.client.force_login(request.user)
        request.session = self.client.session
        response = protected(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["error"]["code"], "FORBIDDEN")


class PublicPageTests(SimpleTestCase):
    def test_home_renders_shared_frontend_template_and_stylesheet(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, "UniSport Buddy")
        self.assertContains(response, "/static/css/site.css")

    def test_sprint_one_ui_routes_render(self):
        for url in ("/login/", "/parties/42/", "/parties/42/edit/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "UniSport Buddy")

    def test_party_create_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("party-create-page"))
        self.assertRedirects(
            response,
            f"{reverse('login-page')}?next=%2Fparties%2Fnew%2F",
        )

    def test_liveness_does_not_require_a_database(self):
        self.assertEqual(self.client.get(reverse("health-live")).json(), {"status": "ok"})

    def test_health_routes_do_not_accept_writes(self):
        for name in ("health-live", "health-ready"):
            with self.subTest(name=name):
                self.assertEqual(self.client.post(reverse(name)).status_code, 405)


class ReadinessTests(TestCase):
    def test_readiness_checks_postgres(self):
        response = self.client.get(reverse("health-ready"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_database_failure_returns_503_without_leaking_details(self):
        with patch("core.views.connection.cursor", side_effect=OperationalError("private detail")):
            response = self.client.get(reverse("health-ready"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertNotContains(response, "private detail", status_code=503)
