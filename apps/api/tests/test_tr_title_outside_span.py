"""Professional titles stay outside the person span."""

from app.detectors.registry import PageText, run_detectors
from app.domain.models import EntityType


def _of_type(text: str, entity_type: EntityType) -> list[str]:
    found, _names = run_detectors([PageText(page=0, text=text, document_offset=0)], None)
    return [item.text for item in found if item.type == entity_type]


def test_titles_stay_outside_the_name() -> None:
    assert "Zeynep Arslan" in _of_type("Müdafi Av. Zeynep Arslan hazır bulundu.", EntityType.LAWYER_NAME)
    assert "Av. Zeynep Arslan" not in _of_type(
        "Müdafi Av. Zeynep Arslan hazır bulundu.", EntityType.LAWYER_NAME
    )
    assert "Sevgi Tan" in _of_type("Hâkim Sevgi Tan başkanlığında görüldü.", EntityType.JUDGE_NAME)
    assert "Haluk Sönmez" in _of_type("Bilirkişi Haluk Sönmez keşif yaptı.", EntityType.EXPERT_NAME)
    assert "Emre Çelik" in _of_type("Dr. Emre Çelik muayene notunu yazdı.", EntityType.PERSON_NAME)
