"""A trade name beside DAVALI stays one defendant, including later mentions.

Names and addresses are synthetic. SAN. VE TİC.A.Ş. and TİC.A.Ş. stay inside
that party label. A later wrap of the same words reuses it instead of splitting
into extra defendant and company tags.
"""

from __future__ import annotations

from app.detectors.registry import PageText, run_detectors
from app.detectors.textutil import fold_tr_identity
from app.domain.models import EntityCandidate, EntityType
from app.transforms.resolution import assign_resolved_entities

WRAPPED = """DAVALI : ÖRNEK TİCARET TURİZM
ÖZEL EĞİTİM İTHALAT İHRACAT
SAN. VE TİC.A.Ş.
75. Yıl, Örnek Mustafa Kemal Blv. No:10/A D:3, 33330 Mezitli/Mersin
KONU : Tazminat
"""

GLUED = """DAVACI : BETA LOJİSTİK
TİC.A.Ş.
"""

SPACED = "DAVALI : GAMMA GIDA SAN. VE TİC. A.Ş.\n"

BODY = (
    "DAVALI : \u00d6RNEK T\u0130CARET TUR\u0130ZM\n"
    "\u00d6ZEL E\u011e\u0130T\u0130M \u0130THALAT \u0130HRACAT\n"
    "SAN. VE T\u0130C.A.\u015e.\n"
    "75. Y\u0131l, \u00d6rnek Mustafa Kemal Blv. No:10/A D:3, 33330 Mezitli/Mersin\n"
    "KONU : Tazminat\n"
    "\n"
    "A\u00c7IKLAMALAR\n"
    "1. 19.08.2026 tarihinde, \u00d6RNEK\u00a0T\u0130CARET\u00a0TUR\u0130ZM\u00a0\u00d6ZEL\u00a0E\u011e\u0130T\u0130M\u00a0\u0130THALAT\n"
    "\u0130HRACAT SAN. VE T\u0130C.A.\u015e. isimli sat\u0131c\u0131dan \u00f6deme yap\u0131ld\u0131.\n"
)


def _scan(text: str) -> list[EntityCandidate]:
    page = PageText(page=0, text=text, document_offset=0)
    found, _names = run_detectors([page], None)
    return found


def _fold(value: str) -> str:
    return fold_tr_identity(value)


def _titles(found: list[EntityCandidate], entity_type: EntityType) -> list[EntityCandidate]:
    return [item for item in found if item.type == entity_type]


def test_wrapped_trade_name_is_one_defendant_including_the_suffix() -> None:
    found = _scan(WRAPPED)
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 1
    text = _fold(defendants[0].text)
    assert _fold("ÖRNEK TİCARET TURİZM") in text
    assert _fold("ÖZEL EĞİTİM İTHALAT İHRACAT") in text
    assert _fold("SAN. VE TİC.A.Ş.") in text
    assert _titles(found, EntityType.COMPANY_NAME) == []


def test_glued_ticaret_suffix_is_inside_the_claimant_span() -> None:
    found = _scan(GLUED)
    claimants = _titles(found, EntityType.CLAIMANT_NAME)
    assert len(claimants) == 1
    text = _fold(claimants[0].text)
    assert _fold("BETA LOJİSTİK") in text
    assert _fold("TİC.A.Ş.") in text
    assert _titles(found, EntityType.COMPANY_NAME) == []


def test_spaced_sanayi_ticaret_form_stays_one_defendant() -> None:
    found = _scan(SPACED)
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 1
    assert _fold("SAN. VE TİC. A.Ş.") in _fold(defendants[0].text)


def test_single_line_anonim_sirket_beside_davalı_is_a_defendant() -> None:
    found = _scan("DAVALI : DELTA NAKLİYAT A.Ş.\n")
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 1
    assert _fold("DELTA NAKLİYAT A.Ş.") == _fold(defendants[0].text)


def test_company_outside_a_party_block_stays_a_company() -> None:
    found = _scan("ÖRNEK TİCARET A.Ş. teslim etti.\n")
    assert any(
        item.type == EntityType.COMPANY_NAME and _fold("ÖRNEK TİCARET A.Ş.") == _fold(item.text)
        for item in found
    )
    assert _titles(found, EntityType.DEFENDANT_NAME) == []


