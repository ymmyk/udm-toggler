from datetime import timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

from toggler.handler import UdmHandler
from toggler.models import Schedule, UserDetail


SCHEDULE_TZ = ZoneInfo('America/Chicago')
WINDOW_MINUTES = 10


def _most_recent_slot(schedule, now_utc):
    """Most recent scheduled datetime <= now_utc that falls within the window.

    Returns a UTC datetime or None if no slot exists in the window.
    """
    now_local = now_utc.astimezone(SCHEDULE_TZ)
    candidate = now_local.replace(
        hour=schedule.time.hour,
        minute=schedule.time.minute,
        second=0,
        microsecond=0,
    )
    if candidate > now_local:
        candidate -= timedelta(days=1)

    if candidate.weekday() not in schedule.days_of_week:
        return None

    candidate_utc = candidate.astimezone(now_utc.tzinfo)
    if now_utc - candidate_utc > timedelta(minutes=WINDOW_MINUTES):
        return None
    return candidate_utc


@shared_task
def run_due_schedules():
    detail = UserDetail.objects.first()
    if detail is None:
        return
    handler = UdmHandler(detail)
    now_utc = timezone.now()

    for schedule in Schedule.objects.filter(is_enabled=True).prefetch_related('rules'):
        slot = _most_recent_slot(schedule, now_utc)
        if slot is None:
            continue
        if schedule.last_ran and schedule.last_ran >= slot:
            continue

        target_state = schedule.action == Schedule.ACTION_ON
        for rule in schedule.rules.all():
            res = handler.toggle_firewall_rule(rule.udm_id, target_state)
            rule.enabled = res[0].get('enabled')
            rule.save(update_fields=['enabled'])

        schedule.last_ran = slot
        schedule.save(update_fields=['last_ran'])
