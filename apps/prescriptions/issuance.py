import hashlib
from django.db import transaction
from core.exceptions import ConflictError
from django.core.exceptions import ValidationError, PermissionDenied
from .models import IssuedDocument
from apps.visits.revisions import latest_signed_revision


def finalized_revision(visit):
    if visit.status not in {'final', 'locked'}:
        raise ValidationError({'visit': ['يجب اعتماد الزيارة قبل إصدار المستند']})
    revision = latest_signed_revision(visit)
    if not revision:
        raise ValidationError({'visit': ['لا توجد نسخة معتمدة وموقعة لهذه الزيارة']})
    return revision


@transaction.atomic
def record_document(visit, actor, kind, snapshot, pdf, signature='', stamp=''):
    from core.access import require_actor_permission
    actor = require_actor_permission(actor, 'edit_visit')
    if not isinstance(snapshot, dict) or not isinstance(pdf, bytes) or not pdf:
        raise ValidationError({'document': ['يلزم مستند وبيانات معاينة صالحان']})
    if actor.role not in {'admin', 'doctor'}:
        raise PermissionDenied('إصدار المستندات مخصص للطبيب المخول')
    if kind not in {'prescription', 'referral'}:
        raise ValidationError({'document_type': ['نوع مستند غير صالح']})
    from core.image_data import validate_embedded_image
    validate_embedded_image(signature, 'signature', required=kind == 'prescription')
    validate_embedded_image(stamp, 'stamp')
    from apps.visits.services import lock_visit
    visit = lock_visit(visit.pk, actor)
    actor = require_actor_permission(actor, 'edit_visit')
    permission = 'export_pdf' if kind == 'prescription' else 'view_referrals'
    if not actor.has_perm(permission):
        raise PermissionDenied('غير مصرح بإصدار المستند')
    if 'patient_version' in snapshot and visit.patient.version != snapshot['patient_version']:
        raise ConflictError('تغير ملف المريض؛ أعد معاينة المستند')
    if not visit.is_active or visit.deleted_at or visit.version != snapshot.get('visit_version'):
        raise ConflictError('تغيرت الزيارة؛ أعد المعاينة قبل إصدار المستند')
    revision = finalized_revision(visit)
    if snapshot.get('revision_id') != revision.pk:
        raise ValidationError({'visit': ['المستند لا يطابق النسخة المعتمدة']})
    snapshot = {'schema_version': 1, **snapshot}
    document = IssuedDocument(document_type=kind, revision=revision, issued_by=actor,
        snapshot=snapshot, checksum=hashlib.sha256(pdf).hexdigest(), pdf_data=pdf,
        signature_data=signature or '', stamp_data=stamp or '')
    from apps.patients.integrity import validate_links
    validate_links(document)
    document.full_clean()
    document.save()
    return document
