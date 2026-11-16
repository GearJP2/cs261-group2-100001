from django.template.loader import render_to_string
from django.test import SimpleTestCase


class ProfileAssetTests(SimpleTestCase):
    def test_profile_loads_api_helper_before_review_script(self):
        html = render_to_string(
            "profile.html",
            {"profile": {"id": 7, "name": "Player", "credit": None, "interests": []}},
        )
        self.assertIn('data-user-id="7"', html)
        helper = '<script src="/static/js/app.js" defer></script>'
        reviews = '<script src="/static/js/profile-reviews.js" defer></script>'
        self.assertIn(helper, html)
        self.assertIn(reviews, html)
        self.assertLess(html.index(helper), html.index(reviews))
