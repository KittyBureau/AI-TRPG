from __future__ import annotations

from typing import List

from pydantic import BaseModel


class DialogRule(BaseModel):
    dialog_type: str
    patterns: List[str]


DEFAULT_DIALOG_TYPE = "scene_description"

DEFAULT_RULES: List[DialogRule] = [
    DialogRule(
        dialog_type="rule_explanation",
        patterns=[
            r"rule",
            r"rules",
            r"mechanic",
            r"mechanics",
            r"how does",
            r"explain",
            r"clarify",
        ],
    ),
    DialogRule(
        dialog_type="resolution_summary",
        patterns=[r"summary", r"summarize", r"recap", r"result", r"outcome", r"so far"],
    ),
    DialogRule(
        dialog_type="action_prompt",
        patterns=[
            r"attack",
            r"move",
            r"go",
            r"open",
            r"search",
            r"look",
            r"talk",
            r"use",
            r"cast",
            r"run",
            r"enter",
            r"leave",
            r"take",
            r"pick",
            r"sneak",
            r"\?",
        ],
    ),
]
