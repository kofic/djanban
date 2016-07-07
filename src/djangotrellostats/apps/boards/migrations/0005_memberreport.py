# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-06 23:33
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0002_auto_20160707_0034'),
        ('boards', '0004_auto_20160707_0034'),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('forward_movements', models.PositiveIntegerField(verbose_name='Forward movements')),
                ('backward_movements', models.PositiveIntegerField(verbose_name='Backward movements')),
                ('card_avg_spent_time', models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Average card spent time')),
                ('card_avg_estimated_time', models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Average task estimated card completion time')),
                ('board', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_reports', to='boards.Board', verbose_name='Board')),
                ('fetch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_reports', to='boards.Fetch', verbose_name='Fetch')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='member_reports', to='members.Member', verbose_name='Member')),
            ],
        ),
    ]