def test_boulevard_abbreviation_is_an_address_not_a_party() -> None:
    found = _scan(WRAPPED)
    addresses = _titles(found, EntityType.ADDRESS)
    assert len(addresses) == 1
    text = _fold(addresses[0].text)
    assert "blv" in text
    assert _fold("Mezitli/Mersin") in text
    assert _fold("75. Yıl") in text
    assert not any("blv" in _fold(item.text) for item in _titles(found, EntityType.DEFENDANT_NAME))


def test_a_person_defendant_stays_a_person_beside_a_company() -> None:
    text = "DAVALI : DELTA NAKLİYAT A.Ş.\nDAVALI : KEMAL YURT\n"
    found = _scan(text)
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert any("A.Ş." in item.text for item in defendants)
    assert any(_fold(item.text) == _fold("KEMAL YURT") for item in defendants)


def test_trailing_space_before_the_line_break_stays_one_defendant() -> None:
    text = (
        "DAVALI                 : \u00d6RNEK T\u0130CARET TUR\u0130ZM \u00d6ZEL E\u011e\u0130T\u0130M \u0130THALAT \u0130HRACAT\n"
        "                                   SAN. VE T\u0130C.A.\u015e.\n"
        "                                   75. Y\u0131l, \u00d6rnek Mustafa Kemal Blv. No:10/A D:3, 33330 Mezitli/Mersin\n"
        "KONU                     : S\u0131f\u0131r kilometre olarak sat\u0131n al\u0131nan ara\u00e7t\u0131r.\n"
        "A\u00c7IKLAMALAR\n"
        "1. 19.08.2026 tarihinde, \u00d6RNEK T\u0130CARET TUR\u0130ZM \u00d6ZEL E\u011e\u0130T\u0130M \u0130THALAT \n"
        "\u0130HRACAT SAN. VE T\u0130C.A.\u015e. isimli sat\u0131c\u0131dan \u00f6deme yap\u0131ld\u0131.\n"
    )
    found = assign_resolved_entities(_scan(text))
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 2
    assert len({item.resolved_entity_id for item in defendants}) == 1
    for item in defendants:
        folded = _fold(item.text)
        assert _fold("ÖRNEK TİCARET TURİZM") in folded
        assert _fold("İTHALAT") in folded
        assert _fold("İHRACAT") in folded
        assert _fold("SAN. VE TİC.A.Ş.") in folded
        assert "blv" not in folded
    assert _titles(found, EntityType.COMPANY_NAME) == []


def test_blank_lines_inside_the_trade_name_stay_one_defendant() -> None:
    text = (
        "DAVALI : \u00d6RNEK T\u0130CARET TUR\u0130ZM \u00d6ZEL E\u011e\u0130T\u0130M \u0130THALAT\n"
        "\n"
        "\u0130HRACAT\n"
        "\n"
        "        SAN. VE T\u0130C.A.\u015e.\n"
        "75. Y\u0131l, \u00d6rnek Mustafa Kemal Blv. No:10/A D:3, 33330 Mezitli/Mersin\n"
        "\n"
        "1. 19.08.2026 tarihinde, \u00d6RNEK T\u0130CARET TUR\u0130ZM \u00d6ZEL E\u011e\u0130T\u0130M \u0130THALAT\u2028"
        "\u0130HRACAT SAN. VE T\u0130C.A.\u015e. isimli sat\u0131c\u0131dan \u00f6deme yap\u0131ld\u0131.\n"
    )
    found = assign_resolved_entities(_scan(text))
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 2
    assert len({item.resolved_entity_id for item in defendants}) == 1
    for item in defendants:
        folded = _fold(item.text)
        assert _fold("ÖRNEK TİCARET TURİZM") in folded
        assert _fold("İTHALAT") in folded
        assert _fold("İHRACAT") in folded
        assert _fold("SAN. VE TİC.A.Ş.") in folded
        assert "blv" not in folded
    assert _titles(found, EntityType.COMPANY_NAME) == []
    addresses = _titles(found, EntityType.ADDRESS)
    assert len(addresses) == 1
    assert "blv" in _fold(addresses[0].text)


