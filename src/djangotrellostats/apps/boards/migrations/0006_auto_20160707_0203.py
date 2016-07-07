# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-07-07 00:03
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('boards', '0005_memberreport'),
    ]

    operations = [
        migrations.RenameField(
            model_name='memberreport',
            old_name='card_avg_estimated_time',
            new_name='avg_card_estimated_time',
        ),
        migrations.RenameField(
            model_name='memberreport',
            old_name='card_avg_spent_time',
            new_name='avg_card_spent_time',
        ),
        migrations.AddField(
            model_name='memberreport',
            name='avg_card_time',
            field=models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Average time a card lives in the board'),
        ),
        migrations.AddField(
            model_name='memberreport',
            name='std_dev_card_spent_time',
            field=models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Std. Deviation card spent time'),
        ),
        migrations.AddField(
            model_name='memberreport',
            name='std_dev_card_time',
            field=models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Std. Dev. time a card lives in the board'),
        ),
        migrations.AddField(
            model_name='memberreport',
            name='std_dev_estimated_time',
            field=models.DecimalField(decimal_places=4, default=None, max_digits=12, null=True, verbose_name='Std. Deviation of the estimated card completion time'),
        ),
    ]