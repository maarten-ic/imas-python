"""A testcase checking if writing and then reading works for the latest full
data dictionary version.
"""

import logging
import os
from pathlib import Path

import numpy as np
import pytest

import imaspy
from imaspy.ids_defs import ASCII_BACKEND, IDS_TIME_MODE_HOMOGENEOUS, MEMORY_BACKEND
from imaspy.test_helpers import compare_children, fill_with_random_data, visit_children

root_logger = logging.getLogger("imaspy")
logger = root_logger
logger.setLevel(logging.WARNING)


# TODO: use a separate folder for the MDSPLUS DB and clear it after the testcase
def test_latest_dd_autofill(ids_name, backend):
    """Write and then read again a full IDSRoot and a single IDSToplevel."""
    ids = open_ids(backend, "w")
    fill_with_random_data(ids[ids_name])

    assert ids[ids_name].readHomogeneous(0).value == IDS_TIME_MODE_HOMOGENEOUS

    ids[ids_name].put()

    if backend == MEMORY_BACKEND:
        # this one does not store anything between instantiations
        pass
    else:
        ids2 = open_ids(backend, "a")
        ids2[ids_name].get()

        if backend == ASCII_BACKEND:
            logger.warning("Skipping ASCII backend tests for empty arrays")
            compare_children(
                ids[ids_name], ids2[ids_name], _ascii_empty_array_skip=True
            )
        else:
            compare_children(ids[ids_name], ids2[ids_name])


def open_ids(backend, mode):
    ids = imaspy.ids_root.IDSRoot(1, 0)
    ids.open_ual_store(os.environ.get("USER", "root"), "test", "3", backend, mode=mode)
    return ids
