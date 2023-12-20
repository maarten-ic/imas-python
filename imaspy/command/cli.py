# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
""" Main CLI entry point """

import logging
import sys
from pathlib import Path

import click
import rich
from packaging.version import Version
from rich.progress import track
from rich.logging import RichHandler

import imaspy
import imaspy.imas_interface
from imaspy import dd_zip


def setup_rich_log_handler():
    # Disable default imaspy log handler
    imaspy_logger = logging.getLogger("imaspy")
    for handler in imaspy_logger.handlers:
        imaspy_logger.removeHandler(handler)
    imaspy_logger.addHandler(RichHandler())


@click.group("imaspy")
def cli():
    pass


def min_version_guard(al_version: Version):
    """Print an error message if the loaded AL version is too old."""
    used_version = imaspy.imas_interface.ll_interface._al_version
    if used_version >= al_version:
        return
    click.echo(
        f"This command requires at least version {al_version} of the Access Layer."
    )
    click.echo(f"The current loaded version is {used_version}, which is too old.")
    sys.exit(1)


@cli.command("version")
def print_version():
    """Print the version number of IMASPy."""
    click.echo(imaspy.__version__)


@cli.command("print")
@click.argument("uri")
@click.argument("ids")
@click.argument("occurrence", default=0)
@click.option(
    "--all",
    "-a",
    "print_all",
    is_flag=True,
    help="Also show nodes with empty/default values",
)
def print_ids(uri, ids, occurrence, print_all):
    """Pretty print the contents of an IDS.

    \b
    uri         URI of the Data Entry (e.g. "imas:mdsplus?path=testdb")
    ids         Name of the IDS to print (e.g. "core_profiles")
    occurrence  Which occurrence to print (defaults to 0)
    """
    min_version_guard(Version("5.0"))
    setup_rich_log_handler()

    dbentry = imaspy.DBEntry(uri, "r")
    ids_obj = dbentry.get(ids, occurrence, autoconvert=False)
    imaspy.util.print_tree(ids_obj, not print_all)


@cli.command("convert")
@click.argument("uri_in")
@click.argument("dd_version")
@click.argument("uri_out")
@click.option("--ids", default="*", help="Specify which IDS to convert")
@click.option("--occurrence", default=-1, help="Specify which occurrence to convert")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output")
def convert_ids(uri_in, dd_version, uri_out, ids, occurrence, quiet):
    """Convert an IDS to the target DD version.

    \b
    uri_in      URI of the input Data Entry
    dd_version  Data dictionary version to convert to. Can also be the path to an
                IDSDef.xml to convert to custom/unreleased DD versions.
    uri_out     URI of the output Data Entry
    """
    min_version_guard(Version("5.1"))
    setup_rich_log_handler()

    # Check if we can load the requested version
    if dd_version in dd_zip.dd_xml_versions():
        version_params = dict(dd_version=dd_version)
    elif Path(dd_version).exists():
        version_params = dict(xml_path=dd_version)
    else:
        dd_zip.raise_unknown_dd_version_error(dd_version)

    entry_in = imaspy.DBEntry(uri_in, "r")
    # Set dd_version/xml_path, so the IDSs are converted to this version during put()
    # Use "x" to prevent accidentally overwriting existing Data Entries
    entry_out = imaspy.DBEntry(uri_out, "x", **version_params)

    # First build IDS/occurrence list so we can show a decent progress bar
    ids_list = [ids] if ids != "*" else entry_out.factory.ids_names()
    idss_with_occurrences = []
    for ids_name in ids_list:
        if occurrence == -1:
            idss_with_occurrences.extend(
                (ids_name, occ) for occ in entry_in.list_all_occurrences(ids_name)
            )
        else:
            idss_with_occurrences.append((ids_name, occurrence))

    # Show progress bar?
    if quiet:
        iterator = idss_with_occurrences
    else:
        iterator = track(idss_with_occurrences)

    # Convert all IDSs
    for ids_name, occurrence in iterator:
        rich.print(f"Converting {ids_name}/{occurrence}...")
        ids = entry_in.get(ids_name, occurrence, autoconvert=False)
        # Explicitly convert instead of auto-converting during put. This is a bit
        # slower, but gives better diagnostics:
        ids2 = imaspy.convert_ids(ids, None, factory=entry_out.factory)
        # Store in output entry:
        entry_out.put(ids2, occurrence)


if __name__ == "__main__":
    cli()
