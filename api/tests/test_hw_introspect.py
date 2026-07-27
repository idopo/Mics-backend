"""AST hardware-capability introspection (Plan 24-08 Task 1).

Synthetic sources modelled on the real gpio.py / i2c.py / timer.py shapes documented in the
plan's <interfaces> block — a class's ancestor chain is never fully closed in one file because
Hardware is always imported, so `closed` must be False whenever an unresolvable base is hit.
"""
from hw_introspect import class_capabilities, resolve_class_methods

GPIO_SRC = '''
from hardware.base import Hardware, Sensor, Effector

class GPIO(Hardware):
    def setup(self):
        pass

class Digital_Out(GPIO, Effector):
    output = True
    is_trigger = True
    type = "DIGITAL_OUT"

    def set(self, value):
        pass

class Digital_In(GPIO, Sensor):
    is_trigger = True
    type = 'DIGI_IN'
    input = True

    def read(self):
        pass

class Solenoid(Digital_Out):
    def open(self):
        pass
'''

I2C_SRC = '''
from hardware.base import Hardware

class MPR121(Hardware):
    def detect_change(self):
        pass

    def read(self):
        pass

class Touch_Detector(MPR121):
    def __init__(self, address=True, num_detectors=1, device_name=None):
        pass
'''

TIMER_SRC = '''
from hardware.base import Hardware

class TIMER(Hardware):
    def start(self):
        pass

    def stop(self):
        pass
'''

CYCLIC_SRC = '''
class A(B):
    pass

class B(A):
    pass
'''


def test_resolve_class_methods_includes_in_file_ancestors_and_reports_open():
    methods, closed = resolve_class_methods(GPIO_SRC, "Solenoid")
    assert {"open", "set", "setup"} <= methods
    assert closed is False  # Hardware is imported, not defined in this file


def test_resolve_class_methods_touch_detector_inherits_mpr121_methods():
    methods, closed = resolve_class_methods(I2C_SRC, "Touch_Detector")
    assert "detect_change" in methods
    assert "read" in methods
    assert closed is False


def test_digital_in_is_trigger_and_input():
    caps = class_capabilities(GPIO_SRC, "Digital_In")
    assert caps["is_trigger"] is True
    assert caps["direction"] == "input"


def test_digital_out_is_trigger_and_output():
    caps = class_capabilities(GPIO_SRC, "Digital_Out")
    assert caps["is_trigger"] is True
    assert caps["direction"] == "output"


def test_solenoid_inherits_is_trigger_and_output_from_digital_out():
    caps = class_capabilities(GPIO_SRC, "Solenoid")
    assert caps["is_trigger"] is True
    assert caps["direction"] == "output"


def test_timer_is_not_a_trigger():
    caps = class_capabilities(TIMER_SRC, "TIMER")
    assert caps["is_trigger"] is False
    assert caps["direction"] is None


def test_touch_detector_is_detector_capability_not_trigger():
    caps = class_capabilities(I2C_SRC, "Touch_Detector")
    assert caps["is_trigger"] is False
    assert caps["is_detector"] is True


def test_cyclic_base_list_terminates():
    methods, closed = resolve_class_methods(CYCLIC_SRC, "A")
    assert isinstance(methods, set)
    assert closed is False


def test_unparseable_source_returns_empty_rather_than_raising():
    assert resolve_class_methods("not valid python (((", "Foo") == (set(), False)
    caps = class_capabilities("not valid python (((", "Foo")
    assert caps == {"is_trigger": False, "direction": None, "is_detector": False, "methods": set(), "closed": False}
