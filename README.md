# PyMAS

PyMAS is (yet another) pure-python library to handle arbitrarily nested
data structures. PyMAS is designed for, but not necessarily bound to,
interacting with Interface Data Structures (IDSs) as defined by the
Integrated Modelling & Analysis Suite (IMAS) Data Model.

It provides:
- An easy-to-install and easy-to-get started package by
  * Not requiring a IMAS installation
  * Not strictly requiring matching a Data Dictionary (DD) version
- An pythononic alternative to the IMAS Python High Level Interface (HLI)
- Checking of correctness on assign time, instead of database write time
- Dynamically created in-memory pre-filled data trees from DD XML specifications

## A word of caution
This package is currently community supported, and in very early alpha. As such
many features that one expects from the Python HLI are not implemented yet, or
are untested and buggy. If you are interested in this development, please drop
the main author an email at karelvandeplassche@gmail.com.

## Getting Started

Clone the repository on your local machine. To set up SSH keys for
GitLab, look here: https://docs.gitlab.com/ee/ssh/
``` bash
git clone git@gitlab.com:Karel-van-de-Plassche/pymas.git # Using SSH keys
git clone https://gitlab.com/Karel-van-de-Plassche/pymas.git # Using username/password
```

Install PyMAS in developer mode with all the optional components it can find:
```bash
cd pymas
pip install --user -e .[all]
```

For now, let's assume you have a Data Dictionary specification available,
and managed to compile the AL.
``` python
# Initialize an empty IDS
import pymas as imas
idsdef_dir = <path to IDSDef.xml>
idsdef = os.path.join(idsdef_dir, 'IDSDef.xml')
shot = 1234
run_in = 0
imas_entry = imas.ids(shot, run_in, xml_path=idsdef, verbosity=2)
```

We end up with a `IDSRoot` instance that is pre-filled with all defaults and
data structures defined in the given DD XML. We could've not given `xml_path`
to create an empty `IDSRoot`. No interaction with any LL-AL has happened yet!

Create a PulseFile. This creates an empty PulseFile with the specified backend.
This _will_ overwrite pulsefiles with the same path. This does need an access
layer, PyMAS does not provide one out of the box currently.
``` python
from imas_entry._libs.imasdef import *
input_user_or_path = <path to pulsefiles, for example your username>
input_database = <database, for example 'iter' >
imas_entry.create_env_backend(input_user_or_path, input_database, '3', MDSPLUS_BACKEND)
```

Now that the pulse file exists, put some data in our Python structure:
``` python
ids = imas_entry.equilibrium
ids.ids_properties.homogeneous_time = 'special' #Whoops! This crashes, wrong type!
ids.ids_properties.homogeneous_time = IDS_TIME_MODE_HETEROGENEOUS # This field needs to be filled for all valid IDSs
ids.time = [0.1, 0.2, 0.3]
ids.time += 2 # Let's offset this by 2
```

No database interaction has happened yet. We need to explicitly send it to the
MDSPLUS pulsefile:
``` python
ids.put() # This removes the pulsefile, and rebuilds it with our in-memory structure!
```

And now we can interact with the regular IMAS tools, for example to plot the
structures with IMASViz.


### Prerequisites

PyMAS is a standalone python package with optional dependencies. All needed
python packages can be found in `requirements.txt`, and should all be publicly
available. A simple `pip install` should take care of everything.

#### Being IMAS DD compatible

To check IMAS DD compatible, one needs the IDS definition XML file. This file
can usually be found at `$IMAS_PREFIX/include/IDSDef.xml` on your IMAS-enabled
system. Otherwise, they can be build from source from the
[ITER IMAS Core Data Dictionary repository](https://git.iter.org/projects/IMAS/repos/data-dictionary/browse).

#### Interacting with IMAS AL

Interaction with the IMAS AL is provided by Cython and Python wrappers provided
by the Python High Level Interface. As Cython code, it needs to be compiled on
your local system. First make sure you can access the
[ITER IMAS Access Layer repository](https://git.iter.org/projects/IMAS/repos/access-layer/browse)
using SSH `ssh://git@git.iter.org/imas/access-layer.git`.
A copy of this repository will be cloned into `src` during build.

Get the prerequisites:
``` bash
pip install numpy cython gitpython
```

Install in verbose mode. After installing, you should have a `ual_x_x_x`
directory in your root. If not, something went wrong. Be sure to browse
the verbose log or open a ticket.
``` bash
pip install --user -e .[all] -v
```

## Where does PyMAS live in IMAS ecosystem?
PyMAS tries to fill a slightly different niche than existing tools. It aims
to be an _alternative_ to Python HLI instead of a wrapper. It tries to be
dynamic instead of pre-generated. Is hopes to be extendable instead of
wrappable.

A small, biased, and wildly incomplete of some common IMAS tools, and
where they live with respect to PyMAS.
``` mermaid
classDiagram
  MDSPLUS_DATABASE .. LL_AL : puts
  MDSPLUS_DATABASE .. LL_AL : gets
  MDSPLUS_DATABASE .. LL_HDC : puts
  MDSPLUS_DATABASE .. LL_HDC : gets
  IMAS DD <.. PythonHLI: build dep
  IMAS DD <-- PyMAS:  runtime dep
  LL_HDC <-- HDC_python_bindings : calls
  LL_AL <-- Cython_HLI : calls
  Python_helpers <-- PyMAS: calls
  HDC_python_bindings <.. PyMAS: Could call

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

PyMAS is open for contributions! Please open a
[fork](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#creating-a-fork)
and create a
[merge request](https://docs.gitlab.com/ee/user/project/repository/forking_workflow.html#merging-upstream)
or request developer access to one of the maintainers.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details

## Acknowledgments

Inspired and bootstrapped by existing tools, notably the IMAS Python HLI,
IMAS Python workflows, and OMAS.
