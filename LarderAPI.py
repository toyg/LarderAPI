import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from time import sleep

import requests

API_URL = "https://larder.io/api/1/"
API_FOLDERS_URL = API_URL + "@me/folders/"
API_BOOKMARKS_BY_FOLDER_URL = API_FOLDERS_URL + "{folder_id}/"


@dataclass
class TimestampedObject:
    """ Superclass for objects carrying timestamps"""

    created: str
    modified: str

    @property
    def created_date(self):
        return _json_to_pydate(self.created)

    @property
    def modified_date(self):
        return _json_to_pydate(self.modified)


@dataclass
class Folder(TimestampedObject):
    """ Lazy-loading Folder representation. """
    id: str
    name: str
    color: str
    icon: str
    parent: str
    links: int = 0
    folders: list = field(default_factory=list)
    bookmarks: list = field(default_factory=list)
    _fetched: bool = False

    @property
    def loaded(self):
        return self._fetched

    @property
    def subfolders(self):
        """ json returned by Larder clearly allows for subfolders to exist,
        although the web interface currently cannot create them."""
        return [Folder(**f) for f in self.folders]

    @staticmethod
    def get_all_folders():
        """ retrieve all Folders in your account. """
        logging.debug("Fetch all folders initiated")
        folder_instances = []
        next_fetch = API_FOLDERS_URL  # + f"?limit={num_items_per_page}&offset=0"
        while next_fetch is not None:
            logging.debug(f"Calling {next}")
            folders_json = Fetcher.fetch_json(next_fetch)
            folder_objects = [Folder(**f) for f in folders_json["results"]]
            folder_instances.extend(folder_objects)
            next_fetch = folders_json["next"]
            sleep(1)  # be nice to avoid throttling
        logging.debug("Fetch folders completed")
        return folder_instances

    def get_bookmarks(self):
        """ retrieve all bookmarks in a folder."""
        if not self._fetched:
            self.bookmarks = []
            logging.debug(f"Fetching bookmarks for {self.name}")
            next_page = API_BOOKMARKS_BY_FOLDER_URL.format(folder_id=self.id)
            while next_page is not None:
                logging.debug(f"calling {next_page}")
                bm_json = Fetcher.fetch_json(next_page)
                bm_objects = [Bookmark(**bm) for bm in bm_json["results"]]
                self.bookmarks.extend(bm_objects)
                next_page = bm_json["next"]
                sleep(1)
            self._fetched = True
            logging.debug(f"DONE fetching bookmarks for {self.name}")
        return self.bookmarks

    def refresh_bookmarks(self):
        """ discard current representation and reload bookmarks"""
        self._fetched = False
        self.get_bookmarks()


@dataclass
class Bookmark(TimestampedObject):
    """ Bookmark representation """
    id: str
    title: str
    description: str
    url: str
    domain: str
    tags: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        tt = [BookmarkTag(**t) for t in self.tags]
        self.tags = tt


@dataclass
class BookmarkTag(TimestampedObject):
    """ Tag representation """
    id: str
    name: str
    color: str


def _json_to_pydate(date_string):
    """ Convert dates appearing in json api (presumably UTC) to Python datetime"""
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ").astimezone(timezone.utc)


class AuthMode(Enum):
    """ Supported authentication mechanisms"""
    TOKEN = 1
    OAUTH = 2


class Fetcher:
    """ Utility to retrieve api calls"""
    token = None
    auth_mode = AuthMode.TOKEN

    @staticmethod
    def init(token_string: str, auth_mode: AuthMode = AuthMode.TOKEN):
        """Provide the token that API requires to work. This must always be called before other API activities"""
        if auth_mode == AuthMode.OAUTH:
            raise NotImplementedError("OAuth is not supported yet.")
        Fetcher.token = token_string
        Fetcher.auth_mode = auth_mode

    @staticmethod
    def fetch_json(url):
        """ Fetch a given URL and return JSON object"""
        token_name = "Bearer" if Fetcher.auth_mode == AuthMode.OAUTH else "Token"

        if not Fetcher.token:
            raise Exception("Call Fetcher.init(token) before performing other operations")
        return requests.get(url,
                            headers={"Authorization": f"{token_name} {Fetcher.token}"}
                            ).json()


# aliasing
init = Fetcher.init
