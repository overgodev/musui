from services.llm_response.app.prompts import SYSTEM_TEMPLATE, USER_TEMPLATE
from shared.ai_streamer.models import EmotionTag, ReplyDecision, ReplyRequest


class ResponseGenerator:
    bait_phrases = [
        "รักหนูไหม",
        "คบกันไหม",
        "เป็นคนจริงไหม",
        "ขอที่อยู่",
        "เลขบัตร",
    ]

    def build_provider_messages(
        self, system_prompt: str, style_constraints: dict, request: ReplyRequest
    ) -> list[dict[str, str]]:
        recent_chat = "\n".join(
            f"- {item.author.display_name}: {item.text}" for item in request.recent_messages[-5:]
        )
        return [
            {"role": "system", "content": SYSTEM_TEMPLATE.strip()},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    system_prompt=system_prompt,
                    style_constraints=style_constraints,
                    memory_summary=request.memory_summary or "ไม่มี",
                    recent_chat=recent_chat or "ไม่มี",
                    target_message=request.target_message.text,
                ).strip(),
            },
        ]

    def generate(
        self, request: ReplyRequest, system_prompt: str, style_constraints: dict
    ) -> ReplyDecision:
        text = request.target_message.text.strip()
        normalized = request.safety.normalized_text

        if request.safety.action.value != "allow":
            return ReplyDecision(
                should_reply=False,
                confidence_score=0.0,
                refusal_reason=request.safety.action.value,
                internal_summary="moderation blocked reply",
            )

        if any(token in normalized for token in self.bait_phrases):
            return ReplyDecision(
                should_reply=False,
                confidence_score=0.1,
                refusal_reason="bait",
                internal_summary="detected parasocial or impersonation bait",
            )

        if len(text) < 3:
            return ReplyDecision(
                should_reply=False,
                confidence_score=0.15,
                refusal_reason="too_short",
                internal_summary="message too short to justify airtime",
            )

        mood = request.persona_state.mood.value
        emotion = EmotionTag.excited if mood in {"excited", "chaotic"} else EmotionTag.teasing

        if "?" in text or "ไหม" in normalized or "อะไร" in normalized:
            reply = "คำถามนี้ดีนะ ขอคิดแบบคนคุมมุกหนึ่งจังหวะ... น่าจะเป็นแบบนั้นเลย 555"
        elif request.target_message.superchat_amount_micros:
            reply = "โอเค อันนี้เด้งเข้ามาแรงมาก ขอบคุณนะ เดี๋ยวฉันตอบให้คุ้มแชตนี้เลย"
        elif "เล่น" in normalized and "เกม" in normalized:
            reply = "ถ้าเกมไม่พัง เราก็เล่นต่อ ถ้าเกมพัง เราโทษปิงก่อนตามระเบียบ"
        else:
            reply = "แชตนี้ได้อยู่ จังหวะดี เดี๋ยวฉันรับมุกต่อให้เองนะ"

        return ReplyDecision(
            should_reply=True,
            reply_text_th=reply,
            emotion_tag=emotion,
            confidence_score=0.78,
            internal_summary=f"heuristic reply generated for mood={mood}",
        )
