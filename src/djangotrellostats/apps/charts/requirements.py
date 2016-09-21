# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import copy
from datetime import timedelta

import pygal
from django.db.models import Sum


# Burndown chart for each requirement
def burndown(board, requirement=None):
    if requirement is not None:
        return _requirement_burndown(requirement)
    return _burndown_by_requirement(board)


# Burndown for a particular requirement
def _requirement_burndown(requirement):
    board = requirement.board

    chart_title = u"Burndown of requirement {0}".format(requirement.code)
    chart_title += u" for board {0} as of {1}".format(board.name, board.get_human_fetch_datetime())

    burndown_chart = pygal.Line(title=chart_title, legend_at_bottom=True, print_values=True,
                                print_zeroes=False, fill=False, human_readable=True, x_label_rotation=45)

    # Estimated number of hours
    estimated_number_of_hours = requirement.estimated_number_of_hours

    # Remaining hours
    remaining_time = estimated_number_of_hours
    daily_spent_times = board.daily_spent_times.filter(
        card__requirements=requirement, spent_time__gt=0
    ).order_by("date")

    # Start working date in this board
    start_working_date = board.get_working_start_date()
    if start_working_date is None:
        return burndown_chart.render_django_response()

    # End working date in this board
    end_working_date = board.get_working_end_date()
    if end_working_date is None:
        return burndown_chart.render_django_response()

    # Remaining time values
    remaining_time_values = [remaining_time]

    # Dates where there is some work in this requirement
    x_labels = ["Start"]

    date_i = copy.deepcopy(start_working_date)
    remaining_time_i = copy.deepcopy(remaining_time)
    while date_i <= end_working_date:
        spent_time = daily_spent_times.filter(date=date_i).aggregate(
            spent_time_sum=Sum("spent_time")
        )["spent_time_sum"]
        if spent_time is not None and spent_time > 0:
            remaining_time_i -= spent_time
            remaining_time_values.append(remaining_time_i)
            x_labels.append(date_i.strftime("%Y-%m-%d"))
        date_i += timedelta(days=1)

    burndown_chart.add(u"Initial estimation for {0}".format(requirement.code), [remaining_time for i in range(0, len(x_labels))])
    burndown_chart.x_labels = x_labels
    burndown_chart.add(u"Burndown of {0}".format(requirement.code), remaining_time_values)

    return burndown_chart.render_django_response()


# Burndown for all requirements
def _burndown_by_requirement(board):

    chart_title = u"Burndown for board {0}".format(board.name)
    chart_title += u" as of {1}".format(board.name, board.get_human_fetch_datetime())

    burndown_chart = pygal.Line(title=chart_title, legend_at_bottom=True, print_values=True,
                                print_zeroes=False, fill=False, human_readable=True, x_label_rotation=45)

    # Estimated number of hours
    estimated_number_of_hours = board.requirements.aggregate(estimated_number_of_hours=Sum("estimated_number_of_hours"))["estimated_number_of_hours"]

    # Remaining hours
    remaining_time = estimated_number_of_hours
    daily_spent_times = board.daily_spent_times.filter(
        card__requirements__board=board, spent_time__gt=0
    ).distinct().order_by("date")

    # Start working date in this board
    start_working_date = board.get_working_start_date()
    if start_working_date is None:
        return burndown_chart.render_django_response()

    # End working date in this board
    end_working_date = board.get_working_end_date()
    if end_working_date is None:
        return burndown_chart.render_django_response()

    # Remaining time values
    remaining_time_values = [remaining_time]

    # Dates where there is some work in this requirement
    x_labels = ["Start"]

    date_i = copy.deepcopy(start_working_date)
    remaining_time_i = copy.deepcopy(remaining_time)
    while date_i <= end_working_date:
        spent_time = daily_spent_times.filter(date=date_i).aggregate(
            spent_time_sum=Sum("spent_time")
        )["spent_time_sum"]
        if spent_time is not None and spent_time > 0:
            remaining_time_i -= spent_time
            remaining_time_values.append(remaining_time_i)
            x_labels.append(date_i.strftime("%Y-%m-%d"))
        date_i += timedelta(days=1)

    burndown_chart.add(u"{0} requirements estimation".format(board.name), [remaining_time for i in range(0, len(x_labels))])
    burndown_chart.x_labels = x_labels
    burndown_chart.add(u"Burndown according to {0} requirements".format(board.name), remaining_time_values)

    return burndown_chart.render_django_response()
