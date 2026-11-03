"""Home navigation has real destination pages for the Sprint 1 UI flow."""

from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse


class ControlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.hrefs.append(attrs["href"])


def hrefs(html):
    parser = ControlParser()
    parser.feed(html)
    return parser.hrefs


class HomeLinkTests(TestCase):
    def test_home_has_sprint_one_navigation_and_no_placeholder_link(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="#"')
        for url in (
            reverse("home"),
            reverse("search-page"),
            reverse("login-page"),
            reverse("party-create-page"),
            reverse("venues:venue_map"),
        ):
            with self.subTest(url=url):
                self.assertIn(url, hrefs(response.content.decode()))

    def test_search_page_renders_search_filters_and_marks_navigation(self):
        user = get_user_model().objects.create_user(username="search-page-user")
        self.client.force_login(user)
        response = self.client.get(reverse("search-page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "หาปาร์ตี้กีฬา ไปเล่นด้วยกัน")
        self.assertContains(response, "data-filter-sport")
        self.assertContains(response, "data-filter-venue")
        self.assertContains(response, "data-filter-date")
        self.assertContains(response, 'class="active" aria-current="page"')
        self.assertContains(response, "css/search.css")

    def test_search_page_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("search-page"))
        self.assertRedirects(
            response,
            f'{reverse("login-page")}?next=%2Fsearch%2F',
        )

    def test_create_party_redirects_to_login_and_returns_to_requested_page(self):
        response = self.client.get(
            reverse("party-create-page"),
            {"sport_id": "3", "venue_id": "8"},
        )
        self.assertRedirects(
            response,
            f'{reverse("login-page")}?next=%2Fparties%2Fnew%2F%3Fsport_id%3D3%26venue_id%3D8',
        )
        login_response = self.client.get(response.url)
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(
            login_response,
            'data-next-url="/parties/new/?sport_id=3&amp;venue_id=8"',
        )

    def test_login_page_ignores_external_next_url(self):
        response = self.client.get(reverse("login-page"), {"next": "https://example.com/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-next-url="{reverse("home")}"')

    def test_authenticated_user_can_open_create_party_page(self):
        user = get_user_model().objects.create_user(username="party-create-user")
        self.client.force_login(user)
        response = self.client.get(reverse("party-create-page"), {"sport_id": "3"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-sport-id="3"')

    def test_home_keeps_business_api_out_of_markup(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "/api/v1/")


class NavbarPartialTests(SimpleTestCase):
    def test_create_button_has_a_real_destination(self):
        html = render_to_string("partials/navbar.html", {"active": "home", "show_create": True})
        self.assertIn(f'href="{reverse("party-create-page")}"', html)
        self.assertNotIn('href="#"', html)

    def test_venues_link_uses_its_active_state(self):
        html = render_to_string("partials/navbar.html", {"active": "venues", "show_create": False})
        self.assertIn(f'href="{reverse("venues:venue_map")}" class="active"', html)
