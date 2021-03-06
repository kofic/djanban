from __future__ import unicode_literals, absolute_import

import os
import time
from io import open


# Abstract board fetcher
from djanban.apps.boards.models import CardComment


class Fetcher(object):
    FETCH_LOCK_FILE_PATH = u"/tmp/django-trello-stats-fetch-board-{0}-lock.txt"

    # Creates a Fetcher object for a board
    def __init__(self, board):
        super(Fetcher, self).__init__()
        self.board = board
        self.cycle_lists = board.cycle_time_lists()
        self.lead_lists = board.lead_time_lists()
        self.lists = board.lists.all()
        self.members = board.members.all()
        self.creator = board.creator

        self.fetch_start_time = None
        self.fetch_end_time = None

    # Prepare the fetch process
    def _start_fetch(self):
        self.fetch_start_time = time.time()
        fetch_lock_file_path = Fetcher.FETCH_LOCK_FILE_PATH.format(self.board.id)
        # Check if lock file exists. If it exists, warn the fetch method
        if os.path.isfile(fetch_lock_file_path):
            raise AssertionError("Lock file {0} already exists".format(fetch_lock_file_path))

        # Creates a new lock file
        with open(fetch_lock_file_path, 'w', encoding="utf-8") as lock_file:
            lock_file.write("Fetching data for board {0}".format(self.board.name))

        return True

    # Ends the fetch process
    def _end_fetch(self):
        self.fetch_end_time = time.time()
        fetch_lock_file_path = Fetcher.FETCH_LOCK_FILE_PATH.format(self.board.id)
        # Lock file must exist
        if not os.path.isfile(fetch_lock_file_path):
            raise AssertionError("Lock file {0} does not exist".format(fetch_lock_file_path))

        # Deleting the lock file
        os.remove(fetch_lock_file_path)

    # Delete all children entities but lists and workflows
    def _truncate(self):
        self.board.clean_cached_charts()

