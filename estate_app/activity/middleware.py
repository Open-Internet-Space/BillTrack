from .context import operation, current_operation


class ActivityContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Never read credential-bearing request bodies into history.
        actor = request.user if request.user.is_authenticated else None
        with operation(actor=actor, source='admin' if request.path.startswith('/admin/') else 'application',
                       reason='Application workflow'):
            return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        current_operation.get()['reason'] = f'{request.method} {request.resolver_match.view_name}'
