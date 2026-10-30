import base64
import hashlib
import json
import secrets
from datetime import time
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import User
from django.test import TestCase

from .models import FirewallRule, Schedule, UserDetail


REDIRECT_URI = 'http://localhost:33418/callback'


class McpOAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('parent', password='pw')
        UserDetail.objects.create(user=self.user, udm_username='udm', udm_password='udm')
        self.rule = FirewallRule.objects.create(
            udm_id='abc', name='Kid tablet', favorite=True, enabled=False, raw={})
        FirewallRule.objects.create(udm_id='def', name='Printer', enabled=False, raw={})

    def _token(self):
        """Run the flow an MCP client does: register, authorize, exchange code."""
        res = self.client.post('/o/register/', json.dumps({
            'client_name': 'Test bot',
            'redirect_uris': [REDIRECT_URI],
            'grant_types': ['authorization_code', 'refresh_token'],
            'response_types': ['code'],
            'token_endpoint_auth_method': 'none',
        }), content_type='application/json')
        self.assertEqual(res.status_code, 201, res.content)
        client_id = res.json()['client_id']

        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        params = {
            'response_type': 'code',
            'client_id': client_id,
            'redirect_uri': REDIRECT_URI,
            'scope': 'mcp',
            'state': 'xyz',
            'code_challenge': challenge,
            'code_challenge_method': 'S256',
        }

        res = self.client.get('/o/authorize/', params)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res['Location'].startswith('/login/?next='))

        self.client.login(username='parent', password='pw')
        res = self.client.get('/o/authorize/', params)
        self.assertContains(res, 'Allow Test bot?')
        res = self.client.post('/o/authorize/', {**params, 'allow': 'Allow'})
        self.assertEqual(res.status_code, 302)
        code = parse_qs(urlparse(res['Location']).query)['code'][0]
        self.client.logout()

        res = self.client.post('/o/token/', {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': client_id,
            'code_verifier': verifier,
        })
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()['access_token']

    def _rpc(self, token, method, params=None, msg_id=1):
        body = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
        if params is not None:
            body['params'] = params
        return self.client.post('/mcp', json.dumps(body), content_type='application/json',
                                HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_unauthenticated_request_points_at_resource_metadata(self):
        res = self.client.post('/mcp', '{}', content_type='application/json')
        self.assertEqual(res.status_code, 401)
        self.assertIn('/.well-known/oauth-protected-resource/mcp', res['WWW-Authenticate'])

        meta = self.client.get('/.well-known/oauth-protected-resource/mcp').json()
        self.assertEqual(meta['resource'], 'http://testserver/mcp')
        self.assertEqual(meta['authorization_servers'], ['http://testserver'])

        meta = self.client.get('/.well-known/oauth-authorization-server').json()
        self.assertEqual(meta['authorization_endpoint'], 'http://testserver/o/authorize/')
        self.assertEqual(meta['registration_endpoint'], 'http://testserver/o/register/')
        self.assertIn('S256', meta['code_challenge_methods_supported'])

    def test_bad_token_rejected(self):
        res = self._rpc('nope', 'tools/list')
        self.assertEqual(res.status_code, 401)

    def test_initialize_and_list_tools(self):
        token = self._token()
        res = self._rpc(token, 'initialize', {
            'protocolVersion': '2025-06-18', 'capabilities': {},
            'clientInfo': {'name': 't', 'version': '1'},
        })
        self.assertEqual(res.json()['result']['protocolVersion'], '2025-06-18')

        res = self.client.post('/mcp', json.dumps({
            'jsonrpc': '2.0', 'method': 'notifications/initialized',
        }), content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(res.status_code, 202)

        names = {t['name'] for t in self._rpc(token, 'tools/list').json()['result']['tools']}
        self.assertIn('set_rule', names)

    def test_list_rules_defaults_to_favorites(self):
        token = self._token()
        result = self._rpc(token, 'tools/call', {'name': 'list_rules'}).json()['result']
        self.assertEqual([r['name'] for r in result['structuredContent']['rules']], ['Kid tablet'])

    @mock.patch('toggler.mcp.UdmHandler')
    def test_set_rule(self, handler_cls):
        handler_cls.return_value.toggle_firewall_rule.return_value = [{'enabled': True}]
        token = self._token()
        result = self._rpc(token, 'tools/call', {
            'name': 'set_rule', 'arguments': {'rule_id': self.rule.id, 'enabled': True},
        }).json()['result']
        self.assertFalse(result['isError'])
        handler_cls.return_value.toggle_firewall_rule.assert_called_once_with('abc', True)
        self.rule.refresh_from_db()
        self.assertTrue(self.rule.enabled)

    def test_set_rule_unknown_id_is_tool_error(self):
        token = self._token()
        result = self._rpc(token, 'tools/call', {
            'name': 'set_rule', 'arguments': {'rule_id': 999, 'enabled': True},
        }).json()['result']
        self.assertTrue(result['isError'])

    def test_set_schedule(self):
        schedule = Schedule.objects.create(
            name='Bedtime', action=Schedule.ACTION_OFF, days_of_week=[0], time=time(21), is_enabled=False)
        token = self._token()
        result = self._rpc(token, 'tools/call', {
            'name': 'set_schedule', 'arguments': {'schedule_id': schedule.id, 'enabled': True},
        }).json()['result']
        self.assertTrue(result['structuredContent']['schedule']['enabled'])
        schedule.refresh_from_db()
        self.assertIsNotNone(schedule.last_ran)

    def test_client_credentials_token_for_headless_bot(self):
        from oauth2_provider.models import Application
        app = Application(
            name='Bot', client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS, user=self.user)
        secret = app.client_secret
        app.save()
        res = self.client.post('/o/token/', {
            'grant_type': 'client_credentials', 'client_id': app.client_id,
            'client_secret': secret, 'scope': 'mcp',
        })
        self.assertEqual(res.status_code, 200, res.content)
        res = self._rpc(res.json()['access_token'], 'tools/call', {'name': 'list_rules'})
        self.assertEqual(res.status_code, 200)

    def test_self_registration_cannot_skip_consent(self):
        for grant in ['client_credentials', 'password', 'implicit',
                      'urn:ietf:params:oauth:grant-type:device_code']:
            res = self.client.post('/o/register/', json.dumps({
                'client_name': 'Evil', 'grant_types': [grant],
                'token_endpoint_auth_method': 'client_secret_post',
            }), content_type='application/json')
            self.assertNotEqual(res.status_code, 201, grant)

    def test_self_registered_app_cannot_use_client_credentials(self):
        # Backstop in case an app slips past the registration check.
        from oauth2_provider.models import Application
        app = Application(
            name='Evil', client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            registration_source=Application.RegistrationSource.DCR)
        secret = app.client_secret
        app.save()
        res = self.client.post('/o/token/', {
            'grant_type': 'client_credentials', 'client_id': app.client_id,
            'client_secret': secret, 'scope': 'mcp',
        })
        self.assertEqual(res.status_code, 400)

    def test_unknown_method(self):
        token = self._token()
        self.assertEqual(self._rpc(token, 'bogus').json()['error']['code'], -32601)


class LoginRedirectTests(TestCase):
    def setUp(self):
        User.objects.create_user('parent', password='pw')

    def test_login_follows_local_next(self):
        res = self.client.post('/login/', {'username': 'parent', 'password': 'pw', 'next': '/o/authorize/?a=1'})
        self.assertEqual(res['Location'], '/o/authorize/?a=1')

    def test_login_ignores_offsite_next(self):
        res = self.client.post('/login/', {'username': 'parent', 'password': 'pw', 'next': 'https://evil.example/'})
        self.assertEqual(res['Location'], '/')
