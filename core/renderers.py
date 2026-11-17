from rest_framework.renderers import JSONRenderer


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Wraps all JSON responses in a consistent envelope.

    - If the response already contains a top-level 'data' or 'error' key,
      it is returned unchanged (to avoid double wrapping).
    - Otherwise, the original data is wrapped under a 'data' key.
    """
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get('response')
        if response is not None and response.status_code in (204, 205, 304):
            # These statuses cannot carry an envelope. Sending JSON after a
            # 204 breaks persistent HTTP connections and proxy parsing.
            return b''
        from .collections import normalize_collection
        request = (renderer_context or {}).get('request')
        if request and request.method == 'GET' and response is not None and response.status_code < 300:
            if isinstance(data, dict) and 'data' in data:
                data = {**data, 'data': normalize_collection(data['data'], request)}
            else:
                data = normalize_collection(data, request)
        if isinstance(data, dict) and ('data' in data or 'error' in data):
            return super().render(data, accepted_media_type, renderer_context)
        return super().render({'data': data}, accepted_media_type, renderer_context)
