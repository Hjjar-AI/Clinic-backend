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

