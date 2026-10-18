"""Attrappe für das Reachy-Mini-SDK: Die Tests laufen ohne Roboter und ohne das Paket reachy-mini."""

import sys
import threading
import types


class _ReachyMiniApp:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.settings_app = None

    def stop(self) -> None:
        self.stop_event.set()


_attrappe = types.ModuleType("reachy_mini")
_attrappe.ReachyMini = object
_attrappe.ReachyMiniApp = _ReachyMiniApp
sys.modules["reachy_mini"] = _attrappe
