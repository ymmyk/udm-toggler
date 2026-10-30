"""
URL configuration for udmtoggler project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponseForbidden
from oauth2_provider import urls as oauth2_urls

from toggler.mcp import mcp_endpoint


# Only the pieces of django-oauth-toolkit an MCP client needs; the
# application-management pages stay in the Django admin.
OAUTH2_ENDPOINTS = {'authorize', 'token', 'revoke-token', 'dcr-register'}
oauth2_patterns = oauth2_urls.metadata_urlpatterns + [
    path('o/', include([
        p for p in oauth2_urls.base_urlpatterns + oauth2_urls.dcr_urlpatterns
        if p.name in OAUTH2_ENDPOINTS
    ] + [
        # Registration responses link here, but self-registered clients may
        # not edit themselves (e.g. to add the client_credentials grant).
        path('register/<str:client_id>/', lambda request, client_id: HttpResponseForbidden(),
             name='dcr-register-management'),
    ])),
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include((oauth2_patterns, 'oauth2_provider'))),
    path('mcp', mcp_endpoint, name='mcp'),
     path('', include('toggler.urls')),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
