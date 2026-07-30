from django.db import models
from django.contrib.auth.models import User

class UserDetail(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    udm_username = models.CharField(max_length=150)
    udm_password = models.CharField(max_length=150)
    session_cookie = models.TextField(blank=True, null=True)
    xsrf_cookie = models.TextField(blank=True, null=True)
    login_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.udm_username}"

    @classmethod
    def fetch(cls, user):
        detail, _ = cls.objects.get_or_create(user=user)
        return detail


class FirewallRule(models.Model):
    id = models.AutoField(primary_key=True)
    udm_id = models.CharField(max_length=64)
    favorite = models.BooleanField(default=False)
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    raw = models.JSONField()

    def __str__(self):
        return self.name


class Schedule(models.Model):
    ACTION_ON = 'on'
    ACTION_OFF = 'off'
    ACTION_CHOICES = [
        (ACTION_ON, 'On'),
        (ACTION_OFF, 'Off'),
    ]

    name = models.CharField(max_length=100)
    action = models.CharField(max_length=3, choices=ACTION_CHOICES)
    rules = models.ManyToManyField(FirewallRule, related_name='schedules', blank=True)
    days_of_week = models.JSONField(default=list)
    time = models.TimeField()
    is_enabled = models.BooleanField(default=True)
    last_ran = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name
