import os
import sys
import time
import traceback

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand

from djangotrellostats.apps.members.models import Member


class Command(BaseCommand):
    help = 'Fetch board data'

    FETCH_LOCK_FILE_PATH = "/tmp/django-trello-stats-fetch-lock.txt"

    def __init__(self, stdout=None, stderr=None, no_color=False):
        super(Command, self).__init__(stdout=None, stderr=None, no_color=False)
        self.start_time = None
        self.end_time = None

    def add_arguments(self, parser):
        parser.add_argument('member_trello_username', nargs='+', type=str)

    def start(self):
        self.start_time = time.time()
        # Check if lock file exists. If it exists, thrown an error
        if os.path.isfile(Command.FETCH_LOCK_FILE_PATH):
            self.stdout.write(self.style.ERROR(u"Lock is in place. Unable to fetch"))
            return False

        # Creates a new lock file
        self.stdout.write(self.style.SUCCESS(u"Lock does not exist. Creating..."))
        lock_file = open(Command.FETCH_LOCK_FILE_PATH, 'w')
        lock_file.write("Fetching data...")
        lock_file.close()
        self.stdout.write(self.style.SUCCESS(u"Lock file created"))
        return True

    def end(self):
        self.end_time = time.time()
        # Lock file must exist
        if not os.path.isfile(Command.FETCH_LOCK_FILE_PATH):
            self.stdout.write(self.style.ERROR(u"Lock does not exist. Cancel operation"))
            return False

        # Deleting the lock file
        os.remove(Command.FETCH_LOCK_FILE_PATH)

        self.stdout.write(self.style.SUCCESS(u"Lock file deleted"))

    def elapsed_time(self):
        return self.end_time - self.start_time

    def handle(self, *args, **options):
        try:
            member_trello_username = options['member_trello_username'][0]
        except (IndexError, KeyError)as e:
            self.stdout.write(self.style.ERROR("member_username is mandatory"))
            return False

        member = Member.objects.get(trello_username=member_trello_username)
        if not member.is_initialized():
            self.stderr.write(self.style.SUCCESS(u"Member {0} is not initialized".format(member.trello_username)))
            return True

        if not self.start():
            self.stdout.write(self.style.ERROR("Unable to fetch"))
            self.warn_administrators(subject=u"Unable to fetch boards", message=u"Unable to fetch boards. Is the lock file present?")
            return False

        try:
            # For each board that is ready, fetch it
            for board in member.created_boards.all():
                if board.is_ready():
                    self.stdout.write(self.style.SUCCESS(u"Board {0} is ready".format(board.name)))
                    board.fetch(debug=False)
                    self.stdout.write(self.style.SUCCESS(u"Board {0} fetched successfully".format(board.name)))
                else:
                    self.stdout.write(self.style.ERROR(u"Board {0} is not ready".format(board.name)))
            self.stdout.write(self.style.SUCCESS(u"All boards fetched successfully {0}".format(self.elapsed_time())))

        # If there is any exception, warn the administrators
        except Exception as e:
            self.warn_administrators(subject=u"Error when fetching boards", message=traceback.format_exc())
            self.stdout.write(self.style.ERROR(u"Error when fetching boards"))

        # Always delete the lock file
        finally:
            self.end()

    # Warn administrators of an error
    def warn_administrators(self, subject, message):
        email_subject = u"[DjangoTrelloStats] [Warning] {0}".format(subject)

        administrator_group = Group.objects.get(name=settings.ADMINISTRATOR_GROUP)
        administrator_users = administrator_group.user_set.all()
        for administrator_user in administrator_users:
            email_message = EmailMultiAlternatives(email_subject, message, settings.EMAIL_HOST_USER, [administrator_user.email])
            email_message.send()
