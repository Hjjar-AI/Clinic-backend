"""Real HTTP boundaries for patient scope, corrections, teams and uploads."""
import hashlib
import uuid
from django.contrib.auth.models import Permission
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.patients.models import PatientContact, PatientCorrection, PatientDocument, PatientMerge
from apps.accounts.services import UserService
from core.models import IdempotencyOperation
from .base import ClinicTestCase, PASSWORD


class PatientHTTPFixtures(ClinicTestCase):
    def url(self, suffix='', patient=None):
        return f'/api/v1/patients/{(patient or self.patient).pk}/{suffix}'

    def record(self, fields, version=1, kind='contacts', **extra):
        return self.write('post', self.url('records/'), {
            'kind': kind, 'fields': fields, 'version': version, **extra,
        })

    def status(self, response, expected):
        self.assertEqual(response.status_code, expected, response.content)


class LongitudinalHTTPTests(PatientHTTPFixtures):
    def test_create_edit_retire_retains_history_and_parent_versions(self):
        created = self.record({'name': 'Synthetic contact', 'is_primary': True})
        self.status(created, 200)
        row = created.json()['data']['record']
        self.assertEqual(created['X-Resource-Version'], '2')
        self.status(self.record({'name': 'Corrected contact'}, 2, record_id=row['id'], reason='Correction'), 200)
        self.status(self.record({}, 3, record_id=row['id'], operation='retire', reason='No longer current'), 200)
        listed = self.api.get(self.url('records/'), {'kind': 'contacts'}).json()['data']
        self.assertEqual(listed['version'], 4)
        self.assertEqual(listed['total'], 1)
        self.assertFalse(listed['items'][0]['is_active'])
        self.assertEqual(listed['items'][0]['retirement_reason'], 'No longer current')
        history = self.api.get(self.url('corrections/')).json()['data']
        self.assertEqual(history['total'], 3)
        self.assertEqual(history['items'][0]['reason'], 'No longer current')
        self.assertEqual(history['items'][1]['changes']['name']['before'], 'Synthetic contact')

    def test_missing_and_stale_versions_leave_inventory_unchanged(self):
        self.status(self.write('post', self.url('records/'), {'kind': 'contacts', 'fields': {'name': 'Synthetic'}}), 400)
        self.status(self.record({'name': 'Synthetic'}, 9), 409)
        self.assertFalse(PatientContact.objects.exists())
        self.assertFalse(PatientCorrection.objects.exists())
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 1)

    def test_replay_does_not_duplicate_history_or_bump_version(self):
        payload = {'kind': 'contacts', 'fields': {'name': 'Synthetic'}, 'version': 1}
        first = self.write('post', self.url('records/'), payload, 'suite-record-replay')
        replay = self.write('post', self.url('records/'), payload, 'suite-record-replay')
        self.status(first, 200)
        self.assertEqual(replay.content, first.content)
        self.assertEqual(replay['X-Idempotency-Replayed'], 'true')
        self.assertEqual(PatientContact.objects.count(), 1)
        self.assertEqual(PatientCorrection.objects.count(), 1)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 2)

    def test_invalid_shapes_operations_and_protected_fields_are_atomic(self):
        invalid = [
            {'kind': 'unsupported', 'fields': {}},
            {'kind': 'contacts', 'fields': []},
            {'kind': 'contacts', 'fields': {'name': 'Synthetic', 'patient': self.patient.pk}},
            {'kind': 'contacts', 'fields': {'name': 'Synthetic'}, 'operation': 'delete'},
            {'kind': 'contacts', 'fields': {}, 'operation': 'retire'},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.status(self.write('post', self.url('records/'), {**payload, 'version': 1}), 400)
        self.assertFalse(PatientContact.objects.exists())
        self.assertFalse(PatientCorrection.objects.exists())

    def test_second_primary_failure_preserves_first_contact_and_version(self):
        self.status(self.record({'name': 'First', 'is_primary': True}), 200)
        self.status(self.record({'name': 'Second', 'is_primary': True}, 2), 400)
        self.assertEqual(list(PatientContact.objects.values_list('name', flat=True)), ['First'])
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 2)

    def test_cross_patient_record_id_cannot_edit_or_retire(self):
        other = self.patient_for()
        created = self.write('post', self.url('records/', other), {'kind': 'contacts', 'fields': {'name': 'Other'}, 'version': 1})
        self.status(created, 200)
        identifier = created.json()['data']['record']['id']
        for operation in ('save', 'retire'):
            with self.subTest(operation=operation):
                self.status(self.record({'name': 'Injected'}, record_id=identifier, operation=operation, reason='Synthetic'), 400)
        row = PatientContact.objects.get(pk=identifier)
        self.assertEqual(row.name, 'Other')
        self.assertTrue(row.is_active)

    def test_retired_record_cannot_be_changed_or_reactivated(self):
        row = self.record({'name': 'Synthetic'}).json()['data']['record']
        self.status(self.record({}, 2, record_id=row['id'], operation='retire', reason='Finished'), 200)
        self.status(self.record({'name': 'Reopened'}, 3, record_id=row['id'], reason='Reopen'), 400)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 3)

    def test_invalid_list_kind_and_offset_rejected(self):
        for query in ({'kind': 'invalid'}, {'kind': 'contacts', 'offset': 'invalid'}):
            with self.subTest(query=query):
                self.status(self.api.get(self.url('records/'), query), 400)

    def test_unassigned_doctor_cannot_read_or_write_records(self):
        self.api.force_login(self.other_doctor)
        self.status(self.api.get(self.url('records/'), {'kind': 'contacts'}), 404)
        self.status(self.record({'name': 'Unauthorized'}), 404)
        self.assertFalse(PatientContact.objects.exists())

    def test_user_without_clinical_permissions_cannot_read_write_or_see_clinical_corrections(self):
        self.patient = self.patient_for(self.receptionist)
        self.status(self.record({'substance': 'Synthetic allergen'}, kind='allergies'), 200)
        self.receptionist.groups.clear()
        self.receptionist.user_permissions.set(Permission.objects.filter(codename__in=['view_patients', 'edit_patient']))
        self.receptionist.clear_permission_cache()
        self.api.force_login(self.receptionist)
        self.status(self.api.get(self.url('records/'), {'kind': 'allergies'}), 403)
        self.status(self.record({'substance': 'Unauthorized'}, 2, kind='allergies'), 403)
        history = self.api.get(self.url('corrections/'))
        self.status(history, 200)
        self.assertEqual(history.json()['data']['total'], 0)

    def test_default_receptionist_can_read_clinical_records_but_cannot_change_them(self):
        self.patient = self.patient_for(self.receptionist)
        self.status(self.record({'substance': 'Synthetic allergen'}, kind='allergies'), 200)
        self.api.force_login(self.receptionist)
        listed = self.api.get(self.url('records/'), {'kind': 'allergies'})
        self.status(listed, 200)
        self.assertEqual(listed.json()['data']['items'][0]['substance'], 'Synthetic allergen')
        self.status(self.record({'substance': 'Unauthorized'}, 2, kind='allergies'), 403)

    def test_verification_is_server_owned_and_identity_edit_demotes_it(self):
        created = self.record({'identifier_type': 'passport', 'value': 'SYNTHETIC', 'verification': 'verified'}, kind='identifiers')
        self.status(created, 200)
        row = created.json()['data']['record']
        self.assertEqual(row['verified_by'], self.admin.pk)
        self.assertIsNotNone(row['verified_at'])
        changed = self.record({'value': 'CORRECTED'}, 2, kind='identifiers', record_id=row['id'], reason='New document')
        self.status(changed, 200)
        changed = changed.json()['data']['record']
        self.assertEqual(changed['verification'], 'reported')
        self.assertIsNone(changed['verified_by'])
        self.assertIsNone(changed['verified_at'])

    def test_receptionist_cannot_self_verify_identity(self):
        self.patient = self.patient_for(self.receptionist)
        self.api.force_login(self.receptionist)
        self.status(self.record({'identifier_type': 'passport', 'value': 'SYNTHETIC', 'verification': 'verified'}, kind='identifiers'), 403)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 1)

    def test_followup_rejects_foreign_visit_and_nonmember_owner(self):
        foreign_visit = self.visit_for(self.patient_for(), self.admin)
        for fields in ({'source_visit': foreign_visit.pk}, {'owner': self.other_doctor.pk}):
            with self.subTest(fields=fields):
                self.status(self.record({'title': 'Synthetic followup', 'due_date': '2026-10-20', **fields}, kind='follow-ups'), 400)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 1)

    def test_all_record_kinds_roundtrip_through_http_serializers(self):
        cases = {
            'identifiers': {'identifier_type': 'passport', 'value': 'SYNTHETIC'},
            'contacts': {'name': 'Synthetic contact', 'is_emergency': True},
            'representatives': {'name': 'Synthetic representative', 'relationship': 'guardian', 'authority_scope': 'contact'},
            'allergies': {'substance': 'Synthetic allergen', 'status': 'confirmed'},
            'medications': {'name': 'Synthetic medication', 'status': 'active'},
            'follow-ups': {'title': 'Synthetic action', 'due_date': '2026-10-20'},
        }
        for version, (kind, fields) in enumerate(cases.items(), start=1):
            with self.subTest(kind=kind):
                self.status(self.record(fields, version, kind), 200)
                listed = self.api.get(self.url('records/'), {'kind': kind}).json()['data']
                self.assertEqual(listed['version'], version + 1)
                self.assertEqual(listed['total'], 1)
                for key, value in fields.items():
                    self.assertEqual(listed['items'][0][key], value)

    def test_representative_invalid_date_range_is_atomic(self):
        self.status(self.record({'name': 'Synthetic', 'relationship': 'guardian', 'authority_scope': 'contact',
            'valid_from': '2026-10-20', 'valid_until': '2026-10-01'}, kind='representatives'), 400)
        self.assertFalse(PatientCorrection.objects.exists())
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 1)


