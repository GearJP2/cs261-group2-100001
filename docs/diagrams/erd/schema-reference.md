# Schema reference

Baseline main `e0edf10`, 2026-11-14. Extracted from Django model metadata; no database connection or data export.
Domain models only; Django auth groups/permissions/admin/session tables omitted from the ER views. User inherits AbstractUser; diagram lists its local fields but omits framework many-to-many tables.
PK/FK/UK denote primary, foreign and single-column unique keys. Composite uniqueness is listed below. Optional parent cardinality means nullable FK, not permission to create dangling references.


## User
Table: `accounts_user`.

## UniversityIdentity
Table: `accounts_universityidentity`.
- `user_id` → `User`; on_delete=CASCADE; nullable=False.
- `unique_university_identity`: `('provider_key', 'subject')`.

## UserProfile
Table: `accounts_userprofile`.
- `user_id` → `User`; on_delete=CASCADE; nullable=False.
- `user_profile_name_not_empty`: `(NOT (AND: ('display_name', '')))`.
- `user_profile_name_not_blank`: `(NOT (AND: ('display_name__regex', '^\\s*$')))`.
- `user_profile_rating_sum_gte_0`: `(AND: ('rating_sum__gte', 0))`.
- `user_profile_rating_count_gte_0`: `(AND: ('rating_count__gte', 0))`.

## UserSportInterest
Table: `accounts_usersportinterest`.
- `user_id` → `User`; on_delete=CASCADE; nullable=False.
- `sport_id` → `Sport`; on_delete=CASCADE; nullable=False.
- `unique_user_sport_interest`: `('user', 'sport')`.

## Sport
Table: `venues_sport`.

## Venue
Table: `venues_venue`.

## VenueSport
Table: `venues_venuesport`.
- `venue_id` → `Venue`; on_delete=CASCADE; nullable=False.
- `sport_id` → `Sport`; on_delete=PROTECT; nullable=False.
- `unique_venue_sport`: `('venue', 'sport')`.

## VenueOpeningHour
Table: `venues_venueopeninghour`.
- `venue_id` → `Venue`; on_delete=CASCADE; nullable=False.
- `venue_hour_valid_weekday`: `(AND: ('weekday__gte', 0), ('weekday__lte', 6))`.
- `venue_hour_close_after_open`: `(AND: ('closes_at__gt', F(opens_at)))`.
- `unique_venue_hour_start`: `('venue', 'weekday', 'opens_at')`.

## Party
Table: `parties_party`.
- `host_id` → `User`; on_delete=PROTECT; nullable=False.
- `sport_id` → `Sport`; on_delete=PROTECT; nullable=False.
- `venue_id` → `Venue`; on_delete=PROTECT; nullable=False.
- `party_capacity_gte_1`: `(AND: ('capacity__gte', 1))`.
- `party_end_after_start`: `(AND: ('ends_at__gt', F(starts_at)))`.
- Index `parties_par_sport_i_13983d_idx`: `['sport', 'starts_at']`.

## PartyMembership
Table: `parties_partymembership`.
- `party_id` → `Party`; on_delete=CASCADE; nullable=False.
- `user_id` → `User`; on_delete=PROTECT; nullable=False.
- `unique_party_membership`: `('party', 'user')`.
- Index `parties_par_party_i_515d7f_idx`: `['party', 'left_at']`.

## JoinRequest
Table: `parties_joinrequest`.
- `party_id` → `Party`; on_delete=CASCADE; nullable=False.
- `user_id` → `User`; on_delete=PROTECT; nullable=False.
- `decided_by_id` → `User`; on_delete=SET_NULL; nullable=True.
- `unique_party_join_request`: `('party', 'user')`.
- `join_request_valid_decision`: `(OR: (AND: ('decided_at__isnull', True), ('decided_by__isnull', True), ('status', 'Pending')), (AND: ('decided_at__isnull', False), ('status__in', ['Approved', 'Rejected'])))`.
- Index `parties_joi_party_i_610537_idx`: `['party', 'status', 'created_at']`.

## PartyReview
Table: `conduct_partyreview`.
- `party_id` → `Party`; on_delete=PROTECT; nullable=False.
- `reviewer_id` → `User`; on_delete=PROTECT; nullable=False.
- `reviewee_id` → `User`; on_delete=PROTECT; nullable=False.
- `unique_party_review`: `('party', 'reviewer', 'reviewee')`.
- `party_review_rating_1_to_5`: `(AND: ('rating__gte', 1), ('rating__lte', 5))`.
- `party_review_not_self`: `(NOT (AND: ('reviewer', F(reviewee))))`.
- Index `review_reviewee_created_idx`: `['reviewee', 'created_at']`.

## NoShowReport
Table: `conduct_noshowreport`.
- `party_id` → `Party`; on_delete=CASCADE; nullable=False.
- `reporter_id` → `User`; on_delete=PROTECT; nullable=False.
- `reported_id` → `User`; on_delete=PROTECT; nullable=False.
- `unique_no_show_report`: `('party', 'reporter', 'reported')`.
- `no_show_report_not_self`: `(NOT (AND: ('reporter', F(reported))))`.
- Index `no_show_party_reported_idx`: `['party', 'reported']`.

## ConductCreditEvent
Table: `conduct_conductcreditevent`.
- `user_id` → `User`; on_delete=PROTECT; nullable=False.
- `party_id` → `Party`; on_delete=SET_NULL; nullable=True.
- `created_by_id` → `User`; on_delete=SET_NULL; nullable=True.
- `unique_conduct_credit_event`: `('party', 'user', 'kind')`.
- `credit_event_delta_not_zero`: `(NOT (AND: ('delta', 0)))`.
- Index `credit_event_user_created_idx`: `['user', 'created_at']`.

## Service rules beyond SQL constraints
- Active membership: left_at IS NULL. Capacity is enforced under Party locks, not a cross-table SQL CHECK.
- Review rating cache is updated atomically with review insertion. Reviewed Party deletion is PROTECT.
- Credit ledger append-only is a service convention, not an immutable-table database trigger. No-show policy: opening balance 100 when NULL then -5; existing balance + delta.
- kind choices include AdminAdjustment/AppealReversal but no corresponding API is implemented. Composite unique with nullable party permits multiple NULL-party rows.
- Django blank/default/choices and service validation are not all database constraints; see models and migrations for the distinction.
