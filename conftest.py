# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
#
# Set up pytest so that any mention of 'backend' as a test argument
# gets run with all four backends.
# Same for ids_type, with all types
from copy import deepcopy
import os
from pathlib import Path

from packaging.version import Version
import importlib_resources
import pytest

from imaspy.dd_zip import dd_etree, latest_dd_version
from imaspy.ids_defs import (
    ASCII_BACKEND,
    HDF5_BACKEND,
    MDSPLUS_BACKEND,
    MEMORY_BACKEND,
    IDS_TIME_MODE_INDEPENDENT,
)
from imaspy.ids_factory import IDSFactory
from imaspy.db_entry import DBEntry
from imaspy.test.test_helpers import open_dbentry

try:
    import imas
except ImportError:
    imas = None
_has_imas = imas is not None

os.environ["IMAS_AL_DISABLE_VALIDATE"] = "1"


def pytest_addoption(parser):
    # if none of these are specified, test with all backends
    parser.addoption("--mdsplus", action="store_true", help="test with MDSPlus backend")
    parser.addoption("--memory", action="store_true", help="test with memory backend")
    parser.addoption("--ascii", action="store_true", help="test with ascii backend")
    parser.addoption("--hdf5", action="store_true", help="test with HDF5 backend")
    parser.addoption("--mini", action="store_true", help="small test with few types")
    parser.addoption(
        "--ids", action="append", help="small test with few types", nargs="+"
    )


_BACKENDS = {
    "ascii": ASCII_BACKEND,
    "memory": MEMORY_BACKEND,
    "hdf5": HDF5_BACKEND,
    "mdsplus": MDSPLUS_BACKEND,
}


@pytest.fixture(scope="session", params=_BACKENDS)
def backend(pytestconfig: pytest.Config, request: pytest.FixtureRequest):
    backends_provided = any(map(pytestconfig.getoption, _BACKENDS))
    if not _has_imas:
        if backends_provided:
            raise RuntimeError(
                "Explicit backends are provided, but IMAS is not available."
            )
        pytest.skip("No IMAS available, skip tests using a backend")
    if backends_provided and not pytestconfig.getoption(request.param):
        pytest.skip(f"Tests for {request.param} backend are skipped.")
    return _BACKENDS[request.param]


@pytest.fixture(scope="session")
def has_imas():
    return _has_imas


@pytest.fixture(scope="session")
def requires_imas():
    if not _has_imas:
        pytest.skip("No IMAS available")


def pytest_generate_tests(metafunc):
    if "ids_name" in metafunc.fixturenames:
        if metafunc.config.getoption("ids"):
            metafunc.parametrize(
                "ids_name",
                [
                    item
                    for arg in metafunc.config.getoption("ids")
                    for item in arg[0].split(",")
                ],
            )
        elif metafunc.config.getoption("mini"):
            metafunc.parametrize("ids_name", ["pulse_schedule"])
        else:
            metafunc.parametrize("ids_name", list(IDSFactory()))


@pytest.fixture(scope="session")
def latest_factory():
    latest_version = latest_dd_version()
    default_factory = IDSFactory()
    default_version = default_factory.version
    # default_version might be a dev version (generated by `git describe`), which cannot
    # be parsed by Version. Take the part before the '-':
    if "-" in default_version:
        default_version = default_version[:default_version.find("-")]
    if Version(default_version) >= Version(latest_version):
        return default_factory
    return IDSFactory(latest_version)


# Fixtures for various assets
@pytest.fixture(scope="session")
def imaspy_assets():
    return importlib_resources.files("imaspy") / "assets"


@pytest.fixture(scope="session")
def fake_toplevel_xml(imaspy_assets):
    return imaspy_assets / "IDS_fake_toplevel.xml"


@pytest.fixture(scope="session")
def ids_minimal(imaspy_assets):
    return imaspy_assets / "IDS_minimal.xml"


@pytest.fixture(scope="session")
def ids_minimal2(imaspy_assets):
    return imaspy_assets / "IDS_minimal_2.xml"


@pytest.fixture(scope="session")
def ids_minimal_struct_array(imaspy_assets):
    return imaspy_assets / "IDS_minimal_struct_array.xml"


@pytest.fixture(scope="session")
def ids_minimal_types(imaspy_assets):
    return imaspy_assets / "IDS_minimal_types.xml"


@pytest.fixture
def fake_structure_xml(fake_toplevel_xml):
    tree = dd_etree(version=None, xml_path=fake_toplevel_xml)
    return deepcopy(tree.find("IDS"))


@pytest.fixture
def fake_filled_toplevel(fake_toplevel_xml: Path, worker_id: str, tmp_path: Path) -> DBEntry:
    """A very specifically filled smallish toplevel"""
    dbentry = open_dbentry(
        MEMORY_BACKEND, "w", worker_id, tmp_path, xml_path=fake_toplevel_xml
    )
    # Take a small toplevel and partially fill it with very specific fields
    top = dbentry.factory.new("gyrokinetics")
    top.wavevector.resize(1)
    top.wavevector[0].eigenmode.resize(1)
    eig = top.wavevector[0].eigenmode[0]
    eig.frequency_norm = 10
    top.ids_properties.homogeneous_time = IDS_TIME_MODE_INDEPENDENT
    dbentry.put(top)

    yield dbentry.get("gyrokinetics")

    dbentry.close()