def test_a_found_institution_is_marked_again_later_in_the_paragraph() -> None:
    from app.detectors.legal.repeats import propagate_organisation_repeats
    from app.domain.models import DetectionMethod

    text = (
        "KONU : Vekillik kaydının SGK portalından silinmesi talebidir.\n"
        "Kayıt SGK üzerinden yapılmıştır. SGK üzerindeki kayıt silinsin.\n"
        "Bağlantı vatandas.uyap.gov.tr adresindedir.\n"
    )
    first = text.index("SGK")
    seed = EntityCandidate(
        text="SGK",
        type=EntityType.ORGANISATION,
        start=first,
        end=first + 3,
        page=0,
        detector="LOCAL_NER_TR",
        method=DetectionMethod.DETERMINISTIC,
        validated=True,
    )
    page = PageText(page=0, text=text, document_offset=0)
    found = assign_resolved_entities([seed, *propagate_organisation_repeats([page], [seed])])
    orgs = [item for item in found if item.type is EntityType.ORGANISATION]
    assert [item.start for item in sorted(orgs, key=lambda item: item.start)] == [
        index for index in range(len(text)) if text.startswith("SGK", index)
    ]
    assert len({item.resolved_entity_id for item in orgs}) == 1
    assert all("uyap.gov" not in item.text for item in orgs)


def test_every_numbered_category_reuses_its_own_tag() -> None:
    from app.detectors.legal.repeats import propagate_detected_surface_repeats
    from app.domain.models import DetectionMethod

    text = "KEREM dosyada geçti. Sonra yine KEREM yazıldı. Plaka 33 ABC 123 ve yeniden 33 ABC 123."
    person_at = text.index("KEREM")
    plate_at = text.index("33 ABC 123")
    seeds = [
        EntityCandidate(
            text="KEREM",
            type=EntityType.PERSON_NAME,
            start=person_at,
            end=person_at + len("KEREM"),
            page=0,
            detector="LOCAL_NER_TR",
            method=DetectionMethod.DETERMINISTIC,
            validated=True,
        ),
        EntityCandidate(
            text="33 ABC 123",
            type=EntityType.VEHICLE_PLATE,
            start=plate_at,
            end=plate_at + len("33 ABC 123"),
            page=0,
            detector="TR_VEHICLE_PLATE",
            method=DetectionMethod.DETERMINISTIC,
            validated=True,
        ),
    ]
    page = PageText(page=0, text=text, document_offset=0)
    found = assign_resolved_entities([*seeds, *propagate_detected_surface_repeats([page], seeds)])
    people = [item for item in found if item.type is EntityType.PERSON_NAME]
    plates = [item for item in found if item.type is EntityType.VEHICLE_PLATE]
    assert len(people) == 2
    assert len(plates) == 2
    assert len({item.resolved_entity_id for item in people}) == 1
    assert len({item.resolved_entity_id for item in plates}) == 1
    assert people[0].resolved_entity_id != plates[0].resolved_entity_id


def test_a_review_copy_follows_the_accepted_tag() -> None:
    from app.detectors.legal.repeats import accept_repeated_numbered_surfaces
    from app.domain.models import DetectionMethod

    def candidate(text: str, entity_type: EntityType, start: int, review: bool) -> EntityCandidate:
        return EntityCandidate(
            text=text,
            type=entity_type,
            start=start,
            end=start + len(text),
            page=0,
            detector="LOCAL_NER_TR",
            method=DetectionMethod.DETERMINISTIC,
            validated=not review,
            needs_review=review,
            attributes={"scoring_decision": "REVIEW" if review else "ACCEPT"},
        )

    found = accept_repeated_numbered_surfaces([
        candidate("SGK", EntityType.ORGANISATION, 0, False),
        candidate("SGK", EntityType.ORGANISATION, 20, True),
        candidate("Oda", EntityType.ORGANISATION, 40, True),
        candidate("01.01.2026", EntityType.DATE, 60, False),
        candidate("01.01.2026", EntityType.DATE, 80, True),
    ])
    sgk = [item for item in found if item.text == "SGK"]
    assert [item.needs_review for item in sgk] == [False, False]
    assert next(item for item in found if item.text == "Oda").needs_review is True
    dates = [item for item in found if item.type is EntityType.DATE]
    assert [item.needs_review for item in dates] == [False, True]


