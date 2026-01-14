from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.domain.dialog_rules import DEFAULT_DIALOG_TYPE, DEFAULT_RULES, DialogRule


class DialogTypeClassifier:
    def __init__(
        self,
        rules: Optional[List[DialogRule]] = None,
        default_type: str = DEFAULT_DIALOG_TYPE,
    ) -> None:
        self.default_type = default_type
        self.rules = rules or DEFAULT_RULES
        self._compiled = [
            (rule.dialog_type, re.compile("|".join(rule.patterns), re.IGNORECASE))
            for rule in self.rules
        ]

    def classify(self, text: str, auto_type_enabled: bool = True) -> Tuple[str, str]:
        if not auto_type_enabled:
            return self.default_type, "fixed"

        normalized = text.strip()
        if not normalized:
            return self.default_type, "auto"

        for dialog_type, pattern in self._compiled:
            if pattern.search(normalized):
                return dialog_type, "auto"

        return self.default_type, "auto"
