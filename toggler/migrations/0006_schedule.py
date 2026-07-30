from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('toggler', '0005_firewallrule_schedule_enabled'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='firewallrule',
            name='schedule_enabled',
        ),
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('action', models.CharField(choices=[('on', 'On'), ('off', 'Off')], max_length=3)),
                ('days_of_week', models.JSONField(default=list)),
                ('time', models.TimeField()),
                ('is_enabled', models.BooleanField(default=True)),
                ('last_ran', models.DateTimeField(blank=True, null=True)),
                ('rules', models.ManyToManyField(blank=True, related_name='schedules', to='toggler.firewallrule')),
            ],
        ),
    ]