def test_a_later_mention_keeps_the_high_probability_tag() -> None:
    from app.domain.models import DetectionMethod
    from app.ner.runtime import _score_ner_candidates_counted

    text = "Vekil SGK kaydı tamam. Vekil SGK notu kaldı. Vekil Oda yazdı."
    first = text.index("SGK")
    second = text.index("SGK", first + 1)
    baro = text.index("Oda")

    def mention(surface: str, start: int, model_score: float) -> EntityCandidate:
        return EntityCandidate(
            text=surface,
            type=EntityType.ORGANISATION,
            start=start,
            end=start + len(surface),
            page=0,
            detector="LOCAL_NER_TR",
            method=DetectionMethod.DETERMINISTIC,
            validated=False,
            attributes={"source": "local_ner", "ner_model_score": model_score},
        )

    page = PageText(page=0, text=text, document_offset=0)
    kept, _accept, _review, _ignore = _score_ner_candidates_counted(
        [page],
        [
            mention("SGK", second, 0.70),
            mention("SGK", first, 0.95),
            mention("Oda", baro, 0.62),
        ],
        [],
    )
    sgk = [item for item in kept if item.text == "SGK"]
    assert len(sgk) == 2
    assert all(item.needs_review is False for item in sgk)
    assert all((item.attributes or {}).get("scoring_decision") == "ACCEPT" for item in sgk)
    weak = next(item for item in sgk if item.start == second)
    assert (weak.attributes or {}).get("accepted_with_surface") is True
    other = next(item for item in kept if item.text == "Oda")
    assert other.needs_review is True


def test_later_mention_reuses_the_same_defendant_title() -> None:
    found = assign_resolved_entities(_scan(BODY))
    defendants = _titles(found, EntityType.DEFENDANT_NAME)
    assert len(defendants) == 2
    assert len({item.resolved_entity_id for item in defendants}) == 1
    for item in defendants:
        text = _fold(item.text)
        assert _fold("ÖRNEK TİCARET TURİZM") in text
        assert _fold("SAN. VE TİC.A.Ş.") in text
        assert _fold("İHRACAT") in text
    assert _titles(found, EntityType.COMPANY_NAME) == []


def test_named_bar_association_is_tagged_and_the_bare_word_is_not() -> None:
    found = _scan(
        "Baro yazısı geldi. BAROSU kayıt etti. barolar dosyayı gördü. "
        "Türkiye Barolar Birliği yazdı. TÜRKİYE BAROLAR BİRLİĞİ'NİN kararı var. "
        "İstanbul Barosu ve ANKARA BAROSU ve izmir barosunun dosyası duruyor."
    )
    orgs = [
        _fold(item.text) for item in found if item.type is EntityType.ORGANISATION
    ]
    surfaces = [_fold(item.text) for item in found]
    assert any(item.startswith(_fold("İstanbul Barosu")) for item in orgs)
    assert any(item.startswith(_fold("Ankara Barosu")) for item in orgs)
    assert any("izmir barosu" in item for item in orgs)
    for item in surfaces:
        assert not item.startswith("baro")
        assert "barolar birlig" not in item


def test_the_word_uyap_is_not_an_institution_and_the_access_line_stays() -> None:
    from app.detectors.legal.repeats import propagate_organisation_repeats
    from app.domain.models import DetectionMethod
    from app.services.pipeline import uses_paper_redaction

    text = (
        "Kayıt UYAP üzerinden yapılmıştır. uyap üzerindeki kayıt silinsin.\n"
        "https://vatandas.uyap.gov.tr/giris adresinden erişebilirsiniz.\n"
    )
    found = _scan(text)
    assert not any(
        item.type is EntityType.ORGANISATION and _fold(item.text) == "uyap" for item in found
    )
    access = [item for item in found if item.type is EntityType.UYAP_ACCESS]
    assert len(access) == 1
    assert "vatandas.uyap.gov.tr" in access[0].text.lower()
    assert uses_paper_redaction(access[0])

    first = text.index("UYAP")
    seed = EntityCandidate(
        text="UYAP",
        type=EntityType.ORGANISATION,
        start=first,
        end=first + 4,
        page=0,
        detector="LOCAL_NER_TR",
        method=DetectionMethod.DETERMINISTIC,
        validated=True,
    )
    page = PageText(page=0, text=text, document_offset=0)
    assert propagate_organisation_repeats([page], [seed]) == []
