# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2017-02-07 00:08
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('boards', '0046_auto_20170207_0108'),
        ('members', '0009_member_max_number_of_boards'),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberRole',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(default='normal', max_length=32, verbose_name='Role a member has in a board')),
                ('board', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roles', to='boards.Board', verbose_name='Boards')),
                ('members', models.ManyToManyField(related_name='roles', to='members.Member', verbose_name='Member')),
            ],
        ),
    ]