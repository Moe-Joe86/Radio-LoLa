"""Stand-in for the Reachy Mini SDK: the tests run without a robot and without the reachy-mini package."""

import sys
import threading
import types


class _ReachyMiniApp:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.settings_app = None

    def stop(self) -> None:
        self.stop_event.set()


_stand_in = types.ModuleType("reachy_mini")
_stand_in.ReachyMini = object
_stand_in.ReachyMiniApp = _ReachyMiniApp
sys.modules["reachy_mini"] = _stand_in
