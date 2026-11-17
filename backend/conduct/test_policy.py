"""US14 No-show threshold rule, isolated from the database."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import IntegrityError
from django.test import SimpleTestCase

from .models import CREDIT_EVENT_UNIQUE_CONSTRAINT, ConductCreditEvent
from .policy import CREDIT_BASE, NO_SHOW_DEDUCTION, REPORT_WINDOW_DAYS, required_reporters
from .services import apply_credit_event


class RequiredReportersTests(SimpleTestCase):
    def test_more_than_half_with_a_minimum_of_two(self):
        """UT-US14-NS-01"""
        table = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 4, 10: 6}
        for eligible_count, expected in table.items():
            with self.subTest(eligible_count=eligible_count):
                self.assertEqual(required_reporters(eligible_count), expected)


class ApprovedCreditUnitTests(SimpleTestCase):
    def test_approved_constants(self):
        self.assertEqual((CREDIT_BASE, NO_SHOW_DEDUCTION, REPORT_WINDOW_DAYS), (100, -5, 7))

    def test_first_existing_and_negative_balances_use_the_approved_opening_balance(self):
        for before, expected in ((None, 95), (83, 78), (-2, -7)):
            with self.subTest(before=before):
                profile = SimpleNamespace(credit_score=before, save=Mock())
                with (
                    patch("conduct.services.UserProfile.objects") as profiles,
                    patch("conduct.services.ConductCreditEvent.objects") as events,
                    patch("conduct.services.transaction.atomic"),
                ):
                    profiles.select_for_update.return_value.filter.return_value.first.return_value = profile
                    event = apply_credit_event(
                        20, "party fixture", ConductCreditEvent.Kind.NO_SHOW_DEDUCTION, -5, "test"
                    )
                    self.assertIs(event, events.create.return_value)
                    self.assertEqual(profile.credit_score, expected)
                    profile.save.assert_called_once_with(update_fields=["credit_score"])

    def test_duplicate_event_does_not_change_or_save_the_balance(self):
        profile = SimpleNamespace(credit_score=95, save=Mock())
        with (
            patch("conduct.services.UserProfile.objects") as profiles,
            patch("conduct.services.ConductCreditEvent.objects") as events,
            patch("conduct.services.transaction.atomic"),
        ):
            profiles.select_for_update.return_value.filter.return_value.first.return_value = profile
            events.create.side_effect = IntegrityError(CREDIT_EVENT_UNIQUE_CONSTRAINT)
            event = apply_credit_event(
                20, "party fixture", ConductCreditEvent.Kind.NO_SHOW_DEDUCTION, -5, "test"
            )
        self.assertIsNone(event)
        self.assertEqual(profile.credit_score, 95)
        profile.save.assert_not_called()
