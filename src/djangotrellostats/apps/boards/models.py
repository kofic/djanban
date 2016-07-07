from __future__ import unicode_literals

import re

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Avg
from django.db.models.query_utils import Q
from django.utils import timezone
import copy
import numpy
import math

from trello import Board as TrelloBoard
from collections import namedtuple


# Abstract model that represents the immutable objects
class ImmutableModel(models.Model):

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.id is not None:
            raise ValueError(u"This model does not allow edition")
        super(ImmutableModel, self).save(*args, **kwargs)


# Each fetch of data is independent of the others
class Fetch(ImmutableModel):
    board = models.ForeignKey("boards.Board", verbose_name=u"Board", related_name="fetches")
    creation_datetime = models.DateTimeField(verbose_name=u"Date this object was created")

    def save(self, *args, **kwargs):
        self.creation_datetime = timezone.now()
        super(ImmutableModel, self).save(*args, **kwargs)

    @staticmethod
    def new(board):
        fetch = Fetch(board=board)
        fetch.save()
        return fetch


# Task board
class Board(models.Model):
    creator = models.ForeignKey("members.Member", verbose_name=u"Member", related_name="created_boards")
    name = models.CharField(max_length=128, verbose_name=u"Name of the board")
    uuid = models.CharField(max_length=128, verbose_name=u"Trello id of the board", unique=True)
    last_activity_date = models.DateTimeField(verbose_name=u"Last activity date", default=None, null=True)

    members = models.ManyToManyField("members.Member", verbose_name=u"Member", related_name="boards")

    @property
    def last_fetch(self):
        try:
            last_fetch = Fetch.objects.all().order_by("-creation_datetime")[0]
        except IndexError:
            raise Fetch.DoesNotExist
        return last_fetch

    # Fetch data of this board
    def fetch(self):
        fetch = Fetch.new(self)
        self._fetch_labels(fetch)
        self._fetch_cards(fetch)

    # Fetch the labels of this board
    def _fetch_labels(self, fetch):

        trello_board = self._get_trello_board()
        trello_labels = trello_board.get_labels()
        for trello_label in trello_labels:
            label = Label.factory_from_trello_label(trello_label, self)
            label.fetch = fetch
            label.save()

    # Fetch the cards of this board
    def _fetch_cards(self, fetch):
        trello_board = self._get_trello_board()
        trello_cards = trello_board.all_cards()

        # Fake class used for passing a list of trello lists to the method of Card stats_by_list
        ListForStats = namedtuple('ListForStats', 'id django_id')
        trello_lists = [ListForStats(id=list_.uuid, django_id=list_.id) for list_ in self.lists.all()]

        trello_cycle_dict = {list_.uuid: True for list_ in self.lists.filter(Q(type="done") | Q(type="development"))}
        done_list = self.lists.get(type="done")
        trello_list_done = ListForStats(id=done_list.uuid, django_id=done_list.id)

        # Hash to obtain the order of a list given its uuid
        trello_list_order_dict = {list_.uuid: list_.id for list_ in self.lists.all()}

        # Comparator function
        def list_cmp(list_1, list_2):
            list_1_order = trello_list_order_dict[list_1]
            list_2_order = trello_list_order_dict[list_2]
            if list_1_order < list_2_order:
                return 1
            if list_1_order > list_2_order:
                return -1
            return 0

        # List reports
        list_report_dict = {list_.uuid: ListReport(fetch=fetch, list=list_, forward_movements=0, backward_movements=0) for list_ in self.lists.all()}

        # Member report
        member_report_dict = {member.uuid: MemberReport(fetch=fetch, board=self, member=member) for member in self.members.all()}

        # Card creation
        for trello_card in trello_cards:
            trello_card.fetch(eager=False)
            card = Card.factory_from_trello_card(trello_card, self)

            card_stats_by_list = trello_card.get_stats_by_list(lists=trello_lists, list_cmp=list_cmp,
                                                               done_list=trello_list_done,
                                                               time_unit="hours", card_movements_filter=None)

            # Total forward and backward movements of a card
            card_forward_moves = 0
            card_backward_moves = 0
            card_time = 0

            # List reports. For each list compute the number of forward movements and backward movements
            # being it its the source.
            # Thus, compute the time the cards live in this list.
            for list_ in trello_lists:
                list_id = list_.id
                card_stats_of_list = card_stats_by_list[list_id]

                # Time the card lives in each list
                if not hasattr(list_report_dict[list_id], "times"):
                    list_report_dict[list_id].times = []

                # Time a card lives in the list
                list_report_dict[list_id].times.append(card_stats_of_list["time"])

                # Forward and backward movements where the list is the source
                list_report_dict[list_id].forward_movements += card_stats_of_list["forward_moves"]
                list_report_dict[list_id].backward_movements += card_stats_of_list["backward_moves"]

                card_time += card_stats_of_list["time"]

                # Update total forward and backward movements
                card_forward_moves += card_stats_of_list["forward_moves"]
                card_backward_moves += card_stats_of_list["backward_moves"]

            # Cycle and Lead times
            if trello_card.idList == done_list.uuid:
                card.lead_time = sum([list_stats["time"] for list_uuid, list_stats in card_stats_by_list.items()])
                card.cycle_time = sum(
                    [list_stats["time"] if list_uuid in trello_cycle_dict else 0 for list_uuid, list_stats in
                     card_stats_by_list.items()])

            card.fetch = fetch
            card.save()

            # Label assignment to each card
            label_uuids = trello_card.idLabels
            card_labels = self.labels.filter(uuid__in=label_uuids, fetch=fetch)
            for card_label in card_labels:
                card.labels.add(card_label)

            # Member reports
            for trello_member_uuid in trello_card.idMembers:
                num_trello_card_members = len(trello_card.idMembers)
                member_report = member_report_dict[trello_member_uuid]

                # Increment the number of cards of the member report
                member_report.number_of_cards += 1

                # Forward movements of the cards
                if member_report.forward_movements is None:
                    member_report.forward_movements = 0
                member_report.forward_movements += math.ceil(1. * card_forward_moves / 1. * num_trello_card_members)

                # Backward movements of the cards
                if member_report.backward_movements is None:
                    member_report.backward_movements = 0
                member_report.backward_movements += math.ceil(1. * card_backward_moves / 1. * num_trello_card_members)

                # Inform this member report has data and must be saved
                member_report.present = True

                # Card time
                if not hasattr(member_report, "card_times"):
                    member_report.card_times = []
                if card_time is not None:
                    member_report.card_times.append(card_time)

                # Card spent time
                if not hasattr(member_report, "card_spent_times"):
                    member_report.card_spent_times = []
                if card.spent_time is not None:
                    member_report.card_spent_times.append(card.spent_time)

                # Card estimated time
                if not hasattr(member_report, "card_estimated_times"):
                    member_report.card_estimated_times = []
                if card.estimated_time is not None:
                    member_report.card_estimated_times.append(card.estimated_time)

        # Average and std. deviation of time cards live in this list
        for list_uuid, list_report in list_report_dict.items():
            list_report.avg_card_time = numpy.mean(list_report.times)
            list_report.std_dev_card_time = numpy.std(list_report.times, axis=0)
            list_report.save()

        # Average and std. deviation of card times by member
        for member_uuid, member_report in member_report_dict.items():
            if hasattr(member_report, "present") and member_report.present:
                # Average and std deviation of the time of member cards
                if len(member_report.card_times) > 0:
                    member_report.avg_card_time = numpy.mean(member_report.card_times)
                    member_report.std_dev_card_time = numpy.std(member_report.card_times)

                # Average and std deviation of the spent time of member cards
                if len(member_report.card_spent_times) > 0:
                    member_report.avg_card_spent_time = numpy.mean(member_report.card_spent_times)
                    member_report.std_dev_card_spent_time = numpy.std(member_report.card_spent_times)

                # Average and std deviation of the estimated time of member cards
                if len(member_report.card_estimated_times) > 0:
                    member_report.avg_card_estimated_time = numpy.mean(member_report.card_estimated_times)
                    member_report.std_dev_card_estimated_time = numpy.std(member_report.card_estimated_times)

                member_report.save()

    # Return the trello board, calling the Trello API.
    def _get_trello_board(self):
        trello_client = self.creator.trello_client
        trello_board = TrelloBoard(client=trello_client, board_id=self.uuid)
        trello_board.fetch()
        return trello_board


