# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
"""Logic for interpreting coordinates in an IDS
"""

from contextlib import contextmanager
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

import numpy as np
from imaspy.exception import CoordinateError, CoordinateLookupError, ValidationError

from imaspy.ids_data_type import IDSDataType
from imaspy.ids_defs import (
    IDS_TIME_MODE_HOMOGENEOUS as HOMOGENEOUS_TIME,
    IDS_TIME_MODE_HETEROGENEOUS as HETEROGENEOUS_TIME,
    EMPTY_FLOAT,
)
from imaspy.ids_path import IDSPath

if TYPE_CHECKING:  # Prevent circular imports
    from imaspy.ids_mixin import IDSMixin
    from imaspy.ids_primitive import IDSPrimitive

logger = logging.getLogger(__name__)


class IDSCoordinate:
    """Class representing a coordinate reference from the DD.

    Example:
        - Coordinates are an index:

          - ``1...N``: any number of items allowed
          - ``1...3``: max 3 items allowed

        - Coordinates refer to other quantities:

          - ``time``: refers to the ``time`` quantity in the IDS toplevel
          - ``profiles_1d(itime)/time``: refers to the ``time`` quantity in the
            ``profiles_1d`` IDSStructArray with (dummy) index itime

        - Coordinates specify alternatives:

          - ``distribution(i1)/profiles_2d(itime)/grid/r OR
            distribution(i1)/profiles_2d(itime)/grid/rho_tor_norm``: coordinate can
            be ``r`` or ``rho_tor_norm`` (only one may be filled)
          - ``coherent_wave(i1)/beam_tracing(itime)/beam(i2)/length OR 1...1``: either
            use ``length`` as coordinate, or this dimension must have size one.
    """

    _cache: Dict[str, "IDSCoordinate"] = {}

    def __new__(cls, coordinate_spec: str) -> "IDSCoordinate":
        if coordinate_spec not in cls._cache:
            cls._cache[coordinate_spec] = super().__new__(cls)
        return cls._cache[coordinate_spec]

    def __init__(self, coordinate_spec: str) -> None:
        if hasattr(self, "_init_done"):
            return  # Already initialized, __new__ returned from cache
        self._coordinate_spec = coordinate_spec
        self.size: Optional[int] = None
        """Exact size of this dimension, e.g. 2 when coordinate = 1...2."""

        refs: List[IDSPath] = []
        specs = coordinate_spec.split(" OR ")
        for spec in specs:
            if spec.startswith("1..."):
                if spec != "1...N":
                    try:
                        self.size = int(spec[4:])
                    except ValueError:
                        logger.debug(
                            f"Ignoring invalid coordinate specifier {spec}",
                            exc_info=True,
                        )
            elif spec:
                try:
                    refs.append(IDSPath(spec))
                except ValueError:
                    logger.debug(
                        f"Ignoring invalid coordinate specifier {spec}", exc_info=True
                    )
        self.references = tuple(refs)
        """A tuple of :class:`~imaspy.ids_path.IDSPath` that this coordinate refers to.
        """

        num_rules = len(self.references) + (self.size is not None)
        self.has_validation = num_rules > 0
        """True iff this coordinate specifies a validation rule."""
        self.has_alternatives = num_rules > 1
        """True iff exclusive alternative coordinates are specified."""
        self.is_time_coordinate = any(ref.is_time_path for ref in self.references)
        """True iff this coordinate refers to ``time``."""

        # Prevent accidentally modifying attributes
        self._init_done = True

    def __setattr__(self, name: str, value: Any):
        if hasattr(self, "_init_done"):
            raise RuntimeError("Cannot set attribute: IDSCoordinate is read-only.")
        super().__setattr__(name, value)

    def __str__(self) -> str:
        return self._coordinate_spec

    def __repr__(self) -> str:
        return f"IDSCoordinate({self._coordinate_spec!r})"

    def __hash__(self) -> int:
        """IDSCoordinate objects are immutable, we can be used e.g. as dict key."""
        return hash(self._coordinate_spec)


def _goto(path: IDSPath, element: "IDSMixin") -> "IDSPrimitive":
    """Wrapper around IDSPath.goto to raise more meaningful errors."""
    try:
        return path.goto(element)
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(
            f"The data dictionary coordinate definition '{path}' cannot be found: {exc}"
        ) from None