class CareTeamHTTPTests(PatientHTTPFixtures):
    def add_member(self, version=1, key=None):
        return self.write('post', self.url('care_team_add/'), {
            'user_id': self.other_doctor.pk, 'role': 'doctor', 'version': version,
        }, key)

    def test_dated_membership_controls_real_http_access_after_removal(self):
        self.status(self.add_member(), 201)
        self.api.force_login(self.other_doctor)
        self.status(self.api.get(self.url()), 200)
        self.api.force_login(self.admin)
        removed = self.write('delete', self.url(f'care-team/{self.other_doctor.pk}/'), {'version': 2, 'reason': 'Reassigned'})
        self.status(removed, 204)
        self.assertEqual(removed['X-Resource-Version'], '3')
        history = self.api.get(self.url('care_team/')).json()['data']
        former = next(row for row in history['care_team'] if row['user'] == self.other_doctor.pk)
        self.assertEqual(history['version'], 3)
        self.assertEqual(former['removal_reason'], 'Reassigned')
        self.assertIsNotNone(former['ended_at'])
        self.api.force_login(self.other_doctor)
        self.status(self.api.get(self.url()), 404)

    def test_stale_add_remove_preserve_membership(self):
        self.status(self.add_member(9), 409)
        self.status(self.add_member(), 201)
        self.status(self.write('delete', self.url(f'care-team/{self.other_doctor.pk}/'), {'version': 1}), 409)
        self.assertTrue(self.patient.care_team.filter(user=self.other_doctor, ended_at__isnull=True).exists())

    def test_replay_has_one_membership_and_preserves_version_header(self):
        first = self.add_member(key='suite-team-replay')
        second = self.add_member(key='suite-team-replay')
        self.status(first, 201)
        self.assertEqual(first.content, second.content)
        self.assertEqual(second['X-Resource-Version'], '2')
        self.assertEqual(self.patient.care_team.filter(user=self.other_doctor).count(), 1)

    def test_doctor_cannot_manage_team_even_with_patient_access(self):
        self.api.force_login(self.doctor)
        self.status(self.add_member(), 403)
        self.status(self.write('delete', self.url(f'care-team/{self.doctor.pk}/'), {'version': 1}), 403)


