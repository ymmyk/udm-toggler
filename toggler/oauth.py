"""Keep open client registration from becoming a way around user consent.

Registration has to be open because MCP clients sign themselves up, but a
self-registered client must only ever get tokens through the authorization
code flow, where a logged-in user approves it. Otherwise anyone could
register a client_credentials app and mint a token with no human involved.
Apps that need other grants (e.g. a headless bot) are created in the admin.
"""
import json

from oauth2_provider.models import Application
from oauth2_provider.oauth2_validators import OAuth2Validator


SELF_REGISTERED_GRANTS = {'authorization_code', 'refresh_token'}


class AuthorizationCodeOnlyDCRPermission:
    """Allow anyone to register, but only for the authorization code flow."""

    def has_permission(self, request):
        try:
            data = json.loads(request.body)
        except ValueError:
            return True  # let the view report the malformed body
        if not isinstance(data, dict):
            return True
        grant_types = data.get('grant_types', ['authorization_code'])
        return isinstance(grant_types, list) and set(grant_types) <= SELF_REGISTERED_GRANTS


class Validator(OAuth2Validator):
    def validate_grant_type(self, client_id, grant_type, client, request, *args, **kwargs):
        # Backstop for the permission above, whatever path created the app.
        if (
                request.client.registration_source != Application.RegistrationSource.MANUAL
                and grant_type not in SELF_REGISTERED_GRANTS
        ):
            return False
        return super().validate_grant_type(client_id, grant_type, client, request, *args, **kwargs)
