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
    def shared(cls):
        """The configured UDM credentials, or None if nothing is set up yet.

        The UDM login belongs to the app rather than to each Django user, so
        every user shares one record instead of needing their own copy.
        """
        return cls.objects.exclude(udm_username='').order_by('pk').first()

    @classmethod
    def fetch(cls, user):
        detail = cls.shared()
        if detail is None:
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
        (ACTION_ON, 'Internet On'),
        (ACTION_OFF, 'Internet Off'),
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

    @property
    def target_rule_enabled(self):
        # "Internet Off" means the firewall (block) rule should be enabled.
        return self.action == self.ACTION_OFF