class PatientDocumentHTTPTests(PatientHTTPFixtures):
    PDF = b'%PDF-1.4\n% Synthetic document\n1 0 obj\n<<>>\nendobj\n%%EOF\n'

    def document_url(self, identifier, patient=None):
        return self.url(f'documents/{identifier}/', patient)

    def upload(self, content=None, **metadata):
        return self.api.post(self.url('documents/'), {
            'file': SimpleUploadedFile('synthetic.pdf', self.PDF if content is None else content, 'application/pdf'), **metadata,
        }, format='multipart', HTTP_X_IDEMPOTENCY_KEY=f'suite-upload-{uuid.uuid4()}')

    def test_upload_download_provenance_checksum_and_independent_version(self):
        response = self.upload(source='Synthetic lab', provider='Synthetic provider', verification='verified', document_date='2026-10-11')
        self.status(response, 201)
        row = response.json()['data']
        self.assertEqual(row['version'], 1)
        self.assertEqual(row['verified_by'], self.admin.pk)
        document = PatientDocument.objects.get(pk=row['id'])
        self.assertEqual(document.checksum, hashlib.sha256(self.PDF).hexdigest())
        downloaded = self.api.get(self.document_url(row['id']) + 'download/')
        self.assertEqual(downloaded.status_code, 200)
        try:
            self.assertEqual(b''.join(downloaded.streaming_content) if downloaded.streaming else downloaded.content, self.PDF)
        finally:
            if not downloaded.closed:
                downloaded.close()
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 1)

    def test_metadata_edit_requires_document_version_and_retains_original_bytes(self):
        row = self.upload(verification='verified', source='Original').json()['data']
        url = self.document_url(row['id'])
        self.status(self.write('patch', url, {'source': 'Corrected', 'version': 1}), 200)
        self.status(self.write('patch', url, {'source': 'Stale', 'version': 1}), 409)
        document = PatientDocument.objects.get(pk=row['id'])
        self.assertEqual(document.source, 'Corrected')
        self.assertEqual(document.verification, 'reported')
        self.assertIsNone(document.verified_by)
        self.assertEqual(document.version, 2)
        with default_storage.open(document.filepath, 'rb') as stored:
            self.assertEqual(stored.read(), self.PDF)

    def test_archive_requires_version_and_retains_file(self):
        row = self.upload().json()['data']
        url = self.document_url(row['id'])
        self.status(self.write('delete', url), 400)
        self.status(self.write('delete', url, {'version': 9}), 409)
        self.status(self.write('delete', url, {'version': 1}), 204)
        document = PatientDocument.all_objects.get(pk=row['id'])
        self.assertIsNotNone(document.deleted_at)
        self.assertTrue(default_storage.exists(document.filepath))
        self.status(self.api.get(url), 404)

    def test_cross_patient_document_routes_cannot_read_write_or_download(self):
        row = self.upload().json()['data']
        url = self.document_url(row['id'], self.patient_for())
        self.status(self.api.get(url), 404)
        self.status(self.api.get(url + 'download/'), 404)
        self.status(self.write('patch', url, {'description': 'Injected', 'version': 1}), 404)
        self.status(self.write('delete', url, {'version': 1}), 404)
        self.assertEqual(PatientDocument.objects.get(pk=row['id']).version, 1)

    def test_unassigned_doctor_cannot_upload_read_or_download(self):
        row = self.upload().json()['data']
        self.api.force_login(self.other_doctor)
        self.status(self.upload(), 404)
        self.status(self.api.get(self.url('documents/')), 404)
        self.status(self.api.get(self.document_url(row['id']) + 'download/'), 404)
        self.assertEqual(PatientDocument.objects.count(), 1)

    def test_invalid_mime_and_metadata_leave_no_rows_or_orphans(self):
        for arguments in ({'content': b'plain synthetic text'}, {'category': 'x' * 51}, {'document_date': 'not-a-date'}):
            with self.subTest(arguments=arguments):
                self.status(self.upload(**arguments), 400)
        self.assertFalse(PatientDocument.all_objects.exists())
        self.assertEqual([path for path in settings.MEDIA_ROOT.rglob('*') if path.is_file()], [])

    def test_missing_stored_document_returns_not_found(self):
        row = self.upload().json()['data']
        document = PatientDocument.objects.get(pk=row['id'])
        default_storage.delete(document.filepath)
        self.status(self.api.get(self.document_url(row['id']) + 'download/'), 404)

    def test_archive_and_idempotent_replay_store_and_return_no_content(self):
        row = self.upload().json()['data']
        url = self.document_url(row['id'])
        first = self.write('delete', url, {'version': 1}, 'suite-empty-archive-replay')
        replay = self.write('delete', url, {'version': 1}, 'suite-empty-archive-replay')
        self.status(first, 204)
        self.status(replay, 204)
        self.assertEqual(first.content, b'')
        self.assertEqual(replay.content, b'')
        operation = IdempotencyOperation.objects.get(key='suite-empty-archive-replay')
        # Django's test client itself strips 204 bodies. Inspect what the
        # middleware persisted before that stripping to protect the real wire.
        self.assertEqual(bytes(operation.response_body), b'')
        self.assertEqual(replay['X-Idempotency-Replayed'], 'true')


