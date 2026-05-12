import re
from pathlib import Path
from typing import Any

import yaml

from shared.ai_streamer.models import Action, ModerationLabel, ModerationResult


class ModerationService:
    def __init__(self, rules_path: str) -> None:
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict[str, Any]:
        with self.rules_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def normalize_text(self, text: str) -> str:
        normalized = text.strip().lower()
        normalized = normalized.replace("\u200b", "")
        normalized = re.sub(r"(.)\1{3,}", r"\1\1\1", normalized)
        for source, target in self.rules.get("slang_map", {}).items():
            normalized = normalized.replace(source, target)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def classify(self, text: str) -> ModerationResult:
        normalized = self.normalize_text(text)
        labels: list[ModerationLabel] = []
        notes: list[str] = []
        regex_rules = self.rules.get("regex_rules", {})
        lexicon = self.rules.get("lexicon", {})
        severity_map = self.rules.get("severity", {})
        action_map = self.rules.get("actions", {})

        ordered_categories = [
            "doxxing",
            "self-harm",
            "illegal",
            "hate",
            "sexual",
            "harassment",
            "impersonation-bait",
            "parasocial-bait",
            "spam",
        ]

        for category in ordered_categories:
            for pattern in regex_rules.get(category, []):
                if re.search(pattern, normalized):
                    labels.append(ModerationLabel(category))
                    notes.append(f"regex:{category}:{pattern}")
                    break
            if not any(label.value == category for label in labels):
                for token in lexicon.get(category, []):
                    if token in normalized:
                        labels.append(ModerationLabel(category))
                        notes.append(f"lexicon:{category}:{token}")
                        break

        if not labels:
            labels = [ModerationLabel.safe]

        severity = max(severity_map.get(label.value, 0) for label in labels)
        dominant_label = max(labels, key=lambda item: severity_map.get(item.value, 0))
        action = Action(action_map.get(dominant_label.value, "allow"))
        return ModerationResult(
            normalized_text=normalized,
            labels=labels,
            severity=severity,
            action=action,
            notes=notes,
        )
