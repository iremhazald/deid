"""NER subword slices must not become tags of their own."""

from app.detectors.legal.merge import merge_rule_candidates
from app.domain.models import DetectionMethod, EntityCandidate

from app.detectors.legal.court import COURT_SPAN, overlaps_duty_court
from app.detectors.registry import PageText
from app.domain.models import EntityType
from app.ner.adapter import ner_prediction_to_candidate
from app.ner.models import NERPrediction


def _page(text: str) -> PageText:
    return PageText(page=0, text=text, document_offset=0)


def _prediction(text: str, start: int, end: int, label: str = "ORG") -> NERPrediction:
    return NERPrediction(
        start=start,
        end=end,
        text=text[start:end],
        label=label,
        score=0.9,
        language="tr",
        provider="test",
        model_id="test",
    )


def test_subword_slice_grows_to_the_whole_word() -> None:
    text = "eksper şirketi Betarapor tarafından"
    start = text.index("rap")
    found = ner_prediction_to_candidate(
        _prediction(text, start, start + 3),
        _page(text),
        document_language="tr",
    )
    assert found is not None
    assert found.text == "Betarapor"
    assert found.type is EntityType.ORGANISATION


def test_duty_court_slice_is_not_an_organisation() -> None:
    text = "MERSİN NÖBETÇİ TÜKETİCİ MAHKEMESİ'NE"
    match = COURT_SPAN.search(text)
    assert match is not None
    assert "NÖBETÇİ" in match.group(0)
    assert "MAHKEMESİ" in match.group(0)
    start = text.index("Çİ")
    assert overlaps_duty_court(text, start, text.index("MAHKEMESİ") + len("MAHKEMESİ"))
    found = ner_prediction_to_candidate(
        _prediction(text, start, text.index("'")),
        _page(text),
        document_language="tr",
    )
    assert found is None


def test_numbered_court_name_stays_available() -> None:
    text = "Mersin 2. Tüketici Mahkemesi karar verdi."
    start = text.index("Mersin")
    end = text.index(" kararı" if " kararı" in text else " karar")
    found = ner_prediction_to_candidate(
        _prediction(text, start, end),
        _page(text),
        document_language="tr",
    )
    assert found is not None
    assert found.text == "Mersin 2. Tüketici Mahkemesi"


def test_full_claimant_name_survives_a_shorter_model_token() -> None:
    full = EntityCandidate(
        text="AYŞE YILMAZ",
        type=EntityType.CLAIMANT_NAME,
        start=10,
        end=21,
        page=0,
        detector="TR_LEGAL_PARTY",
        method=DetectionMethod.DETERMINISTIC,
    )
    short = EntityCandidate(
        text="AYŞE",
        type=EntityType.PERSON_NAME,
        start=10,
        end=14,
        page=0,
        detector="LOCAL_NER_TR",
        method=DetectionMethod.DETERMINISTIC,
    )
    merged = merge_rule_candidates([full, short])
    claimants = [item for item in merged if item.type is EntityType.CLAIMANT_NAME]
    assert [item.text for item in claimants] == ["AYŞE YILMAZ"]
    assert all(item.text != "AYŞE" for item in merged)


def test_extending_left_releases_the_neighbour() -> None:
    from app.transforms.entity_merge import _release_overlap

    text = "AYŞE YILMAZ TOFAŞ"
    neighbour = EntityCandidate(
        text="AYŞE YILMAZ",
        type=EntityType.ORGANISATION,
        start=0,
        end=11,
        page=0,
        detector="LOCAL_NER_TR",
        method=DetectionMethod.DETERMINISTIC,
    )
    released = _release_overlap(neighbour, text.index("YILMAZ"), len(text), text)
    assert released is not None
    assert released.text == "AYŞE"
    assert released.end == text.index("YILMAZ") - 1


def test_complete_person_span_is_unchanged() -> None:
    text = "DAVACI : AYŞE YILMAZ"
    start = text.index("AYŞE")
    end = start + len("AYŞE YILMAZ")
    found = ner_prediction_to_candidate(
        _prediction(text, start, end, "PER"),
        _page(text),
        document_language="tr",
    )
    assert found is not None
    assert found.text == "AYŞE YILMAZ"
    assert found.type is EntityType.PERSON_NAME
