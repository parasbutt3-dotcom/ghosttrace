from typing import Type

from app.integrations.base import BaseIntegration

_REGISTRY: dict[str, Type[BaseIntegration]] = {}


def register(kind: str):
    def decorator(cls):
        _REGISTRY[kind] = cls
        return cls
    return decorator


def get_integration_class(kind: str):
    return _REGISTRY.get(kind)


def available_kinds():
    return list(_REGISTRY.keys())
