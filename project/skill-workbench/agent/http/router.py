"""Minimal deterministic router with optional {param} segments."""
from __future__ import annotations


class RouteNotFound(Exception):
    pass


class Router:
    def __init__(self) -> None:
        self._routes: list[tuple[str, tuple[str, ...], object]] = []

    def add(self, method: str, path: str, handler) -> None:
        self._routes.append((method.upper(), tuple(part for part in path.split("/") if part), handler))

    def dispatch(self, method: str, path: str):
        parts = tuple(part for part in path.split("/") if part)
        for route_method, route_parts, handler in self._routes:
            if route_method != method.upper() or len(route_parts) != len(parts):
                continue
            params = {}
            matched = True
            for expected, actual in zip(route_parts, parts):
                if expected.startswith("{") and expected.endswith("}"):
                    params[expected[1:-1]] = actual
                elif expected != actual:
                    matched = False
                    break
            if matched:
                return handler, params
        raise RouteNotFound(path)