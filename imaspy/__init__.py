# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.

# isort: skip_file

from packaging.version import Version as _V

from . import _version

__version__ = _version.get_versions()["version"]

version = __version__

# Import logging _first_
from . import setup_logging

# Import main user API objects in the imaspy module
from .db_entry import DBEntry
from .ids_factory import IDSFactory
from .ids_convert import convert_ids
from .ids_identifiers import identifiers

# Load the IMASPy IMAS AL/DD core
from . import (
    db_entry,
    dd_helpers,
    dd_zip,
    util,
)

PUBLISHED_DOCUMENTATION_ROOT = (
    "https://sharepoint.iter.org/departments/POP/CM/IMDesign/"
    "Code%20Documentation/IMASPy-doc"
)
"""URL to the published documentation."""
OLDEST_SUPPORTED_VERSION = _V("3.22.0")
"""Oldest Data Dictionary version that is supported by IMASPy."""
