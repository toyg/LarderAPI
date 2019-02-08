# Copyright (c) 2019 Giacomo Lacava
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program. If not, see https://www.gnu.org/licenses/ .

import logging
from copy import copy
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone
from enum import Enum
from time import sleep

import requests

API_URL = "https://larder.io/api/1/"

LINK_MAP = {'Folder': 'folders',
            'Bookmark': 'links',
            'Tag': 'tags'}

# folders are a bit special, so we cache them
_FOLDERCACHE = {}


class EmptyObjectException(Exception):
    pass


@dataclass
class RESTObject:
    """ Base class for common CRUD operations."""

    id: str = None

    @classmethod
    def _get_qualified_apiurl(cls):
        """ get the base url for the object type """
        return API_URL + f"@me/{LINK_MAP.get(cls.__name__)}/"

    def delete(self):
        """ delete instance """
        if self.id is not None:
            HttpInterface.delete(f"{self._get_qualified_apiurl()}{self.id}/delete/")

    def load(self):
        """ load instance details """
        if self.id is not None:
            result_json = HttpInterface.get(f"{self._get_qualified_apiurl()}{self.id}/")
        else:
            raise EmptyObjectException("Cannot load an object without an ID")

    def save(self):
        """ create or update the instance. """
        result_json = {}
        if not self.id:
            # create
            result_json = HttpInterface.post(
                f"{self._get_qualified_apiurl()}add/",
                asdict(self)
            ).json()
        else:
            # update
            result_json = HttpInterface.post(
                f"{self._get_qualified_apiurl()}{self.id}/edit/",
                asdict(self)
            ).json()
        for key, value in result_json.items():
            setattr(self, key, value)

    @classmethod
    def get_all(cls):
        """ retrieve all instances of this type. """
        instances = []
        next_fetch = cls._get_qualified_apiurl()
        while next_fetch is not None:
            logging.debug(f"Calling {next}")
            objects_json = HttpInterface.get(next_fetch)
            folder_objects = [cls(**f) for f in objects_json["results"]]
            instances.extend(folder_objects)
            next_fetch = objects_json["next"]
            sleep(1)  # be nice to avoid throttling
        return instances


@dataclass
class TimestampedObject(RESTObject):
    """ Superclass for objects carrying timestamps"""

    created: str = None
    modified: str = None

    @property
    def created_date(self):
        return _json_to_pydate(self.created)

    @property
    def modified_date(self):
        return _json_to_pydate(self.modified)


@dataclass
class Folder(TimestampedObject):
    """ Lazy-loading Folder representation.
    Folder is a bit special, because a folder canonical url is actually returning
    all bookmarks it contains. For this reason, we implement an alternative scheme
    based on caching get_all().
    """
    name: str = None
    color: str = None
    icon: str = None
    parent: str = None
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

    @classmethod
    def get_all(cls):
        """ retrieve all Folders in your account.
        It overrides standard get_all() to cache them."""
        folder_instances = super().get_all()
        _FOLDERCACHE = folder_instances
        return copy(folder_instances)

    def load(self):
        """ override default call to avoid taking down unnecessary data """
        cached_instance = _FOLDERCACHE.get(self.id)
        if cached_instance is None:
            raise EmptyObjectException("Cannot load an object without an ID")
        for field in fields(self):
            setattr(self, field.name, getattr(cached_instance, field))

    def save(self):
        """ override to keep caching updated """
        super().save()
        _FOLDERCACHE[self.id] = self

    def get_bookmarks(self):
        """ retrieve all bookmarks in a folder."""
        if not self._fetched:
            self.bookmarks = []
            logging.debug(f"Fetching bookmarks for {self.name}")
            next_page = f"{self._get_qualified_apiurl()}{self.id}/"
            while next_page is not None:
                logging.debug(f"calling {next_page}")
                bm_json = HttpInterface.get(next_page)
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
    url: str = None
    title: str = None
    description: str = None
    domain: str = None
    tags: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        tt = [Tag(**t) for t in self.tags]
        self.tags = tt

    def load(self):
        raise NotImplemented("You cannot retrieve a link by ID, this is a limitation of the API. "
                             "Get bookmarks from folders or search (when we implement that).")


@dataclass
class Tag(TimestampedObject):
    """ Tag representation.
    Note: you cannot instantiate a tag by name.
    This is a limitation of the Larder API.
    To edit a tag you didn't create, get all tags first and search in there."""

    name: str = None
    color: str = None

    def save(self):
        if self.name is None:
            raise ValueError("You cannot save a tag without a name")
        super().save()

    def load(self):
        raise NotImplemented("You cannot retrieve a tag by name or ID")


def _json_to_pydate(date_string):
    """ Convert dates appearing in json api (presumably UTC) to Python datetime"""
    return datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ").astimezone(timezone.utc)


class AuthMode(Enum):
    """ Supported authentication mechanisms"""
    TOKEN = 1
    OAUTH = 2


class HttpInterface:
    """ Utility to make api calls"""
    token = None
    auth_mode = AuthMode.TOKEN

    @staticmethod
    def init(token_string: str, auth_mode: AuthMode = AuthMode.TOKEN):
        """Provide the token that API requires to work. This must always be called before other API activities"""
        if auth_mode == AuthMode.OAUTH:
            raise NotImplementedError("OAuth is not supported yet.")
        HttpInterface.token = token_string
        HttpInterface.auth_mode = auth_mode

    @staticmethod
    def build_headers():
        token_name = "Bearer" if HttpInterface.auth_mode == AuthMode.OAUTH else "Token"
        if not HttpInterface.token:
            raise Exception("Call LarderAPI.init(token) before performing other operations")
        return {"Authorization": f"{token_name} {HttpInterface.token}"}

    @staticmethod
    def get(url):
        """ Fetch a given URL and return JSON object"""
        logging.debug(f"GET on {url}")
        headers = HttpInterface.build_headers()
        return requests.get(url,
                            headers=headers
                            ).json()

    @staticmethod
    def delete(url):
        logging.debug(f"DELETE on {url}")
        headers = HttpInterface.build_headers()
        result = requests.delete(url, headers=headers)
        logging.debug(result.status_code)
        if result.status_code != 204:
            raise IOError(f"Deletion operation failed, {url} \n returned code {result.status_code} : {result.text}")

    @staticmethod
    def post(url, params):
        logging.debug(f"POST on {url}")
        headers = HttpInterface.build_headers()
        result = requests.post(url, params, headers=headers)
        logging.debug(result.status_code)
        if result.status_code != 201:
            raise IOError(f"POST operation failed, {url} \n returned code {result.status_code} : {result.text}")
        return result


# aliasing
init = HttpInterface.init
