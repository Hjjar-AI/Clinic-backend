import hashlib
import hmac
import json
import re
from django.conf import settings


def payload_bytes(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class BackupValidationService:
    def _sign_data(self, data):
        return hmac.new(settings.BACKUP_HMAC_KEY.encode(), data, hashlib.sha256).hexdigest()

    def verify_signature(self, data, signature):
        return (isinstance(signature, str) and re.fullmatch(r'[0-9a-f]{64}', signature) is not None
                and hmac.compare_digest(self._sign_data(data), signature))

    def verify_envelope(self, envelope):
        if not isinstance(envelope, dict) or not isinstance(envelope.get('data'), dict):
            raise ValueError('Invalid backup envelope')
        data = envelope['data']
        # Legacy JSON exports signed the indented inner object.
        signatures = (payload_bytes(data), json.dumps(data, ensure_ascii=False, indent=2).encode())
        if not any(self.verify_signature(raw, envelope.get('signature')) for raw in signatures):
            raise ValueError('Backup signature verification failed')
        return data
