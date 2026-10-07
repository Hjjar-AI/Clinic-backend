import contextvars

_request_var = contextvars.ContextVar('current_request', default=None)

def get_current_request():
    return _request_var.get()

def set_current_request(request):
    _request_var.set(request)