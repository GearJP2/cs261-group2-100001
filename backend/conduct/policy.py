"""No-show and conduct credit policy.

Approved by Gear on 2026-11-13 (issues #100/#105, PR #129).
See docs/us14-no-show-approved-policy.md. Deployment remains separately controlled
by settings.NO_SHOW_ENABLED, which defaults to false.
"""

# Approved policy: credit change per deduction.
NO_SHOW_DEDUCTION = -5

# Approved policy: starting balance, used only when
# credit_score is NULL at the first deduction (new value = CREDIT_BASE + delta).
CREDIT_BASE = 100

# Approved policy: reports are accepted from
# party.ends_at until ends_at + this many days.
REPORT_WINDOW_DAYS = 7


def required_reporters(eligible_count):
    """Approved policy: "more than half", minimum 2.

    eligible_count is the party's participants excluding the reported user. A lone
    eligible participant can decide alone.
    """
    if eligible_count == 1:
        return 1
    return max(2, eligible_count // 2 + 1)
