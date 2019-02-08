LarderAPI
========

This is a simple wrapper for the [Larder.io](https://larder.io) API.

Currently it only supports (some) read-only operations, 
mostly meant for backup activities.

Requirements
-----------

* Python 3.7 or 3.6 (if 3.6, you have to manually `pip install dataclasses`)
* `pip install -r requirements.txt`

Basic Usage
----------

```python
from LarderAPI import *
init("your token here")
folders = Folder.get_all_folders()
my_folder = folders[0]

# folders by default are retrieved with all metadata except bookmarks.
# to trigger bookmark download, use .get_bookmarks() on the object
bookmarks = my_folder.get_bookmarks()

# all objects with timestamps have python datetime accessors
print(my_folder.created_date)
print(bookmarks[0].modified_date)
```

LarderBackup.py
---------------
LarderBackup is a simple script to back-up all bookmarks.

Usage: `python3 LarderBackup.py <token> <destination directory>`

It will create a Netscape-format file in the specified directory,
e.g. `LarderBackup_2019-02-07_22:09:31.html`.

Note that tags will not be backed up. 

Contribute
----------

Pull requests are welcome! 

License
-------

LarderAPI is @ 2019 Giacomo Lacava, released under the terms of 
the General Public License 3.