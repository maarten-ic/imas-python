# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
"""Represents a Top-level IDS (like ``core_profiles``, ``equilibrium``, etc)
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from imaspy.backends.imas_core.imas_interface import ll_interface
from imaspy.exception import ValidationError
from imaspy.ids_base import IDSDoc
from imaspy.ids_defs import (
    ASCII_BACKEND,
    ASCII_SERIALIZER_PROTOCOL,
    DEFAULT_SERIALIZER_PROTOCOL,
    IDS_TIME_MODE_INDEPENDENT,
    IDS_TIME_MODE_UNKNOWN,
    IDS_TIME_MODES,
    needs_imas,
)
from imaspy.ids_metadata import IDSMetadata, IDSType, get_toplevel_metadata
from imaspy.ids_structure import IDSStructure

if TYPE_CHECKING:
    from imaspy.db_entry import DBEntry
    from imaspy.ids_factory import IDSFactory


logger = logging.getLogger(__name__)


def _serializer_tmpdir() -> str:
    env_tmpdir = os.getenv("IMAS_AL_SERIALIZER_TMP_DIR")
    if env_tmpdir:
        return env_tmpdir
    return "/dev/shm" if os.path.exists("/dev/shm") else "."


def _create_serialization_dbentry(filepath: str, dd_version: str) -> "DBEntry":
    """Create a temporary DBEntry for use in the ASCII serialization protocol."""
    from imaspy.db_entry import DBEntry  # Local import to avoid circular imports

    if ll_interface._al_version.major == 4:  # AL4 compatibility
        dbentry = DBEntry(
            ASCII_BACKEND, "serialize", 1, 1, "serialize", dd_version=dd_version
        )
        dbentry.create(options=f"-fullpath {filepath}")
        return dbentry
    else:  # AL5
        path = Path(filepath)
        return DBEntry(
            f"imas:ascii?path={path.parent};filename={path.name}",
            "w",
            dd_version=dd_version,
        )


class IDSToplevel(IDSStructure):
    """This is any IDS Structure which has ids_properties as child node

    At minimum, one should fill ids_properties/homogeneous_time
    IF a quantity is filled, the coordinates of that quantity must be filled as well
    """

    __doc__ = IDSDoc(__doc__)
    _path = ""  # Path to ourselves without the IDS name and slashes

    def __init__(self, parent: "IDSFactory", structure_xml, lazy=False):
        """Save backend_version and backend_xml and build translation layer.

        Args:
            parent: Parent of ``self``.
            structure_xml: XML structure that defines this IDS toplevel.
            lazy: Whether this toplevel is used for a lazy-loaded get() or get_slice()
        """
        self._lazy = lazy
        # structure_xml might be an IDSMetadata already when initializing from __copy__
        # or __deepcopy__
        if isinstance(structure_xml, IDSMetadata):
            metadata = structure_xml
        else:
            metadata = get_toplevel_metadata(structure_xml)
        super().__init__(parent, metadata)

    def __deepcopy__(self, memo):
        copy = super().__deepcopy__(memo)
        copy._lazy = self._lazy
        return copy

    @property
    def _dd_version(self) -> str:
        return self._version

    @property
    def _time_mode(self) -> int:
        """Retrieve the time mode from `/ids_properties/homogeneous_time`"""
        return self.ids_properties.homogeneous_time

    @property
    def _is_dynamic(self) -> bool:
        return False

    @staticmethod
    def default_serializer_protocol():
        """Return the default serializer protocol."""
        return DEFAULT_SERIALIZER_PROTOCOL

    @needs_imas
    def serialize(self, protocol=None):
        """Serialize this IDS to a data buffer.

        The data buffer can be deserialized from any Access Layer High-Level Interface
        that supports this. Currently known to be: IMASPy, Python, C++ and Fortran.

        Example:

        .. code-block: python

            core_profiles = imaspy.IDSFactory().core_profiles()
            # fill core_profiles with data
            ...

            data = core_profiles.serialize()

            # For example, send `data` to another program with libmuscle.
            # Then deserialize on the receiving side:

            core_profiles = imaspy.IDSFactory().core_profiles()
            core_profiles.deserialize(data)
            # Use core_profiles:
            ...

        Args:
            protocol: Which serialization protocol to use. Currently only
                ASCII_SERIALIZER_PROTOCOL is supported.

        Returns:
            Data buffer that can be deserialized using :meth:`deserialize`.
        """
        if protocol is None:
            protocol = self.default_serializer_protocol()
        if self.ids_properties.homogeneous_time == IDS_TIME_MODE_UNKNOWN:
            raise ValueError("IDS is found to be EMPTY (homogeneous_time undefined)")
        if protocol == ASCII_SERIALIZER_PROTOCOL:
            tmpdir = _serializer_tmpdir()
            filepath = tempfile.mktemp(prefix="al_serialize_", dir=tmpdir)
            dbentry = _create_serialization_dbentry(filepath, self._dd_version)
            dbentry.put(self)
            dbentry.close()

            try:
                # read contents of tmpfile
                with open(filepath, "rb") as f:
                    data = f.read()
            finally:
                os.unlink(filepath)  # remove tmpfile from disk
            return bytes([ASCII_SERIALIZER_PROTOCOL]) + data
        raise ValueError(f"Unrecognized serialization protocol: {protocol}")

    @needs_imas
    def deserialize(self, data):
        """Deserialize the data buffer into this IDS.

        See :meth:`serialize` for an example.

        Args:
            data: binary data created by serializing an IDS.
        """
        if len(data) <= 1:
            raise ValueError("No data provided")
        protocol = int(data[0])  # first byte of data contains serialization protocol
        if protocol == ASCII_SERIALIZER_PROTOCOL:
            tmpdir = _serializer_tmpdir()
            filepath = tempfile.mktemp(prefix="al_serialize_", dir=tmpdir)
            # write data into tmpfile
            try:
                with open(filepath, "wb") as f:
                    f.write(data[1:])
                # Temporarily open an ASCII backend for deserialization from tmpfile
                dbentry = _create_serialization_dbentry(filepath, self._dd_version)
                dbentry.get(self.metadata.name, destination=self)
                dbentry.close()
            finally:
                # tmpfile may not exist depending if an error occurs in above code
                if os.path.exists(filepath):
                    os.unlink(filepath)
        else:
            raise ValueError(f"Unrecognized serialization protocol: {protocol}")

    def validate(self):
        """Validate the contents of this IDS.

        The following sanity checks are executed on this IDS:

        - The IDS must have a valid time mode (``ids_properties.homogeneous_time``)
        - For all non-empty quantities with coordinates:

            - If coordinates have an exact size (e.g. coordinate1 = 1...3), the size in
              that dimension must match this.
            - If coordinates refer to other elements (e.g. coordinate1 = time), the size
              in that dimension must be the same as the size of the referred quantity.

              Note that time is a special coordinate:

              - When using homogeneous time, the time coordinate is the /time node.
              - When using heterogeneous time, the time coordinate is the one specified
                by the coordinate. For dynamic Array of Structures, the time element is
                a FLT_0D inside the AoS (see ``profiles_1d`` in the core_profiles IDS).
                In such cases the time element must be set.
              - When using independent time mode, no time-dependent quantities may be
                set.

            - If a "same_as" coordinate is specified (e.g. coordinate2_same_as = r), the
              size in that dimension must be the same as the size in that dimension of
              the referred quantity.

        If any check fails, a ValidationError is raised that describes the problem.

        Example:

            >>> core_profiles = imaspy.IDSFactory().core_profiles()
            >>> core_profiles.validate()  # Did not set homogeneous_time
            [...]
            imaspy.exception.ValidationError: Invalid value for ids_properties/homogeneous_time: IDSPrimitive("/core_profiles/ids_properties/homogeneous_time", -999999999)
            >>> core_profiles.ids_properties.homogeneous_time = imaspy.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
            >>> core_profiles.validate()  # No error: IDS is valid
            >>> core_profiles.profiles_1d.resize(1)
            >>> core_profiles.validate()
            [...]
            imaspy.exception.CoordinateError: Dimension 1 of element profiles_1d has incorrect size 1. Expected size is 0 (size of coordinate time).
            >>> core_profiles.time = [1]
            >>> core_profiles.validate()  # No error: IDS is valid

        """  # noqa: E501 (line too long)
        if self._lazy:
            logger.warning(
                "Validating lazy loaded IDS '%s': this will not validate the full "
                "IDS, only the loaded data is validated.",
                self.metadata.name,
            )
        time_mode = self._time_mode
        if time_mode not in IDS_TIME_MODES:
            raise ValidationError(
                f"Invalid value for ids_properties/homogeneous_time: {time_mode.value}"
            )
        if self.metadata.type is IDSType.CONSTANT:  # IMAS-3330 static IDS
            if time_mode != IDS_TIME_MODE_INDEPENDENT:
                raise ValidationError(
                    f"Invalid value for ids_properties/homogeneous_time: {time_mode}. "
                    "The IDS is static, therefore homogeneous_time must be "
                    f"IDS_TIME_MODE_INDEPENDENT ({IDS_TIME_MODE_INDEPENDENT})."
                )
        try:
            self._validate()
        except ValidationError as exc:
            # hide recursive stack trace from user
            logger.debug("Original stack-trace of ValidationError: ", exc_info=1)
            raise exc.with_traceback(None) from None

    def _validate(self):
        # Override to skip the self.metadata.type.is_dynamic check in IDSBase._validate
        # accept_lazy=True: users are warned in IDSToplevel.validate()
        for child in self.iter_nonempty_(accept_lazy=True):
            child._validate()

    @needs_imas
    def get(self, occurrence: int = 0, db_entry: Optional["DBEntry"] = None) -> None:
        """Get data from AL backend storage format.

        This method exists for API compatibility with the IMAS python HLI.
        See :py:meth:`DBEntry.get <imaspy.db_entry.DBEntry.get>`.
        """
        if db_entry is None:
            raise NotImplementedError()
        db_entry.get(self.metadata.name, occurrence, destination=self)

    @needs_imas
    def getSlice(
        self,
        time_requested: float,
        interpolation_method: int,
        occurrence: int = 0,
        db_entry: Optional["DBEntry"] = None,
    ) -> None:
        """Get a slice from the backend.

        This method exists for API compatibility with the IMAS python HLI.
        See :py:meth:`DBEntry.get_slice <imaspy.db_entry.DBEntry.get_slice>`.
        """
        if db_entry is None:
            raise NotImplementedError()
        db_entry.get_slice(
            self.metadata.name,
            time_requested,
            interpolation_method,
            occurrence,
            destination=self,
        )

    @needs_imas
    def putSlice(
        self, occurrence: int = 0, db_entry: Optional["DBEntry"] = None
    ) -> None:
        """Put a single slice into the backend.

        This method exists for API compatibility with the IMAS python HLI.
        See :py:meth:`DBEntry.put_slice <imaspy.db_entry.DBEntry.put_slice>`.
        """
        if db_entry is None:
            raise NotImplementedError()
        db_entry.put_slice(self, occurrence)

    @needs_imas
    def deleteData(
        self, occurrence: int = 0, db_entry: Optional["DBEntry"] = None
    ) -> None:
        """Delete AL backend storage data.

        This method exists for API compatibility with the IMAS python HLI.
        See :py:meth:`DBEntry.delete_data <imaspy.db_entry.DBEntry.delete_data>`.
        """
        if db_entry is None:
            raise NotImplementedError()
        db_entry.delete_data(self, occurrence)

    @needs_imas
    def put(self, occurrence: int = 0, db_entry: Optional["DBEntry"] = None) -> None:
        """Put this IDS to the backend.

        This method exists for API compatibility with the IMAS python HLI.
        See :py:meth:`DBEntry.put <imaspy.db_entry.DBEntry.put>`.
        """
        if db_entry is None:
            raise NotImplementedError()
        db_entry.put(self, occurrence)

    def __repr__(self):
        my_repr = f"<{type(self).__name__}"
        my_repr += f" (IDS:{self.metadata.name})>"
        return my_repr

    @property
    def _toplevel(self) -> "IDSToplevel":
        """Return ourselves"""
        # Used to cut off recursive call
        return self
