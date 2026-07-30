from django.db import migrations


PERIODIC_TASK_NAME = 'Run due schedules (every minute)'
TASK_PATH = 'toggler.tasks.run_due_schedules'


def create_periodic_task(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    PeriodicTask.objects.filter(task__in=[
        'toggler.tasks.enable_scheduled_rules',
        'toggler.tasks.disabled_schedule_rules',
    ]).delete()

    interval, _ = IntervalSchedule.objects.get_or_create(
        every=1,
        period='minutes',
    )
    PeriodicTask.objects.update_or_create(
        name=PERIODIC_TASK_NAME,
        defaults={
            'interval': interval,
            'task': TASK_PATH,
            'enabled': True,
        },
    )


def remove_periodic_task(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=PERIODIC_TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('toggler', '0006_schedule'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(create_periodic_task, remove_periodic_task),
    ]
