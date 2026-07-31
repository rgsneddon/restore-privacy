"""Restore Privacy — Mac / desktop residual **node operator** app.

Not the end-user VPN Connect client. Local GUI + controller for running this
host as a lab/full residual node and admin controls (client priority, update push).
"""

from __future__ import annotations

__all__ = ["APP_NAME", "APP_TITLE", "main"]

APP_NAME = "rpt-node-operator"
APP_TITLE = "Restore Privacy — Node Operator"


def main(argv: list[str] | None = None) -> int:
    from node_operator.app import main as _main

    return _main(argv)
