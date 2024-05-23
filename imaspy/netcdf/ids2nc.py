# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
"""NetCDF IO support for IMASPy. Requires [netcdf] extra dependencies.
"""

from typing import Iterator, Tuple

import netCDF4
import numpy

from imaspy.ids_base import IDSBase
from imaspy.ids_data_type import IDSDataType
from imaspy.ids_struct_array import IDSStructArray
from imaspy.ids_structure import IDSStructure
from imaspy.ids_toplevel import IDSToplevel
from imaspy.netcdf.nc_metadata import NCMetadata

default_fillvals = {
    IDSDataType.INT: netCDF4.default_fillvals["i4"],
    IDSDataType.STR: "",
    IDSDataType.FLT: netCDF4.default_fillvals["f8"],
    IDSDataType.CPX: netCDF4.default_fillvals["f8"] * (1 + 1j),
}
dtypes = {
    IDSDataType.INT: numpy.int32,
    IDSDataType.STR: str,
    IDSDataType.FLT: numpy.float64,
    IDSDataType.CPX: numpy.complex128,
}
SHAPE_DTYPE = numpy.int32


def nc_tree_iter(
    node: IDSStructure, aos_index: Tuple[int, ...] = ()
) -> Iterator[Tuple[Tuple[int, ...], IDSBase]]:
    """Tree iterator that tracks indices of all ancestor array of structures.

    Args:
        node: IDS node to iterate over

    Yields:
        (aos_index, node) for all filled leaf nodes and array of structures nodes.
    """
    for child in node.iter_nonempty_():
        yield (aos_index, child)
        if isinstance(child, IDSStructArray):
            for i in range(len(child)):
                yield from nc_tree_iter(child[i], aos_index + (i,))
        elif isinstance(child, IDSStructure):
            yield from nc_tree_iter(child, aos_index)


