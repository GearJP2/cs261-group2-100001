"""US14 No-show threshold rule, isolated from the database."""

from django.test import SimpleTestCase

from .policy import required_reporters


class RequiredReportersTests(SimpleTestCase):
    def test_more_than_half_with_a_minimum_of_two(self):
        """UT-US14-NS-01"""
        table = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 4, 10: 6}
        for eligible_count, expected in table.items():
            with self.subTest(eligible_count=eligible_count):
                self.assertEqual(required_reporters(eligible_count), expected)
