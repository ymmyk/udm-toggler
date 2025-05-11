from django.urls import path
from django.conf import settings

from django.conf.urls.static import static

from .views import custom_login_view, home, custom_logout_view, configure

urlpatterns = [
    path('login/', custom_login_view, name='toggler-login'),
    path('logout/', custom_logout_view, name='toggler-logout'),
    path('', home, name='toggler-home'),
    path('configure/', configure, name='toggler-configure'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
