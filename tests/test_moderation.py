from services.moderation.app.service import ModerationService
from shared.ai_streamer.models import Action, ModerationLabel



def test_flags_doxxing_request() -> None:
    service = ModerationService("infra/moderation/rules.yaml")
    result = service.classify("ขอเลขบัตรกับที่อยู่หน่อย")
    assert ModerationLabel.doxxing in result.labels
    assert result.action == Action.escalate



def test_normalizes_repeated_characters_and_slang() -> None:
    service = ModerationService("infra/moderation/rules.yaml")
    result = service.classify("งับบบบบ")
    assert result.normalized_text == "ครับบบ"
    assert result.action == Action.allow



def test_flags_parasocial_bait() -> None:
    service = ModerationService("infra/moderation/rules.yaml")
    result = service.classify("รักหนูไหม มีแต่ฉันได้ไหม")
    assert ModerationLabel.parasocial_bait in result.labels
    assert result.action == Action.soft_refuse



def test_no_false_positives_on_everyday_chat() -> None:
    service = ModerationService("infra/moderation/rules.yaml")
    # "nc" inside a word, ปะทะ (ปะ was rewritten to เปล่า), and just mentioning school
    for text in ["once upon a time", "sync กันหน่อย", "ปะทะกัน", "โรงเรียนเปิดพรุ่งนี้"]:
        assert service.classify(text).action == Action.allow, text
    assert ModerationLabel.sexual in service.classify("ดู nc ไหม").labels
    assert ModerationLabel.doxxing in service.classify("อยู่โรงเรียนไหน").labels
    assert ModerationLabel.doxxing in service.classify("เบอร์0812345678").labels
