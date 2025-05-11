import requests
from datetime import datetime, timedelta
from django.utils import timezone


BASE_URL = 'https://192.168.1.1'
COOKIE_EXPIRY_MINUTES = 20

class UdmHandler:
    def __init__(self, detail):
        self.detail = detail

    def _get_login_cookie(self):
        login_at = self.detail.login_at
        if not timezone.is_aware(login_at):
            login_at = timezone.make_aware(login_at)
        if (
                not self.detail.session_cookie or
                not self.detail.login_at or
                (timezone.now() - login_at) > timedelta(minutes=COOKIE_EXPIRY_MINUTES)
        ):
            url = f'{BASE_URL}/api/auth/login'
            payload = {
                'username': self.detail.udm_username,
                'password': self.detail.udm_password,
            }

            try:
                response = requests.post(url, json=payload, verify=False)
                response.raise_for_status()
                cookie = response.cookies.get_dict()
                session_cookie = '; '.join([f'{k}={v}' for k, v in cookie.items()])
                self.detail.session_cookie = session_cookie
                self.detail.login_at = datetime.now()
                self.detail.xsrf_cookie = response.headers.get('x-updated-csrf-token')
                self.detail.save()
                print(response.json())
                print(response.headers)
                return session_cookie
            except requests.RequestException as e:
                raise Exception(f"Login failed: {e}")
        return self.detail.session_cookie

    def _udm_request(self, path, method='GET', payload=None):
        cookie = self._get_login_cookie()
        headers = {
            'Content-Type': 'application/json',
            'Cookie': cookie,
        }
        url = f'{BASE_URL}{path}'

        try:
            if method != 'GET':
                headers['X-CSRF-Token'] = self.detail.xsrf_cookie
            if method == 'GET':
                response = requests.get(url, headers=headers, verify=False)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=payload, verify=False)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=payload, verify=False)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, json=payload, verify=False)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"UDM API request failed: {e}")

    def get_firewall_rules(self):
        return self._udm_request('/proxy/network/v2/api/site/default/firewall-policies')

    def toggle_firewall_rule(self, rule_id, enabled):
        self.get_firewall_rules()
        payload = [{
            '_id': rule_id,
            'enabled': enabled,
        }]

        return self._udm_request('/proxy/network/v2/api/site/default/firewall-policies/batch', 'PUT', payload)
