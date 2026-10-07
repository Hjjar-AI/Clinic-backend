# backend/apps/backup/backup_validation.py
import hmac
import hashlib
from django.conf import settings

class BackupValidationService:
    def _sign_data(self, data: bytes) -> str:
        key = settings.BACKUP_HMAC_KEY.encode('utf-8')
        return hmac.new(key, data, hashlib.sha256).hexdigest()

    def verify_signature(self, data: bytes, signature: str) -> bool:
        expected = self._sign_data(data)
        return hmac.compare_digest(expected, signature)