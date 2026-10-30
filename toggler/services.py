from datetime import timedelta

from django.utils import timezone

from .models import FirewallRule
from .tasks import WINDOW_MINUTES


def sync_rules(handler):
    """Mirror the UDM's (non-predefined) firewall rules into FirewallRule rows."""
    rules = handler.get_firewall_rules()
    ids = set()
    for rule in rules:
        if rule.get('predefined'):
            continue

        fw, _ = FirewallRule.objects.get_or_create(udm_id=rule.get('_id'), defaults=dict(
            name=rule.get('name'),
            raw=rule,
        ))
        ids.add(fw.id)
        if fw.enabled != rule.get('enabled'):
            fw.enabled = rule.get('enabled')
            fw.save(update_fields=['enabled'])
        if fw.name != rule.get('name'):
            fw.name = rule.get('name')
            fw.save(update_fields=['name'])
    FirewallRule.objects.exclude(pk__in=ids).delete()


def set_rule_enabled(handler, rule, enabled):
    """Push a rule's state to the UDM and store what the UDM reports back."""
    res = handler.toggle_firewall_rule(rule.udm_id, enabled)
    rule.enabled = res[0].get('enabled')
    rule.save(update_fields=['enabled'])
    return rule


def set_schedule_enabled(schedule, enabled):
    schedule.is_enabled = enabled
    if enabled:
        # Don't fire a slot that passed while the schedule was off.
        schedule.last_ran = timezone.now() - timedelta(minutes=WINDOW_MINUTES)
    schedule.save(update_fields=['is_enabled', 'last_ran'])
    return schedule
