import concurrent
import logging
import sys
from concurrent.futures import as_completed
from datetime import datetime
from operator import attrgetter
from pathlib import Path
from queue import Queue
from threading import Lock
from time import sleep

import LarderAPI
from LarderAPI import Folder, AuthMode

OUTPUT_HEADER = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!--This is an automatically generated file.
    It will be read and overwritten.
    Do Not Edit! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<Title>Bookmarks</Title>
<H1>Bookmarks</H1>
<DL><p>
"""
OUTPUT_FOOTER = """</DL>
"""
OUTPUT_FOLDER_HEADER = """<DT><H3 ADD_DATE="{folder_add_ts}" LAST_MODIFIED="{folder_last_ts}">{folder_name}</H3>
<DL><p>
"""
OUTPUT_FOLDER_FOOTER = """</DL><p>
"""

OUTPUT_BM = """<DT><A HREF="{bm_url}" ADD_DATE="{bm_add_ts}" LAST_MODIFIED="{bm_last_ts}">{bm_title}</A>
"""

writer_lock = Lock()


def _load_folder(folder: Folder, task_queue: Queue):
    """ trigger lazy-loading of bookmarks, then push object on the task queue"""
    folder.refresh_bookmarks()
    task_queue.put_nowait(folder)
    sleep(1)


def _process_folder(writer, task_queue: Queue):
    """ retrieve a Folder object from task queue and add it to output """
    folder_object = task_queue.get()
    with writer_lock:
        _dump_folder_to_output(writer, folder_object)
    task_queue.task_done()


def _dump_folder_to_output(writer, folder_instance: Folder):
    """ given a filelike object, serialize the folder instance"""
    logging.debug(f"writing output for {folder_instance.name}...")
    writer.write(OUTPUT_FOLDER_HEADER.format(folder_add_ts=int(folder_instance.created_date.timestamp()),
                                             folder_last_ts=int(folder_instance.modified_date.timestamp()),
                                             folder_name=folder_instance.name))
    for bookmark in sorted(folder_instance.bookmarks, key=attrgetter("title")):
        writer.write(OUTPUT_BM.format(bm_url=bookmark.url,
                                      bm_add_ts=int(bookmark.created_date.timestamp()),
                                      bm_last_ts=int(bookmark.modified_date.timestamp()),
                                      bm_title=bookmark.title))
    writer.write(OUTPUT_FOLDER_FOOTER)
    logging.debug(f"... DONE writing output for {folder_instance.name}")


def backup(token: str,
           target_folder: str,
           auth_mode: AuthMode = AuthMode.TOKEN):
    """ backup an entire Larder account to Netscape-style file in the given folder.
    :param token - the token you can get from Larder settings
    :param auth_mode - reserved for future usage, just rely on default for now.
    """

    logging.info("Starting Larder backup...")
    LarderAPI.init(token, auth_mode)
    task_queue = Queue()
    fetches = []
    writes = []
    logging.info("Retrieving folders...")
    folders = Folder.get_all_folders()
    logging.info("... folders retrieved.")
    target_file = Path(target_folder) / "LarderBackup_{:%Y-%m-%d_%H:%M:%S}.html".format(datetime.now())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        with open(target_file, 'w', encoding="utf-8") as out_file:
            out_file.write(OUTPUT_HEADER)
            for f in folders:
                fetches.append(executor.submit(_load_folder, f, task_queue))
                writes.append(executor.submit(_process_folder, out_file, task_queue))
            fetches_done = list(as_completed(fetches))
            logging.info("All bookmarks retrieved.")
            writes_done = list(as_completed(writes))
            logging.info(f"Completed writing to {target_file}")
            out_file.write(OUTPUT_FOOTER)
    logging.info("... backup completed.")


if __name__ == "__main__":
    if len(sys.argv < 3):
        print("Usage: LarderBackup.py <token> <destination directory>")
        sys.exit(1)
    backup(sys.argv[1], sys.argv[2])