class MergeHTTPTests(PatientHTTPFixtures):
    def preview(self, target):
        response = self.write('post', self.url('merge_preview/'), {'target_id': target.pk})
        self.status(response, 200)
        return response.json()['data']

    def merge(self, preview, **changes):
        return self.write('post', self.url('merge/'), {
            'token': preview['token'], 'reason': 'Same synthetic person',
            'version': preview['version'], 'target_version': preview['target_version'], **changes,
        })

    def test_http_merge_preserves_signed_snapshot_and_survivor_identity(self):
        target = self.patient_for(first_name='Survivor')
        visit = self.visit_for(status='final')
        snapshot = visit.revisions.get().snapshot
        response = self.merge(self.preview(target))
        self.status(response, 200)
        self.assertEqual(response.json()['data']['id'], target.pk)
        self.assertEqual(response.json()['data']['first_name'], 'Survivor')
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
        self.assertEqual(self.patient.merged_into_id, target.pk)
        visit.refresh_from_db()
        self.assertEqual(visit.patient_id, target.pk)
        self.assertEqual(visit.revisions.get().snapshot, snapshot)
        self.assertEqual(PatientMerge.objects.count(), 1)

    def test_target_changes_invalidate_preview_without_partial_merge(self):
        target = self.patient_for()
        preview = self.preview(target)
        changed = self.write('patch', self.url(patient=target), {'occupation': 'New value', 'version': 1})
        self.status(changed, 200)
        self.status(self.merge(preview, target_version=2), 409)
        self.assertFalse(PatientMerge.objects.exists())
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

    def test_source_content_changes_invalidate_http_preview(self):
        preview = self.preview(self.patient_for())
        self.visit_for()
        self.status(self.merge(preview), 409)
        self.assertFalse(PatientMerge.objects.exists())

    def test_preview_is_bound_to_the_requesting_admin(self):
        preview = self.preview(self.patient_for())
        other_admin = UserService().create_user('other_merge_admin', PASSWORD, 'Synthetic admin', 'admin')
        other_admin.force_password_change = False
        other_admin.save(update_fields=['force_password_change'])
        self.api.force_login(other_admin)
        self.status(self.merge(preview), 400)
        self.assertFalse(PatientMerge.objects.exists())

    def test_missing_reason_tampered_token_and_missing_target_version_are_atomic(self):
        preview = self.preview(self.patient_for())
        for changes in ({'reason': ''}, {'token': 'tampered'}, {'target_version': None}):
            with self.subTest(changes=changes):
                self.status(self.merge(preview, **changes), 400)
        self.assertFalse(PatientMerge.objects.exists())

    def test_nonadmin_cannot_preview_or_execute_merge(self):
        target = self.patient_for()
        preview = self.preview(target)
        self.api.force_login(self.doctor)
        self.status(self.write('post', self.url('merge_preview/'), {'target_id': target.pk}), 403)
        self.status(self.merge(preview), 403)