# Card of the task board
class Card(ImmutableModel):
    COMMENT_SPENT_ESTIMATED_TIME_REGEX = r"^plus!\s(?P<spent>(\-)?\d+(\.\d+)?)/(?P<estimated>(\-)?\d+(\.\d+)?)"

    class Meta:
        unique_together = (
            ("uuid", "fetch"),
        )

    name = models.CharField(max_length=128, verbose_name=u"Name of the card")
    uuid = models.CharField(max_length=128, verbose_name=u"Trello id of the card")
    url = models.CharField(max_length=128, verbose_name=u"URL of the card")
    short_url = models.CharField(max_length=128, verbose_name=u"Short URL of the card")
    description = models.TextField(verbose_name=u"Description of the card")
    is_closed = models.BooleanField(verbose_name=u"Is this card closed?", default=False)
    position = models.PositiveIntegerField(verbose_name=u"Position in the list")
    last_activity_date = models.DateTimeField(verbose_name=u"Last activity date")
    spent_time = models.DecimalField(verbose_name=u"Actual card spent time", decimal_places=4, max_digits=12, default=None, null=True)
    estimated_time = models.DecimalField(verbose_name=u"Estimated card completion time", decimal_places=4, max_digits=12, default=None, null=True)
    cycle_time = models.DecimalField(verbose_name=u"Lead time", decimal_places=4, max_digits=12, default=None, null=True)
    lead_time = models.DecimalField(verbose_name=u"Cycle time", decimal_places=4, max_digits=12, default=None, null=True)
    labels = models.ManyToManyField("boards.Label", related_name="cards")

    fetch = models.ForeignKey("boards.Fetch", verbose_name=u"Fetch", related_name="cards")

    board = models.ForeignKey("boards.Board", verbose_name=u"Board", related_name="cards")
    list = models.ForeignKey("boards.List", verbose_name=u"List", related_name="cards")

    @staticmethod
    def factory_from_trello_card(trello_card, board):
        list_ = board.lists.get(uuid=trello_card.idList)

        card = Card(uuid=trello_card.id, name=trello_card.name, url=trello_card.url, short_url=trello_card.short_url,
                    description=trello_card.desc, is_closed=trello_card.closed, position=trello_card.pos,
                    last_activity_date=trello_card.dateLastActivity,
                    board=board, list=list_
                )

        # Card spent and estimated times
        trello_card_comments = trello_card.fetch_comments()
        card_times = Card._get_times_from_trello_comments(trello_card_comments)
        card.spent_time = card_times["spent"]
        card.estimated_time = card_times["estimated"]
        return card

    @staticmethod
    def _get_times_from_trello_comments(comments):
        total_spent = None
        total_estimated = None
        # For each comment, find the desired pattern and extract the spent and estimated times
        for comment in comments:
            comment_content = comment["data"]["text"]
            matches = re.match(Card.COMMENT_SPENT_ESTIMATED_TIME_REGEX, comment_content)
            if matches:
                # Add to total spent
                if total_spent is None:
                    total_spent = 0
                spent = float(matches.group("spent"))
                total_spent += spent
                # Add to total estimated
                if total_estimated is None:
                    total_estimated = 0
                estimated = float(matches.group("estimated"))
                total_estimated += estimated

        return {"estimated": total_estimated, "spent": total_spent}


