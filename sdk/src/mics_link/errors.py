"""Public exception types for mics-link.

`InvalidValueError` subclasses BOTH `MicsLinkError` and `TypeError` so a researcher's
existing `except TypeError` around their acquisition loop still catches it — additive, not
architectural (34-CONTEXT.md "Guiding principle"), applied to error handling too.
"""


class MicsLinkError(Exception):
    """Base class for every exception `mics_link` raises."""


class InvalidValueError(MicsLinkError, TypeError):
    """Raised at the `send_signal`/`send_event` call site for a value whose exact type is
    not one of the four allowed dtypes (bool, int, float, str). See `mics_link.values`.
    """
