"""mics-link — a socket-free-to-import client SDK for streaming signals and events from a
researcher's own process (e.g. a DeepLabCut-Live inference loop) to a MICS pilot over ZMQ.

The public API (`connect`, `MicsLink`, ...) is assembled in plan 34-06; this file stays
minimal until then so plans 34-02/03/04 can each own a separate module without touching a
shared file.
"""

__version__ = "0.1.0"
