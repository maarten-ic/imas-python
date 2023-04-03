# IMASPy
IMASPy is a pure-python library to handle arbitrarily nested data structures.
IMASPy is designed for, but not necessarily bound to, interacting with
Interface Data Structures (IDSs) as defined by the
Integrated Modelling & Analysis Suite (IMAS) Data Model.

It provides:

* An easy-to-install and easy-to-get started package by
  * Not requiring an IMAS installation
  * Not strictly requiring matching a Data Dictionary (DD) version
* An pythonic alternative to the IMAS Python High Level Interface (HLI)
* Checking of correctness on assign time, instead of database write time
* Dynamically created in-memory pre-filled data trees from DD XML specifications

This package is developed on [ITER bitbucket](https://git.iter.org/projects/IMAS/repos/imaspy).
For user support, contact the IMAS team on the [IMAS user slack](https://imasusers.slack.com),
open a [JIRA issue](https://jira.iter.org/projects/IMAS), or email the
support team on imas-support@iter.org.

## Installation
### On ITER system, EuroFusion gateway
There is a `module` available on ITER and the Gateway, so you can run
```bash
module load IMASPy
```
Additionally, if you wish to use the MDSPlus backend, you should load
```bash
module load MDSplus-Java/7.96.17-GCCcore-10.2.0-Java-11
```
at least the first time you are using the backend with a new data-dictionary version.

### Local
We recommend using a `venv`:
```bash
python3 -m venv ./venv
. venv/bin/activate
```

Then clone this repository, and run `pip install`:
```bash
git clone ssh://git@git.iter.org/imas/imaspy.git
cd imaspy
pip install .
```
If you get strange errors you might want to upgrade your `setuptools` and `pip`.
(you might want to add the `--user` flag to your pip installs when not in a `venv`)

### Development installation
For development an installation in editable mode may be more convenient, and
you will need some extra dependencies to run the test suite and build documentation.
```bash
pip install -e .[test,docs]
```

Test your installation by trying
```
cd ~
python -c "import imaspy; print(imaspy.__version__)"
```
which should return your just installed version number.

### Installation without ITER access
The installation script tries to access the [ITER IMAS Core Data Dictionary repository](https://git.iter.org/projects/IMAS/repos/data-dictionary/browse)
to fetch the latest versions. If you do not have git+ssh access there, you can
try to find this repository elsewhere, and do a `git fetch --tags`.

Alternatively you could try to obtain an `IDSDef.zip` and place it in `~/.config/imaspy/`.

## How to use
```python
import imaspy
root = imaspy.IDSRoot(shot=1, run=0)
print(root.equilibrium)

root.equilibrium.ids_properties.comment = "testing"

root.open_ual_store(user="daan", tokamak="ITER", version="3", backend_type=imaspy.ids_defs.HDF5_BACKEND, mode="w")
root.equilibrium.put()

# TODO: find an example with a significant change between versions (rename?)
older_root = imaspy.IDSRoot(shot=1, run=0, version="3.35.0")
# backend_version is autodetected
older_root.open_ual_store(user="daan", tokamak="ITER", version="3", backend_type=imaspy.ids_defs.HDF5_BACKEND, mode="r")
older_root.equilibrium.get()
print(older_root.equilibrium.ids_properties.comment)
```

## Documentation
Documentation is autogenerated from the source using [Sphinx](http://sphinx-doc.org/)
and can be found at the [ITER sharepoint](https://sharepoint.iter.org/departments/POP/CM/IMDesign/Code%20Documentation/IMASPy-doc/html/index.html)

The documentation can be manually generated by installing sphinx and running:

```bash
make -C docs html
```

## Interacting with IMAS AL
Interaction with the IMAS AL is provided by a Cython interface to the Access Layer.
As Cython code, it needs to be compiled on your local system.
To find the headers, the Access Layer `include` folder needs to be in your `INCLUDE_PATH`. On most HPC systems, a `module load IMAS` is enough.

## Where does IMASPy live in IMAS ecosystem?
IMASPy tries to fill a slightly different niche than existing tools. It aims
to be an _alternative_ to Python HLI instead of a wrapper. It tries to be
dynamic instead of pre-generated. Is hopes to be extendable instead of
wrappable.

A small, biased, and wildly incomplete of some common IMAS tools, and
where they live with respect to IMASPy.

``` mermaid
classDiagram
  MDSPLUS_DATABASE .. LL_AL : puts
  MDSPLUS_DATABASE .. LL_AL : gets
  MDSPLUS_DATABASE .. LL_HDC : puts
  MDSPLUS_DATABASE .. LL_HDC : gets
  IMAS DD <.. PythonHLI: build dep
  IMAS DD <-- IMASPy:  runtime dep
  LL_HDC <-- HDC_python_bindings : calls
  LL_AL <-- Cython_HLI : calls
  Python_helpers <-- IMASPy: calls
  HDC_python_bindings <.. IMASPy: Could call

  Cython_HLI <-- Python_helpers : calls
  Python_helpers <-- Python HLI: calls

  IMASDD <..  IMASviz_codegen: build dep
  IMASviz_codegen <..  IMASviz: build dep

  PythonHLI <-- OMAS: calls
  OMAS <-- OMFIT: calls
  OMFIT <-- IMASgo : calls

  PythonHLI <-- pyAL: calls
  PythonHLI <-- JINTRAC_WORKFLOWS : calls
  pyAL <-- HnCD_WORKFLOWS : calls
  PythonHLI <-- HnCD_WORKFLOWS : calls
  PythonHLI <-- IMASviz: calls
```

## Contributing
IMASPy is open for contributions! Please open a
[fork](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#creating-a-fork)
and create a
[merge request](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#merging-upstream)
or request developer access from one of the maintainers.

## Acknowledgments
Inspired and bootstrapped by existing tools, notably the IMAS Python HLI,
IMAS Python workflows, and OMAS.
