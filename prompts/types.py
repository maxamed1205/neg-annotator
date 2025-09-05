from __future__ import annotations
from typing import TypedDict, Optional, Dict, Any


class Token(TypedDict):
    text: str
    start: int
    end: int


class Cue(TypedDict, total=False):
    id: str
    cue_label: str
    start: int
    end: int
    group: str
    role: str


class Rule(TypedDict, total=False):
    id: str
    group: str
    when_pattern: str
    when_marker: str
    options: Dict[str, Any]
    negative_guards: Any
    _compiled: Any
    _guards: Any


class Strategy(TypedDict, total=False):
    id: str
    scope_strategy: str
    options: Dict[str, Any]
    guards: Any


__all__ = ["Token", "Cue", "Rule", "Strategy"]
