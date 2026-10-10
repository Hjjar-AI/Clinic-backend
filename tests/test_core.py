from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase
from core.constraints import check_constraint
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition, transition_reason, lifecycle_payload
from core.mutation import parse_version, request_version, check_mutation
from core.normalization import normalize_identifier, normalize_phone, normalized_search_text
from core.query_utils import parse_date_range
from apps.visits.input_validation import clinical_object, text
from apps.visits.lab_validation import normalize_lab_values


class MutationTests(SimpleTestCase):
    def test_positive_integer_and_ascii_string_versions(self):
        for value in (1, 42, '1', '0042'):
            with self.subTest(value=value):
                self.assertEqual(parse_version(value), int(value))

    def test_lossy_or_malformed_versions_rejected(self):
        for value in (True, False, 0, -1, 1.0, None, [], {}, '', '1.0', ' 1', '+1', '١', '1' * 21):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                parse_version(value)

    def test_quoted_if_match_and_body_agree(self):
        self.assertEqual(request_version(SimpleNamespace(data={'version': 2}, headers={'If-Match': '"2"'})), 2)
        self.assertEqual(request_version(SimpleNamespace(data={}, headers={'If-Match': '3'})), 3)

    def test_missing_or_conflicting_request_versions(self):
        for data, headers in (({}, {}), ({'version': 2}, {'If-Match': '3'}), ({}, {'If-Match': 'W/"2"'})):
            with self.subTest(data=data, headers=headers), self.assertRaises(ValidationError):
                request_version(SimpleNamespace(data=data, headers=headers))

    def test_stale_or_archived_mutations_conflict(self):
        for record, version in ((SimpleNamespace(version=2), 1),
                                (SimpleNamespace(version=1, is_active=False), 1)):
            with self.assertRaises(ConflictError):
                check_mutation(record, version)
        check_mutation(SimpleNamespace(version=1, is_active=True, deleted_at=None), 1)

    def test_native_constraints_clone_without_wrapper_serialization(self):
        constraint = check_constraint(condition=models.Q(version__gte=1), name='suite_version')
        self.assertIs(type(constraint), models.CheckConstraint)
        self.assertEqual(constraint.clone(), constraint)
        self.assertEqual(constraint.deconstruct()[0], 'django.db.models.CheckConstraint')

    def test_legacy_constraint_keyword(self):
        with patch('core.constraints.VERSION', (5, 0)), patch('core.constraints.models.CheckConstraint') as constructor:
            check_constraint(condition=models.Q(version__gte=1), name='suite_version')
        self.assertIn('check', constructor.call_args.kwargs)
        self.assertNotIn('condition', constructor.call_args.kwargs)


class ValidationTests(SimpleTestCase):
    def test_lifecycle_terminal_and_repeat_behavior(self):
        self.assertTrue(enforce_transition('appointment', 'scheduled', 'confirmed'))
        self.assertFalse(enforce_transition('visit', 'locked', 'locked'))
        with self.assertRaises(ValidationError):
            enforce_transition('invoice', 'paid', 'draft')
        for target in ([], {}, None, True, 'invented'):
            with self.subTest(target=target), self.assertRaises(ValidationError):
                enforce_transition('task', 'open', target)

    def test_cancellation_reason_bounded_and_required(self):
        self.assertEqual(transition_reason('  reason  ', True), 'reason')
        for value in ('', ' ', 'x' * 501, 42, []):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                transition_reason(value, True)

    def test_lifecycle_metadata_for_terminal_states(self):
        self.assertTrue(lifecycle_payload()['visit_status']['locked']['terminal'])
        self.assertEqual(lifecycle_payload()['invoice_status']['paid']['allowed_transitions'], [])

    def test_arabic_identifiers_and_search_normalization(self):
        self.assertEqual(normalize_identifier(' ١٢٣-۴۵۶  '), '123456')
        self.assertEqual(normalized_search_text('أحمد'), normalized_search_text('احمد'))
        self.assertEqual(normalize_phone('٠٩٤٤١٢٣٤٥٦'), '+963944123456')

    def test_date_ranges_reject_reversed_and_invalid_dates(self):
        for values in ({'date_from': 'invalid'}, {'date_from': '2026-01-02', 'date_to': '2026-01-01'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                parse_date_range(values)
        self.assertEqual(parse_date_range({}), (None, None))

    def test_clinical_json_rejects_invalid_or_oversized_values(self):
        for value in ([], {'mse': 4}, {'formulation': []}, {'answer': float('nan')}, {'mse': 'x' * 50_001}):
            with self.subTest(value_type=type(value)), self.assertRaises(ValidationError):
                clinical_object(value)
        self.assertEqual(clinical_object({'mse': 'Synthetic'}), {'mse': 'Synthetic'})

    def test_text_trim_and_type_validation(self):
        self.assertEqual(text(None, 'field', 3), '')
        self.assertEqual(text(' a ', 'field', 3), 'a')
        for value in (3, 'long'):
            with self.assertRaises(ValidationError):
                text(value, 'field', 3)

    def test_pending_lab_needs_no_fabricated_result(self):
        values = normalize_lab_values([{'name': 'CBC', 'date': '2026-01-01', 'status': 'pending'}], True)
        self.assertEqual(values[0]['value'], '')

    def test_completed_lab_requires_result_and_valid_date(self):
        for row in ({'name': 'CBC', 'date': '2026-01-01', 'status': 'normal'},
                    {'name': 'CBC', 'date': '2026-02-30', 'status': 'pending'},
                    {'name': 'CBC', 'date': '2026-01-01', 'status': 'invalid'}):
            with self.subTest(row=row), self.assertRaises(ValidationError):
                normalize_lab_values([row], True)