# Label of the task board
class Label(ImmutableModel):

    class Meta:
        unique_together = (
            ("uuid", "fetch"),
        )

    name = models.CharField(max_length=128, verbose_name=u"Name of the label")
    uuid = models.CharField(max_length=128, verbose_name=u"Trello id of the label")
    color = models.CharField(max_length=128, verbose_name=u"Color of the label")
    board = models.ForeignKey("boards.Board", verbose_name=u"Board", related_name="labels")
    fetch = models.ForeignKey("boards.Fetch", verbose_name=u"Fetch", related_name="labels")

    @staticmethod
    def factory_from_trello_label(trello_label, board):
        return Label(uuid=trello_label.id, name=trello_label.name, color=trello_label.color, board=board)

    def avg_estimated_time(self, **kwargs):
        avg_estimated_time = self.cards.filter(**kwargs).aggregate(Avg("estimated_time"))["estimated_time__avg"]
        return avg_estimated_time

    def avg_spent_time(self, **kwargs):
        avg_spent_time = self.cards.filter(**kwargs).aggregate(Avg("spent_time"))["spent_time__avg"]
        return avg_spent_time

    def avg_cycle_time(self, **kwargs):
        avg_cycle_time = self.cards.filter(**kwargs).aggregate(Avg("cycle_time"))["cycle_time__avg"]
        return avg_cycle_time

    def avg_lead_time(self, **kwargs):
        avg_lead_time = self.cards.filter(**kwargs).aggregate(Avg("lead_time"))["lead_time__avg"]
        return avg_lead_time


