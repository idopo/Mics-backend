"""Ten-line MICS-Link sender. Docstrings and comments do not count.

This is ADDITIVE: three real lines dropped into a loop you already have.
`my_existing_loop()` below is a PLACEHOLDER -- swap it for whatever already produces
your values (a camera read, a model inference step, a sensor poll). `mics_link` does
not know or does not care what it is; that is the point.
"""
from mics_link import connect

# my_existing_loop() is a stand-in for your own acquisition loop -- not part of mics_link.
with connect("132.77.72.28", 5599, "demo") as link:
    for x in my_existing_loop():
        link.send_signal("left_paw_x", x)