class IDSCoordinates:
    """Class representing coordinates of an IDSMixin.

    Can be used to automatically retrieve coordinate values via the indexing operator.

    Example:
        >>> import imaspy
        >>> core_profiles = imaspy.IDSFactory().core_profiles()
        >>> core_profiles.ids_properties.homogeneous_time = \\
        ...     imaspy.ids_defs.IDS_TIME_MODE_HOMOGENEOUS
        >>> core_profiles.profiles_1d.coordinates[0]
        IDSNumericArray("/core_profiles/time", array([], dtype=float64))
    """

    def __init__(self, mixin: "IDSMixin") -> None:
        self._mixin = mixin

    def __repr__(self) -> str:
        mixin_path = self._mixin._path
        coordinates = []
        for i in range(len(self)):
            coor_str = f"\n  {i}: '{self._mixin.metadata.coordinates[i]}'"
            same_as = self._mixin.metadata.coordinates_same_as[i]
            if same_as.references:
                coor_str += f" (same as '{same_as}')"
            coordinates.append(coor_str)
        return f"<IDSCoordinates of '{mixin_path}'>{''.join(coordinates)}"

    def __len__(self) -> int:
        """Number of coordinates is equal to the dimension of the bound IDSMixin."""
        return self._mixin.metadata.ndim

    def __getitem__(self, key: int) -> Union["IDSPrimitive", np.ndarray]:
        """Get the coordinate of the given dimension.

        When the coordinate is an index (e.g. 1...N) this will return a numpy arange
        with the same size as the data currently has in that dimension.

        When one coordinate path is defined in the DD, the corresponding IDSPrimitive
        object is returned.

        When multiple coordinate paths are defined, the one that is set is returned. A
        ValueError is raised when multiple or none are defined.
        """
        coordinate = self._mixin.metadata.coordinates[key]
        if not coordinate.references:
            return np.arange(self._mixin.shape[key])
        coordinate_path: Optional[IDSPath] = None
        # Time is a special coordinate:
        if coordinate.is_time_coordinate:
            time_mode = self._mixin._time_mode
            if time_mode == HOMOGENEOUS_TIME:
                coordinate_path = IDSPath("time")
            elif time_mode == HETEROGENEOUS_TIME:
                # Time coordinates are guaranteed to be unique (no alternatives)
                coordinate_path = coordinate.references[0]
            else:
                raise ValueError(
                    "Invalid IDS time mode: ids_properties/homogeneous_time is "
                    f"{time_mode}, was expecting {HETEROGENEOUS_TIME} or "
                    f"{HOMOGENEOUS_TIME}."
                )
        elif not coordinate.has_alternatives:
            coordinate_path = coordinate.references[0]

        # Check if the coordinate is inside the AoS
        if coordinate_path is not None:
            if self._mixin.metadata.data_type is IDSDataType.STRUCT_ARRAY:
                if self._mixin.metadata.path.is_ancestor_of(coordinate_path):
                    # Create a numpy array with the contents of all elements in the AoS
                    # TODO: move this to IDSPath?
                    data = [_goto(coordinate_path, ele).value for ele in self._mixin]
                    return np.array(data)
            coordinate_node = _goto(coordinate_path, self._mixin)
            if not coordinate_node.metadata.alternative_coordinate1:
                return coordinate_node

            # This coordinate has alternatives, check which are set
            nonzero_alternatives = [coordinate_node] if len(coordinate_node) > 0 else []
            for alternative_path in coordinate_node.metadata.alternative_coordinate1:
                alternative_node = alternative_path.goto(coordinate_node)
                if len(alternative_node) > 0:
                    nonzero_alternatives.append(alternative_node)
            if not nonzero_alternatives:
                # None of the coordinates are set, return the primary coordinate
                return coordinate_node
            # Check if the lengths of all nonzero alternatives agree
            if len(set(map(len, nonzero_alternatives))) != 1:
                sizes = "\n".join(
                    f"    `{alt.metadata.path_doc}` has size {len(alt)}"
                    for alt in nonzero_alternatives
                )
                raise CoordinateLookupError(
                    f"Dimension {key} of element `{self._mixin.metadata.path_doc}` has "
                    "multiple alternative coordinates set, but they don't have "
                    f"matching sizes:\n{sizes}"
                )
            if len(nonzero_alternatives) > 1:
                logger.info("Multiple alternative coordinates are set, using the first")
            return nonzero_alternatives[0]

        # Handle alternative coordinates, currently (DD 3.38.1) the `coordinate in
        # structure` logic is not applicable for these cases:
        refs = [_goto(ref, self._mixin) for ref in coordinate.references]
        ref_is_defined = [len(ref.value) > 0 for ref in refs]
        if sum(ref_is_defined) == 0:
            if coordinate.size is not None:
                # alternatively we can be an index
                return np.arange(self._mixin.shape[key])
            raise CoordinateLookupError(
                f"Dimension {key} of element `{self._mixin.metadata.path_doc}` must "
                f"have exactly one of its coordinates ({coordinate.references}) set, "
                "but none are set."
            )
        if sum(ref_is_defined) == 1:
            for i in range(len(refs)):
                if ref_is_defined[i]:
                    return refs[i]
        raise CoordinateLookupError(
            f"Dimension {key} of element `{self._mixin.metadata.path_doc}` must have "
            f"exactly one of its coordinates ({coordinate.references}) set, but "
            "multiple are set."
        )

    @property
    def time_index(self) -> Optional[int]:
        """Get the index of the time coordinate

        Returns:
            The index of the time coordinate, or None if there is no time coordinate.
        """
        for i, coor in enumerate(self._mixin.metadata.coordinates):
            if coor.is_time_coordinate:
                return i
        return None

    def _validate(self, aos_indices: Dict[str, int]):
        """Coordinate validation checks.

        See also:
            :py:meth:`imaspy.ids_toplevel.IDSToplevel.validate`.
        """
        shape = self._mixin.shape
        metadata = self._mixin.metadata
        path = metadata.path_doc

        # Validate coordinate
        for dim in range(metadata.ndim):
            coordinate = metadata.coordinates[dim]
            if not coordinate.has_validation:
                continue  # Nothing to validate

            # Validate size
            if coordinate.size:
                if shape[dim] == coordinate.size:
                    continue  # Correct size
                elif not coordinate.has_alternatives:
                    # If the coordinate has alternatives (see test case
                    # test_validate_reference_or_fixed_size) we continue checking the
                    # references below.
                    # If only size is specified, the dimension is not the correct size:
                    raise CoordinateError(
                        path, dim, shape[dim], coordinate.size, None, aos_indices
                    )

            # Validate references
            assert coordinate.references
            with self._capture_goto_errors(dim, coordinate, aos_indices) as captured:
                other_element = self[dim]
            if captured:
                continue  # Ignored error, continue to next dimension

            if isinstance(other_element, np.ndarray):
                if coordinate.size:
                    # other_element may be a numpy array when coordinate = "path OR
                    # 1...1" and path is unset
                    raise CoordinateError(
                        path, dim, shape[dim], coordinate.size, None, aos_indices
                    )
                # Otherwise, this is a dynamic AoS with heterogeneous_time, verify that
                # none of the values are EMPTY_FLOAT
                if EMPTY_FLOAT in other_element:
                    (n,) = np.where(other_element == EMPTY_FLOAT)
                    raise ValidationError(
                        f"Coordinate `{path}[{n[0]}]/time` is empty.", aos_indices
                    )

            with self._capture_goto_errors(dim, coordinate, aos_indices) as captured:
                # other_element may (incorrectly) be a struct in older DD versions
                expected_size = other_element.shape[0]
            if captured:
                continue  # Ignored error, continue to next dimension
            if shape[dim] != expected_size:
                other_path = other_element.metadata.path_doc
                raise CoordinateError(
                    path, dim, shape[dim], expected_size, other_path, aos_indices
                )

        # Validate coordinate_same_as
        for dim in range(metadata.ndim):
            same_as = metadata.coordinates_same_as[dim]
            if not same_as.has_validation:
                continue  # Nothing to validate

            assert len(same_as.references) == 1
            with self._capture_goto_errors(dim, coordinate, aos_indices) as captured:
                other_element = same_as.references[0].goto(self._mixin)
            if captured:
                continue  # Ignored error, continue to next dimension

            expected_size = other_element.shape[dim]
            if shape[dim] != expected_size:
                other_path = other_element.metadata.path_doc
                raise CoordinateError(
                    path, dim, shape[dim], expected_size, other_path, aos_indices
                )

    @contextmanager
    def _capture_goto_errors(self, dim, coordinate, aos_indices):
        """Helper method for _validate to capture errors encountered during
        IDSPath.goto().
        """
        did_capture = []
        path = self._mixin.metadata.path_doc
        try:
            yield did_capture
        except CoordinateLookupError as exc:
            raise ValidationError(exc.args[0], aos_indices)
        except IndexError as exc:
            # Can happen in IDSPath.goto when an invalid index is encountered.
            raise ValidationError(
                f"Dimension {dim} of element `{path}` has an invalid index "
                f"provided for coordinate `{coordinate.references}`.",
                aos_indices,
            ) from exc
        except Exception as exc:
            # Ignore all other exceptions and log them
            if "Unexpected index" in str(exc):
                logger.debug(
                    "Ignored AoS coordinate outside our tree (see IMAS-4675) of "
                    "element `%s`, dimension %s, coordinate `%s`",
                    path,
                    dim,
                    coordinate.references,
                )
            else:
                if self._mixin._version <= "3.38.1":
                    version_error = (
                        "This is expected to happen in DD versions <= 3.38.1, where "
                        "some coordinate metadata is incorrect."
                    )
                else:
                    version_error = "Please report this issue to the IMASPy developers."
                logger.warning(
                    "An error occurred while finding coordinate `%s` of dimension %s, "
                    "which is ignored. %s",
                    coordinate.references,
                    dim,
                    version_error,
                    exc_info=1,
                )
            # Flag to the caller that an error was suppressed
            did_capture.append(1)
