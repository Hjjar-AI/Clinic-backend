from core.constraints import check_constraint
from .choices import DocumentType
from django.conf import settings
from django.db import models
from core.models import ImmutableModel

class IssuedDocument(ImmutableModel):
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    revision = models.ForeignKey('visits.VisitRevision', on_delete=models.PROTECT, related_name='documents')
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_documents')
    issued_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()
    checksum = models.CharField(max_length=64)
    pdf_data = models.BinaryField()
    signature_data = models.TextField(blank=True)
    stamp_data = models.TextField(blank=True)

    def clean(self):
        super().clean()
        from core.json_schemas import validate_issued_snapshot
        from core.image_data import validate_embedded_image
        validate_issued_snapshot(self.snapshot)
        validate_embedded_image(self.signature_data, 'signature', required=self.document_type == 'prescription')
        validate_embedded_image(self.stamp_data, 'stamp')

    class Meta:
        constraints = [
            check_constraint(condition=models.Q(document_type__in=DocumentType.values), name='prescriptions_issueddocument_document_type_valid'),
        ]

