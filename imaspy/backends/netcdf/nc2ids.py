from typing import Iterator, List, Tuple

import netCDF4

from imaspy.backends.netcdf.nc_metadata import NCMetadata
from imaspy.ids_base import IDSBase
from imaspy.ids_data_type import IDSDataType
from imaspy.ids_defs import IDS_TIME_MODE_HOMOGENEOUS
from imaspy.ids_metadata import IDSMetadata
from imaspy.ids_structure import IDSStructure
from imaspy.ids_toplevel import IDSToplevel


def split_on_aos(metadata: IDSMetadata):
    paths = []
    curpath = metadata.name

    item = metadata
    while item._parent.data_type is not None:
        item = item._parent
        if item.data_type is IDSDataType.STRUCT_ARRAY:
            paths.append(curpath)
            curpath = item.name
        else:
            curpath = f"{item.name}/{curpath}"
    paths.append(curpath)
    return paths[::-1]


IndexedNode = Tuple[Tuple[int, ...], IDSBase]


def tree_iter(structure: IDSStructure, metadata: IDSMetadata) -> Iterator[IndexedNode]:
    paths = split_on_aos(metadata)
    if len(paths) == 1:
        yield (), structure[paths[0]]
    else:
        yield from _tree_iter(structure, paths, ())


def _tree_iter(
    structure: IDSStructure, paths: List[str], curindex: Tuple[int, ...]
) -> Iterator[IndexedNode]:
    aos_path, *paths = paths
    aos = structure[aos_path]

    if len(paths) == 1:
        path = paths[0]
        for i, node in enumerate(aos):
            yield curindex + (i,), node[path]

    else:
        for i, node in enumerate(aos):
            yield from _tree_iter(node, paths, curindex + (i,))


def nc2ids(group: netCDF4.Group, ids: IDSToplevel):
    """Get data from the netCDF group and store it in the provided IDS."""
    try:
        _nc2ids(group, ids)
    except Exception as exc:
        raise RuntimeError(
            "An error occurred while reading data from the netCDF file "
            f"'{group.filepath()}'. The netCDF functionality is currently in "
            "preview status. Unexpected data in an otherwise valid netCDF file "
            "may cause errors in IMASPy. A more robust mechanism to load IDS data from "
            "netCDF files will be included in the next release of IMASPy."
        ) from exc


def _nc2ids(group: netCDF4.Group, ids: IDSToplevel):
    var_names = list(group.variables)
    # FIXME: ensure that var_names are sorted properly
    # Current assumption is that creation-order is fine
    homogeneous_time = (
        group["ids_properties.homogeneous_time"][()] == IDS_TIME_MODE_HOMOGENEOUS
    )
    ncmeta = NCMetadata(ids.metadata)

    # Never return masked arrays, they're slow and we'll handle most of the unset values
    # through the `:shape` arrays
    group.set_auto_mask(False)

    for var_name in var_names:
        if var_name.endswith(":shape"):
            continue  # TODO: validate that this is used

        # FIXME: error handling:
        metadata = ids.metadata[var_name]

        # TODO: validate metadata (data type, units, etc.) conforms to DD

        if metadata.data_type is IDSDataType.STRUCTURE:
            continue  # This only contains DD metadata we already know

        var = group[var_name]
        if metadata.data_type is IDSDataType.STRUCT_ARRAY:
            if "sparse" in var.ncattrs():
                shapes = group[var_name + ":shape"][()]
                for index, node in tree_iter(ids, metadata):
                    node.resize(shapes[index][0])

            else:
                # FIXME: extract dimension name from nc file?
                dim = ncmeta.get_dimensions(metadata.path_string, homogeneous_time)[-1]
                size = group.dimensions[dim].size
                for _, node in tree_iter(ids, metadata):
                    node.resize(size)

            continue

        # FIXME: this may be a gigantic array, not required for sparse data
        var = group[var_name]
        data = var[()]

        if "sparse" in var.ncattrs():
            if metadata.ndim:
                shapes = group[var_name + ":shape"][()]
                for index, node in tree_iter(ids, metadata):
                    shape = shapes[index]
                    if shape.all():
                        node.value = data[index + tuple(map(slice, shapes[index]))]
            else:
                for index, node in tree_iter(ids, metadata):
                    value = data[index]
                    if value != getattr(var, "_FillValue", None):
                        node.value = data[index]

        elif metadata.path_string not in ncmeta.aos:
            # Shortcut for assigning untensorized data
            ids[metadata.path] = data

        else:
            for index, node in tree_iter(ids, metadata):
                node.value = data[index]
