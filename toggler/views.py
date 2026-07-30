from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from rich import print

from .handler import UdmHandler
from .models import FirewallRule, Schedule, UserDetail
from .tasks import WINDOW_MINUTES


DAYS = [
    (0, 'Mon'),
    (1, 'Tue'),
    (2, 'Wed'),
    (3, 'Thu'),
    (4, 'Fri'),
    (5, 'Sat'),
    (6, 'Sun'),
]


def custom_login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('/')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def custom_logout_view(request):
    logout(request)
    return redirect('/login/')


def _refresh_udm(request, handler):
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
    messages.success(request, 'Firewall rules updated')


@login_required(login_url='/login/')
def home(request):
    detail = UserDetail.fetch(request.user)
    handler = UdmHandler(detail)
    if request.GET.get('refresh') == 'true':
        try:
            _refresh_udm(request, handler)
        except Exception as e:
            messages.error(request, str(e))
        return redirect(request.path)

    all_rules = FirewallRule.objects.filter(favorite=True).all().order_by('name')
    block_all = request.GET.get('all')
    if block_all:
        block_all = block_all == 'true'
        for rule in all_rules:
            res = handler.toggle_firewall_rule(rule.udm_id, block_all)
            rule.enabled = res[0].get('enabled')
            rule.save(update_fields=['enabled'])

    if rule_id := request.GET.get('toggle'):
        try:
            rule = FirewallRule.objects.get(id=rule_id)
            rule.enabled = not rule.enabled
            res = handler.toggle_firewall_rule(rule.udm_id, rule.enabled)
            rule.enabled = res[0].get('enabled')
            rule.save(update_fields=['enabled'])
        except Exception as e:
            messages.error(request, str(e))
        return redirect(request.path)


    return render(request, 'home.html', {'rules': all_rules})


@login_required(login_url='/login/')
def configure(request):
    detail = UserDetail.fetch(request.user)
    handler = UdmHandler(detail)
    if request.GET.get('refresh') == 'true':
        try:
            _refresh_udm(request, handler)
        except Exception as e:
            messages.error(request, str(e))
        return redirect(request.path)

    if rule_id := request.GET.get('toggle'):
        try:
            rule = FirewallRule.objects.get(id=rule_id)
            rule.favorite = not rule.favorite
            rule.save()
            messages.success(request, 'Firewall rules updated')
        except FirewallRule.DoesNotExist:
            messages.error(request, 'Firewall rule not found')
        return redirect(request.path)

    all_rules = FirewallRule.objects.all().order_by('name')
    return render(request, 'configure.html', {'rules': all_rules})


class ScheduleForm(forms.ModelForm):
    days_of_week = forms.MultipleChoiceField(
        choices=DAYS,
        widget=forms.CheckboxSelectMultiple,
    )
    time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    rules = forms.ModelMultipleChoiceField(
        queryset=FirewallRule.objects.filter(favorite=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Schedule
        fields = ['name', 'action', 'rules', 'days_of_week', 'time', 'is_enabled']

    def clean_days_of_week(self):
        return [int(d) for d in self.cleaned_data['days_of_week']]


@login_required(login_url='/login/')
def schedule_list(request):
    if sched_id := request.GET.get('toggle'):
        schedule = get_object_or_404(Schedule, id=sched_id)
        schedule.is_enabled = not schedule.is_enabled
        if schedule.is_enabled:
            schedule.last_ran = timezone.now() - timedelta(minutes=WINDOW_MINUTES)
        schedule.save(update_fields=['is_enabled', 'last_ran'])
        return redirect(request.path)

    if sched_id := request.GET.get('delete'):
        Schedule.objects.filter(id=sched_id).delete()
        messages.success(request, 'Schedule deleted')
        return redirect(request.path)

    schedules = Schedule.objects.all().order_by('name')
    return render(request, 'schedule_list.html', {
        'schedules': schedules,
        'days': DAYS,
    })


@login_required(login_url='/login/')
def schedule_edit(request, sched_id=None):
    instance = get_object_or_404(Schedule, id=sched_id) if sched_id else None

    if request.method == 'POST':
        form = ScheduleForm(request.POST, instance=instance)
        if form.is_valid():
            schedule = form.save(commit=False)
            if instance is None and schedule.is_enabled:
                schedule.last_ran = timezone.now() - timedelta(minutes=WINDOW_MINUTES)
            schedule.save()
            form.save_m2m()
            messages.success(request, 'Schedule saved')
            return redirect(reverse('toggler-schedule-list'))
    else:
        form = ScheduleForm(instance=instance)

    return render(request, 'schedule_form.html', {
        'form': form,
        'schedule': instance,
    })
