"""dlc_link — a DeepLabCut adapter and lib-source generator that is an ordinary customer
of the `mics-link` public API, with no privileged hooks.

**Package-wide write discipline (D-44 through D-48).** The user's DLC project directory
is READ-ONLY by explicit user requirement, and their shell prompt sits inside it, so any
cwd-relative default path in this package would land in the project. Therefore, every
module in this package obeys one rule: no module writes any file unless an explicit path
flag says where, no flag that writes has a default, and no module writes to the current
working directory or the system temp root. Importing this package writes nothing.
"""

__version__ = "0.1.0"
