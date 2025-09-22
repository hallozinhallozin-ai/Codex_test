# -*- coding: utf-8 -*-
"""Регистрация встроенных типов устройств."""
from services.device_registry import register_device_type, get_available_types, registry

from .curtain import CurtainController, CurtainControlFrame
from .fan import FanController, FanControlFrame
from .pump import PumpController, PumpControlFrame

register_device_type(
    "curtain",
    controller_cls=CurtainController,
    frame_cls=CurtainControlFrame,
    uri_factory=lambda ip: f"ws://{ip}/ws",
)
register_device_type(
    "fan",
    controller_cls=FanController,
    frame_cls=FanControlFrame,
    uri_factory=lambda ip: f"ws://{ip}:81",
)
register_device_type(
    "pump",
    controller_cls=PumpController,
    frame_cls=PumpControlFrame,
    uri_factory=lambda ip: f"ws://{ip}/ws",
)

__all__ = [
    "register_device_type",
    "get_available_types",
    "registry",
]
