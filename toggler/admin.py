from django.contrib import admin
from .models import UserDetail

@admin.register(UserDetail)
class UserDetailAdmin(admin.ModelAdmin):
    list_display = ('user', 'udm_username', 'login_at')
    search_fields = ('user__username', 'udm_username')
    readonly_fields = ('login_at',)

    # Optional: Use raw_id_fields to make user selection more manageable in large DBs
    raw_id_fields = ('user',)
