import io
import logging
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.test import Client, TestCase, override_settings
from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


def broken(request):
    raise RuntimeError('password=private-value token=private-token')


def forbidden(request):
    raise PermissionDenied('private-permission-reason')


def posted(request):
    return JsonResponse({'ok': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def validation(request):
    return Response({'amount': ['Enter a positive amount.']}, status=400)


urlpatterns=[path('api/broken/',broken,name='broken'),path('broken/',broken,name='broken-page'),
    path('api/forbidden/',forbidden,name='forbidden'),path('forbidden/',forbidden),
    path('api/posted/',posted),path('api/validation/',validation)]


@override_settings(DEBUG=False, ROOT_URLCONF=__name__)
class UserVisibleErrorTests(TestCase):
    def setUp(self):
        self.client=Client(raise_request_exception=False)

    def test_server_errors_are_safe_json_or_readable_html_with_matching_references(self):
        for url in ('/api/broken/','/broken/'):
            response=self.client.get(url)
            self.assertEqual(response.status_code,500)
            reference=response['X-Request-ID']
            self.assertRegex(reference,r'^[a-f0-9]{32}$')
            self.assertContains(response,reference,status_code=500)
            self.assertNotContains(response,'private-value',status_code=500)
            self.assertNotContains(response,'Traceback',status_code=500)
            if url.startswith('/api/'):
                self.assertEqual(response.json()['reference'],reference)
            else:
                self.assertContains(response,'Back to BillTrack',status_code=500)

    def test_forbidden_not_found_and_csrf_errors_remain_readable(self):
        for url,status in (('/api/missing/',404),('/missing/',404),('/api/forbidden/',403),('/forbidden/',403)):
            response=self.client.get(url)
            self.assertEqual(response.status_code,status)
            self.assertContains(response,response['X-Request-ID'],status_code=status)
            self.assertNotContains(response,'private-permission-reason',status_code=status)
        response=Client(enforce_csrf_checks=True).post('/api/posted/',{})
        self.assertEqual(response.status_code,403)
        self.assertIn('reference',response.json())

    def test_validation_shape_is_preserved_and_client_reference_is_not_trusted(self):
        response=self.client.get('/api/validation/',HTTP_X_REQUEST_ID='user-supplied-token')
        self.assertEqual(response.json(),{'amount':['Enter a positive amount.']})
        self.assertNotEqual(response['X-Request-ID'],'user-supplied-token')

    def test_safe_log_format_keeps_reference_and_location_without_secret_arguments(self):
        from ..error_handling import SafeErrorFilter, SafeErrorFormatter
        response=self.client.get('/broken/')
        request=response.wsgi_request
        try:
            broken(request)
        except RuntimeError:
            import sys
            record=logging.LogRecord('django.request',logging.ERROR,__file__,1,'private-token',(),sys.exc_info())
        record.request=request
        record.status_code=500
        SafeErrorFilter().filter(record)
        rendered=SafeErrorFormatter('%(levelname)s %(message)s').format(record)
        self.assertIn(response['X-Request-ID'],rendered)
        self.assertIn('RuntimeError',rendered)
        self.assertNotIn('private-value',rendered)
        self.assertNotIn('private-token',rendered)

    def test_development_server_socket_logs_do_not_require_an_http_request(self):
        from ..error_handling import SafeErrorFilter
        record=logging.LogRecord('django.server',logging.WARNING,__file__,1,'private-path',(),None)
        record.request=object()
        self.assertTrue(SafeErrorFilter().filter(record))
        self.assertNotIn('private-path',record.getMessage())

from estate_project.urls import handler400, handler403, handler404, handler500
