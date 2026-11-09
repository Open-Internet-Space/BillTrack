"""Safe user-facing failures with references that can be found in server logs."""
import logging
import traceback
import uuid

from django.http import JsonResponse
from django.shortcuts import render


def reference(request):
    if not getattr(request, 'error_reference', None):
        request.error_reference = uuid.uuid4().hex
    return request.error_reference


class RequestReferenceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reference(request)
        response = self.get_response(request)
        response['X-Request-ID'] = request.error_reference
        if response.status_code >= 400:
            response['Cache-Control'] = 'no-store'
        return response


class SafeErrorFilter(logging.Filter):
    def filter(self, record):
        request = getattr(record, 'request', None)
        if request is not None and hasattr(request, 'method'):
            route = getattr(getattr(request, 'resolver_match', None), 'view_name', None) or 'unmatched'
            method = request.method if request.method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS') else 'OTHER'
            record.msg = f'Reference={reference(request)} status={getattr(record, "status_code", "unknown")} method={method} route={route}'
        else:
            record.msg = 'Application diagnostic; logger=' + record.name
        record.args = ()
        return True


class SafeErrorFormatter(logging.Formatter):
    def formatException(self, exc_info):
        # Keep failure locations, never exception arguments, source literals or locals.
        locations = ''.join(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n'
                            for frame in traceback.extract_tb(exc_info[2]))
        return locations + exc_info[0].__name__

    def format(self, record):
        previous = record.exc_text
        record.exc_text = None
        try:
            return super().format(record)
        finally:
            record.exc_text = previous


def error_response(request, status, message=None):
    titles = {400: 'Request could not be processed', 403: 'This action is not available',
              404: 'Page or record not found', 500: 'BillTrack ran into a problem'}
    messages = {
        400: 'Return to BillTrack and try again. Contact the administrator if this continues.',
        403: 'You may not have permission for this action. Return to BillTrack or contact the administrator.',
        404: 'Return to BillTrack and refresh the records. The page or record may have moved or been removed.',
        500: 'If you were saving changes, check the records before trying again. Contact the administrator with the reference below.',
    }
    context = {'title': titles[status], 'message': message or messages[status], 'reference': reference(request)}
    if request.path.startswith('/api/'):
        response = JsonResponse({'detail': context['message'], 'reference': context['reference']}, status=status)
    else:
        response = render(request, 'errors/error.html', context, status=status)
    response['X-Request-ID'] = context['reference']
    response['Cache-Control'] = 'no-store'
    return response


def bad_request(request, exception):
    return error_response(request, 400)


def permission_denied(request, exception):
    return error_response(request, 403)


def page_not_found(request, exception):
    return error_response(request, 404)


def server_error(request):
    return error_response(request, 500)


def csrf_failure(request, reason=''):
    return error_response(request, 403, 'This form could not pass its security check. Return to BillTrack, refresh the form and try again.')
