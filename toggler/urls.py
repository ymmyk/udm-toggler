from django.urls import path
from django.conf import settings

from django.conf.urls.static import static

from .views import (
    configure,
    custom_login_view,
    custom_logout_view,
    home,
    schedule_edit,
    schedule_list,
)

urlpatterns = [
    path('login/', custom_login_view, name='toggler-login'),
    path('logout/', custom_logout_view, name='toggler-logout'),
    path('', home, name='toggler-home'),
    path('configure/', configure, name='toggler-configure'),
    path('schedules/', schedule_list, name='toggler-schedule-list'),
    path('schedules/new/', schedule_edit, name='toggler-schedule-new'),
    path('schedules/<int:sched_id>/edit/', schedule_edit, name='toggler-schedule-edit'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
