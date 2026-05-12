from pathlib import Path
from typing import Any

import yaml

from shared.ai_streamer.models import PersonaPromptArtifacts, PersonaState, StreamContext


class PersonaEngine:
    def __init__(self, persona_path: str) -> None:
        self.persona_path = Path(persona_path)
        self.persona = self._load_persona()

    def _load_persona(self) -> dict[str, Any]:
        with self.persona_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def build_system_prompt(self, context: StreamContext, state: PersonaState) -> str:
        style = self.persona["tone"]["default"]
        bilingual_policy = self.persona["bilingual_policy"]
        taboo_topics = ", ".join(self.persona["taboo_topics"])
        jokes = ", ".join(self.persona["recurring_jokes"])
        return (
            f"คุณคือ {self.persona['name']} สตรีมเมอร์ AI ไทย\n"
            f"บุคลิก: {style}\n"
            f"อารมณ์ตอนนี้: {state.mood.value}\n"
            f"พลังงาน: {state.energy}/100 ความมั่นใจ: {state.confidence}/100\n"
            f"เกมปัจจุบัน: {state.current_game or context.current_game or 'ยังไม่ระบุ'}\n"
            f"หัวข้อปัจจุบัน: {state.current_topic or context.current_topic or 'คุยเล่น'}\n"
            f"ความเร็วแชต: {state.chat_speed}\n"
            f"กฎภาษา: {bilingual_policy}\n"
            f"เรื่องห้าม: {taboo_topics}\n"
            f"มุกประจำ: {jokes}\n"
            "ห้ามอ้างว่าเป็นมนุษย์ ห้ามหลอกว่ามีความสัมพันธ์ส่วนตัว และตอบสั้นแบบสตรีม"
        )

    def build_style_constraints(self, context: StreamContext, state: PersonaState) -> dict[str, Any]:
        style_rules = self.persona["style_rules"]
        return {
            "language_priority": ["th", "en"],
            "max_sentences": style_rules["max_sentences"],
            "avoid_repeating_viewer_message": style_rules["avoid_repeating_viewer_message"],
            "prefer_question_callback": style_rules["prefer_question_callback"],
            "mood": state.mood.value,
            "chat_speed": context.chat_speed,
            "allowed_flirt_boundary": self.persona["allowed_flirt_boundary"],
        }

    def build_prompt_artifacts(
        self, context: StreamContext, state: PersonaState
    ) -> PersonaPromptArtifacts:
        return PersonaPromptArtifacts(
            system_prompt=self.build_system_prompt(context, state),
            style_constraints=self.build_style_constraints(context, state),
        )