class IDS2NC:
    """Class responsible for storing an IDS to a NetCDF file."""

    def __init__(self, ids: IDSToplevel, group: netCDF4.Group) -> None:
        self.ids = ids
        """IDS to store."""
        self.group = group
        """NetCDF Group to store the IDS in."""

        self.ncmeta = NCMetadata(ids.metadata)
        """NetCDF related metadata."""
        self.dimension_size = {}
        """Map dimension name to its size."""
        self.filled_data = {}
        """Map of IDS paths to filled data nodes."""
        self.filled_variables = set()
        """Set of filled IDS variables"""
        self.homogeneous_time = ids.ids_properties.homogeneous_time == 1
        """True iff the IDS time mode is homogeneous."""
        self.shapes = {}
        """Map of IDS paths to data shape arrays."""

    def run(self) -> None:
        """Store the IDS in the NetCDF group."""
        self.collect_filled_data()
        self.determine_data_shapes()
        self.create_dimensions()
        self.create_variables()
        # self.group.sync()  # TODO: figure out if needed
        self.store_data()

    def collect_filled_data(self) -> None:
        """Collect all filled data in the IDS and determine dimension sizes.

        Results are stored in :attr:`filled_data` and :attr:`dimension_size`.
        """
        # Initialize dictionary with all paths that could exist in this IDS
        filled_data = {path: {} for path in self.ncmeta.paths}
        dimension_size = {}
        get_dimensions = self.ncmeta.get_dimensions

        for aos_index, node in nc_tree_iter(self.ids):
            path = node.metadata.path_string
            filled_data[path][aos_index] = node
            ndim = node.metadata.ndim
            if not ndim:
                continue
            dimensions = get_dimensions(path, self.homogeneous_time)
            # We're only interested in the non-tensorized dimensions: [-ndim:]
            for dim_name, size in zip(dimensions[-ndim:], node.shape):
                dimension_size[dim_name] = max(dimension_size.get(dim_name, 0), size)

        # Remove paths without data
        self.filled_data = {path: data for path, data in filled_data.items() if data}
        self.filled_variables = {path.replace("/", ".") for path in self.filled_data}
        # Store dimension sizes
        self.dimension_size = dimension_size

    def determine_data_shapes(self) -> None:
        """Determine tensorized data shapes and sparsity, save in :attr:`shapes`."""
        get_dimensions = self.ncmeta.get_dimensions

        for path, nodes_dict in self.filled_data.items():
            metadata = self.ids.metadata[path]
            # Structures don't have a size
            if metadata.data_type is IDSDataType.STRUCTURE:
                continue
            ndim = metadata.ndim
            dimensions = get_dimensions(path, self.homogeneous_time)

            # node shape if it is completely filled
            full_shape = tuple(self.dimension_size[dim] for dim in dimensions[-ndim:])

            if len(dimensions) == ndim:
                # Data at this path is not tensorized
                node = nodes_dict[()]
                sparse = node.shape != full_shape
                if sparse:
                    shapes = numpy.array(node.shape, dtype=SHAPE_DTYPE)

            else:
                # Data is tensorized, determine if it is homogeneously shaped
                aos_dims = get_dimensions(self.ncmeta.aos[path], self.homogeneous_time)
                shapes_shape = [self.dimension_size[dim] for dim in aos_dims]
                if ndim:
                    shapes_shape.append(ndim)
                shapes = numpy.zeros(shapes_shape, dtype=SHAPE_DTYPE)

                if ndim:  # ND types have a shape
                    for aos_coords, node in nodes_dict.items():
                        shapes[aos_coords] = node.shape
                    sparse = not numpy.array_equiv(shapes, full_shape)

                else:  # 0D types don't have a shape
                    for aos_coords in nodes_dict.keys():
                        shapes[aos_coords] = 1
                    sparse = not shapes.all()
                    shapes = None

            if sparse:
                self.shapes[path] = shapes
                if ndim:
                    # Ensure there is a pseudo-dimension f"{ndim}D" for shapes variable
                    self.dimension_size[f"{ndim}D"] = ndim

    def create_dimensions(self) -> None:
        """Create netCDF dimensions."""
        for dimension, size in self.dimension_size.items():
            self.group.createDimension(dimension, size)

    def create_variables(self) -> None:
        """Create netCDF variables."""
        get_dimensions = self.ncmeta.get_dimensions
        for path in self.filled_data:
            metadata = self.ids.metadata[path]
            var_name = path.replace("/", ".")

            if metadata.data_type in (IDSDataType.STRUCTURE, IDSDataType.STRUCT_ARRAY):
                # Create a 0D dummy variable for metadata
                var = self.group.createVariable(var_name, "S1", ())

            else:
                dtype = dtypes[metadata.data_type]
                # Create variable
                var = self.group.createVariable(
                    var_name,
                    dtype,
                    get_dimensions(path, self.homogeneous_time),
                    compression=None if dtype is str else "zlib",
                    complevel=1,
                    fill_value=default_fillvals[metadata.data_type],
                )

            # Fill metadata attributes
            var.documentation = metadata.documentation
            if metadata.units:
                var.units = metadata.units

            if metadata.data_type is not IDSDataType.STRUCT_ARRAY:
                var.coordinates = self.filter_coordinates(path)

            # Sparsity and :shape array
            if path in self.shapes:
                if not metadata.ndim:
                    # Doesn't need a :shape array:
                    var.sparse = "Sparse data, missing data is filled with _FillValue"

                else:
                    shape_name = f"{var_name}:shape"
                    var.sparse = f"Sparse data, data shapes are stored in {shape_name}"

                    # Create variable to store data shape
                    dimensions = get_dimensions(
                        self.ncmeta.aos.get(path), self.homogeneous_time
                    ) + (f"{metadata.ndim}D",)
                    self.group.createVariable(
                        shape_name,
                        SHAPE_DTYPE,
                        dimensions,
                    )

    def filter_coordinates(self, path: str) -> str:
        """Filter the coordinates list from NCMetadata to filled variables only."""
        return " ".join(
            coordinate
            # FIXME: update get_coordinates to return a list of str!
            for coordinate in self.ncmeta.get_coordinates(
                path, self.homogeneous_time
            ).split(" ")
            if coordinate in self.filled_variables
        )

    def store_data(self) -> None:
        """Store data in the netCDF variables"""
        for path, nodes_dict in self.filled_data.items():
            metadata = self.ids.metadata[path]
            var_name = path.replace("/", ".")

            # No data/shapes to store for structures
            if metadata.data_type is IDSDataType.STRUCTURE:
                continue

            shapes = self.shapes.get(path)
            if shapes is not None:
                self.group[f"{var_name}:shape"][()] = shapes

            # No data to store for arrays of structures
            if metadata.data_type is IDSDataType.STRUCT_ARRAY:
                continue

            var = self.group[var_name]
            if var.ndim == metadata.ndim:
                # Not tensorized: directly set value
                node = nodes_dict[()]
                if metadata.data_type is IDSDataType.STR and metadata.ndim == 1:
                    # NetCDF doesn't support setting slices for vlen data types
                    for i in range(len(node)):
                        var[i] = node[i]
                elif shapes is None:
                    # Data is not sparse and we can assign everything
                    var[()] = node.value
                else:
                    # Data is sparse, so we set a slice
                    var[tuple(map(slice, node.shape))] = node.value

            else:
                # Data is tensorized: tensorize in-memory
                var.set_auto_mask(False)
                # TODO: depending on the data, tmp_var may be HUGE, we may need a more
                # efficient assignment algorithm for large and/or irregular data
                tmp_var = var[()]

                # Fill tmp_var
                if shapes is None:
                    # Data is not sparse, so we can assign to the aos_coords
                    for aos_coords, node in nodes_dict.items():
                        tmp_var[aos_coords] = node.value
                else:
                    # Data is sparse, so we must select a slice
                    for aos_coords, node in nodes_dict.items():
                        tmp_var[aos_coords + tuple(map(slice, node.shape))] = node.value

                # Assign data to variable
                var[()] = tmp_var
                del tmp_var
