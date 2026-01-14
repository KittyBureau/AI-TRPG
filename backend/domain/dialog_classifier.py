from __future__ import annotations

from typing import Tuple

from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE


class DialogTypeClassifier:
    def __init__(self, default_type: str = DEFAULT_DIALOG_TYPE) -> None:
        self.default_type = default_type

    def classify(self, text: str, auto_type_enabled: bool = True) -> Tuple[str, str]:
        return self.default_type, "fallback"
