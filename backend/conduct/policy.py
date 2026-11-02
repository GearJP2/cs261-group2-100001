"""No-show and conduct credit policy.

PROPOSAL, pending team confirmation (issue #100/#105). Every value below is unconfirmed
and is the only place these numbers live; change them here. The feature stays behind
settings.NO_SHOW_ENABLED until they are confirmed.
"""

# PROPOSAL, pending team confirmation (issue #100/#105): credit change per deduction.
NO_SHOW_DEDUCTION = -5

# PROPOSAL, pending team confirmation (issue #100/#105): starting balance, used only when
# credit_score is NULL at the first deduction (new value = CREDIT_BASE + delta).
CREDIT_BASE = 100

# PROPOSAL, pending team confirmation (issue #100/#105): reports are accepted from
# party.ends_at until ends_at + this many days.
REPORT_WINDOW_DAYS = 7


def required_reporters(eligible_count):
    """PROPOSAL, pending team confirmation (issue #100/#105): "more than half", minimum 2.

    eligible_count is the party's participants excluding the reported user. A lone
    eligible participant can decide alone.
    """
    if eligible_count == 1:
        return 1
    return max(2, eligible_count // 2 + 1)