# List of the task board
class List(models.Model):
    LIST_TYPES = ("normal", "development", "done")
    LIST_TYPE_CHOICES = (
        ("normal", "Normal"),
        ("development", "In development"),
        ("done", "Done")
    )
    name = models.CharField(max_length=128, verbose_name=u"Name of the board")
    uuid = models.CharField(max_length=128, verbose_name=u"Trello id of the list", unique=True)
    board = models.ForeignKey("boards.Board", verbose_name=u"Board", related_name="lists")
    type = models.CharField(max_length=64, choices=LIST_TYPE_CHOICES, default="normal")


class ListReport(models.Model):
    fetch = models.ForeignKey("boards.Fetch", verbose_name=u"Fetch", related_name="list_reports")
    list = models.ForeignKey("boards.List", verbose_name=u"List", related_name="list_reports")
    forward_movements = models.PositiveIntegerField(verbose_name=u"Forward movements")
    backward_movements = models.PositiveIntegerField(verbose_name=u"Backward movements")
    avg_card_time = models.DecimalField(verbose_name=u"Average time cards live in this list", decimal_places=4, max_digits=12)
    std_dev_card_time = models.DecimalField(verbose_name=u"Average time cards live in this list", decimal_places=4, max_digits=12)


class MemberReport(models.Model):
    fetch = models.ForeignKey("boards.Fetch", verbose_name=u"Fetch", related_name="member_reports")
    board = models.ForeignKey("boards.Board", verbose_name=u"Board", related_name="member_reports")
    number_of_cards = models.PositiveIntegerField(verbose_name=u"Number of assigned cards", default=0)
    member = models.ForeignKey("members.Member", verbose_name=u"Member", related_name="member_reports")
    forward_movements = models.PositiveIntegerField(verbose_name=u"Forward movements")
    backward_movements = models.PositiveIntegerField(verbose_name=u"Backward movements")
    avg_card_time = models.DecimalField(verbose_name=u"Average time a card lives in the board", decimal_places=4, max_digits=12, default=None, null=True)
    std_dev_card_time = models.DecimalField(verbose_name=u"Std. Dev. time a card lives in the board", decimal_places=4, max_digits=12, default=None, null=True)
    avg_card_spent_time = models.DecimalField(verbose_name=u"Average card spent time", decimal_places=4, max_digits=12,
                                                default=None, null=True)
    std_dev_card_spent_time = models.DecimalField(verbose_name=u"Std. Deviation card spent time", decimal_places=4, max_digits=12,
                                              default=None, null=True)
    avg_card_estimated_time = models.DecimalField(verbose_name=u"Average task estimated card completion time", decimal_places=4,
                                         max_digits=12, default=None, null=True)
    std_dev_estimated_time = models.DecimalField(verbose_name=u"Std. Deviation of the estimated card completion time",
                                                  decimal_places=4,
                                                  max_digits=12, default=None, null=True)


class Workflow(models.Model):
    name = models.CharField(max_length=128, verbose_name=u"Name of the workflow")
    board = models.ForeignKey("boards.Board", verbose_name=u"Workflow", related_name="workflows")
    lists = models.ManyToManyField("boards.List", through="WorkflowList", related_name="workflow")


class WorkflowList(models.Model):
    order = models.PositiveIntegerField(verbose_name=u"Order of the list")
    is_done_list = models.BooleanField(verbose_name=u"Informs if the list is a done list", default=False)
    list = models.ForeignKey("boards.List", verbose_name=u"List", related_name="workflowlist")
    workflow = models.ForeignKey("boards.Workflow", verbose_name=u"Workflow", related_name="workflowlists")

