"""Synthetic tests for the 11 additional legal-role person labels.

Names are invented. Detection stays on the shared normalized-text pipeline.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from app.detectors.registry import PageText, run_detectors
from app.detectors.textutil import fold_tr_identity
from app.domain.models import (
    AnalysisResponse,
    AnalysisStatus,
    DetectionMethod,
    DetectionMode,
    DocumentKind,
    EntityCandidate,
    EntityType,
    LocalNERStatus,
    PrivacyProfile,
    ReclassifyRequest,
    RedactionDecision,
    RedactionRequest,
    SourceDocumentType,
    TransformationStrategy,
    WorkspaceMode,
)
from app.services.jobs import Job
from app.services.pipeline import (
    analyze_pdf,
    analyze_textual_document,
    pdf_transformation_route,
    preview_transformations,
)
from app.transforms.catalog import allowed_strategies, build_catalog, recommended_strategy
from app.transforms.entity_merge import confirm_entity_merge, reclassify_entities
from app.transforms.possible_matches import generate_possible_matches
from app.transforms.resolution import assign_resolved_entities
from app.transforms.strategies import initials_value
from app.transforms.tag_registry import stamp_placeholder_tokens, tag_locale_for_document
from app.transforms.tag_taxonomy import spec_for
from app.transforms.turkish_morphology import attach_turkish_suffix

NEW_LABELS = (
    "VICTIM_NAME",
    "COMPLAINANT_NAME",
    "SUSPECT_NAME",
    "ACCUSED_NAME",
    "COMPLAINANT_ACCUSED_NAME",
    "INTERVENOR_NAME",
    "LEGAL_REPRESENTATIVE_NAME",
    "MEDIATOR_NAME",
    "INTERPRETER_NAME",
    "ENFORCEMENT_OFFICER_NAME",
    "NOTARY_NAME",
    "ARBITRATOR_NAME",
)
EXISTING_LABELS = (
    "PERSON_NAME",
    "JUDGE_NAME",
    "LAWYER_NAME",
    "CLAIMANT_NAME",
    "DEFENDANT_NAME",
    "WITNESS_NAME",
    "EXPERT_NAME",
    "PROSECUTOR_NAME",
    "COURT_CLERK_NAME",
)
PERSON_STRATEGIES = {
    TransformationStrategy.REDACT,
    TransformationStrategy.PLACEHOLDER,
    TransformationStrategy.INITIALS,
    TransformationStrategy.KEEP,
}
ROSTER = """T.C.
ÖRNEK 3. AĞIR CEZA MAHKEMESİ

MAĞDUR          : AYŞE YILMAZ
MÜŞTEKİ         : HASAN DEMİR
ŞÜPHELİ         : ALİ KAYA
SANIK           : MEHMET ÇELİK
KATILAN         : ZEYNEP ARSLAN
KANUNİ TEMSİLCİ : FATMA AKSOY
ARABULUCU       : DENİZ ŞAHİN
TERCÜMAN        : SELİN KOÇ
İCRA MÜDÜRÜ     : MURAT YILDIZ
NOTER           : ECE AYDIN
HAKEM           : EMRE ÖZTÜRK
"""
EXPECTED = (
    ("AYŞE YILMAZ", EntityType.VICTIM_NAME),
    ("HASAN DEMİR", EntityType.COMPLAINANT_NAME),
    ("ALİ KAYA", EntityType.SUSPECT_NAME),
    ("MEHMET ÇELİK", EntityType.ACCUSED_NAME),
    ("ZEYNEP ARSLAN", EntityType.INTERVENOR_NAME),
    ("FATMA AKSOY", EntityType.LEGAL_REPRESENTATIVE_NAME),
    ("DENİZ ŞAHİN", EntityType.MEDIATOR_NAME),
    ("SELİN KOÇ", EntityType.INTERPRETER_NAME),
    ("MURAT YILDIZ", EntityType.ENFORCEMENT_OFFICER_NAME),
    ("ECE AYDIN", EntityType.NOTARY_NAME),
    ("EMRE ÖZTÜRK", EntityType.ARBITRATOR_NAME),
)


def _scan(text: str, language: str) -> list[EntityCandidate]:
    page = PageText(page=0, text=text, document_offset=0)
    locale_ids = ["global", "en"] if language == "en" else None
    found, _names = run_detectors([page], locale_ids)
    return found


def _fold(value: str) -> str:
    return fold_tr_identity(value)


def _has(found: list[EntityCandidate], entity_type: EntityType, name: str) -> bool:
    target = _fold(name)
    return any(item.type == entity_type and _fold(item.text) == target for item in found)


def _of_type(found: list[EntityCandidate], entity_type: EntityType) -> list[str]:
    return [item.text for item in found if item.type == entity_type]


def _person(text: str, entity_type: EntityType, start: int, role: str | None = None) -> EntityCandidate:
    return EntityCandidate(
        id=f"{entity_type.value}-{start}",
        text=text,
        type=entity_type,
        start=start,
        end=start + len(text),
        page=0,
        detector="test",
        method=DetectionMethod.DETERMINISTIC,
        role=role,
    )


def test_schema_accepts_eleven_labels_and_keeps_existing_ones() -> None:
    assert len(EntityType) == 59
    for label in NEW_LABELS:
        assert EntityType(label).value == label
    for label in EXISTING_LABELS:
        assert EntityType(label).value == label
    request = ReclassifyRequest(entity_ids=["span-1"], entity_type=EntityType.VICTIM_NAME)
    assert request.model_dump()["entity_type"] == "VICTIM_NAME"

    catalog = build_catalog()
    categories = {item["category"]: item for item in catalog["categories"]}
    legal = next(group["types"] for group in catalog["scan_scope_groups"] if group["id"] == "legal")
    for label in NEW_LABELS:
        assert label in categories
        assert set(categories[label]["allowed_strategies"]) == {item.value for item in PERSON_STRATEGIES}
        assert "PARTIAL_MASK" not in categories[label]["allowed_strategies"]
        assert categories[label]["recommended_strategy"] == "PLACEHOLDER"
        assert label in legal
        assert set(allowed_strategies(EntityType(label))) == PERSON_STRATEGIES
        assert recommended_strategy(EntityType(label)) is TransformationStrategy.PLACEHOLDER
    assert "PROSECUTOR_NAME" in categories
    assert "COURT_CLERK_NAME" in categories
    assert "DEFENDANT_NAME" in categories
    assert "CLAIMANT_NAME" in categories


def test_turkish_role_table_assigns_each_label_to_the_name_only() -> None:
    found = _scan(ROSTER, "tr")
    for name, entity_type in EXPECTED:
        assert _has(found, entity_type, name), (name, _of_type(found, entity_type))
        match = next(item for item in found if item.type == entity_type and _fold(item.text) == _fold(name))
        assert not any(char.isdigit() for char in match.text)
    for role in (
        "MAĞDUR",
        "MÜŞTEKİ",
        "ŞÜPHELİ",
        "SANIK",
        "KATILAN",
        "TEMSİLCİ",
        "ARABULUCU",
        "TERCÜMAN",
        "MÜDÜRÜ",
        "NOTER",
        "HAKEM",
    ):
        assert not any(_fold(item.text) == _fold(role) for item in found)


def test_turkish_case_colon_linebreak_and_registry_number() -> None:
    samples = [
        ("mağdur: Ayşe Yılmaz", EntityType.VICTIM_NAME, "Ayşe Yılmaz"),
        ("Suç Mağduru Ayşe Yılmaz", EntityType.VICTIM_NAME, "Ayşe Yılmaz"),
        ("Mağdur Çocuk\nAyşe Yılmaz", EntityType.VICTIM_NAME, "Ayşe Yılmaz"),
        ("Şikâyetçi: Hasan Demir", EntityType.COMPLAINANT_NAME, "Hasan Demir"),
        ("MÜŞTEKİ-ŞÜPHELİ : AYŞE YILMAZ", EntityType.COMPLAINANT_NAME, "AYŞE YILMAZ"),
        ("Şüphelinin Adı Soyadı: Ali Kaya", EntityType.SUSPECT_NAME, "Ali Kaya"),
        ("Sanığın Adı Soyadı\nMehmet Çelik", EntityType.ACCUSED_NAME, "Mehmet Çelik"),
        ("Suça Sürüklenen Çocuk: Mehmet Çelik", EntityType.ACCUSED_NAME, "Mehmet Çelik"),
        ("SSÇ : MEHMET ÇELİK", EntityType.ACCUSED_NAME, "MEHMET ÇELİK"),
        ("Müdahil Zeynep Arslan", EntityType.INTERVENOR_NAME, "Zeynep Arslan"),
        ("Katılan Müşteki: Zeynep Arslan", EntityType.INTERVENOR_NAME, "Zeynep Arslan"),
        ("Yasal Temsilci Fatma Aksoy", EntityType.LEGAL_REPRESENTATIVE_NAME, "Fatma Aksoy"),
        ("Vasi : FATMA AKSOY", EntityType.LEGAL_REPRESENTATIVE_NAME, "FATMA AKSOY"),
        ("Kayyım : FATMA AKSOY", EntityType.LEGAL_REPRESENTATIVE_NAME, "FATMA AKSOY"),
        ("Arabulucu Avukat Deniz Şahin", EntityType.MEDIATOR_NAME, "Deniz Şahin"),
        ("Yeminli Tercüman Selin Koç", EntityType.INTERPRETER_NAME, "Selin Koç"),
        ("Çevirmen : Selin Koç", EntityType.INTERPRETER_NAME, "Selin Koç"),
        ("İcra Müdür Yardımcısı Murat Yıldız", EntityType.ENFORCEMENT_OFFICER_NAME, "Murat Yıldız"),
        ("İcra Görevlisi : Murat Yıldız", EntityType.ENFORCEMENT_OFFICER_NAME, "Murat Yıldız"),
        ("İcra Memuru Murat Yıldız", EntityType.ENFORCEMENT_OFFICER_NAME, "Murat Yıldız"),
        ("Noterin Adı Soyadı: Ece Aydın", EntityType.NOTARY_NAME, "Ece Aydın"),
        ("Noterlik görevini yürüten Ece Aydın", EntityType.NOTARY_NAME, "Ece Aydın"),
        ("Tek Hakem Emre Öztürk", EntityType.ARBITRATOR_NAME, "Emre Öztürk"),
        ("Hakem Heyeti Başkanı : Emre Öztürk", EntityType.ARBITRATOR_NAME, "Emre Öztürk"),
        ("Hakem Kurulu Üyesi Emre Öztürk", EntityType.ARBITRATOR_NAME, "Emre Öztürk"),
    ]
    for text, entity_type, name in samples:
        found = _scan(text, "tr")
        assert _has(found, entity_type, name), (text, [(item.type.value, item.text) for item in found])

    numbered = _scan("MAĞDUR : AYŞE YILMAZ 376901\nSANIK : MEHMET ÇELİK 284513\n", "tr")
    victim = next(item for item in numbered if item.type == EntityType.VICTIM_NAME)
    accused = next(item for item in numbered if item.type == EntityType.ACCUSED_NAME)
    assert victim.text == "AYŞE YILMAZ"
    assert accused.text == "MEHMET ÇELİK"
    assert "376901" not in victim.text
    assert "284513" not in accused.text


def test_role_words_and_ordinary_mentions_are_not_people() -> None:
    text = (
        "MAĞDUR\n"
        "MÜŞTEKİ\n"
        "ŞÜPHELİ\n"
        "SANIK\n"
        "KATILAN\n"
        "NOTER\n"
        "HAKEM\n"
        "Mağdur beyanı okundu.\n"
        "Müşteki şikayetini tekrarladı.\n"
        "Şüpheli ifadesi alındı.\n"
        "Sanık savunmasını yaptı.\n"
        "Toplantıya katılan kişiler tutanak tuttu.\n"
        "Toplantıya katılan Ayşe Yılmaz söz aldı.\n"
        "Müdür göreve başladı.\n"
        "Müdür Ahmet Yılmaz göreve başladı.\n"
        "İstanbul 5. Noterliği 184513\n"
        "Futbol hakem Emre Öztürk maçı yönetti.\n"
        "Av. Kerem Aslan müvekkilini temsil etti.\n"
    )
    found = _scan(text, "tr")
    for entity_type in (
        EntityType.VICTIM_NAME,
        EntityType.COMPLAINANT_NAME,
        EntityType.SUSPECT_NAME,
        EntityType.ACCUSED_NAME,
        EntityType.INTERVENOR_NAME,
        EntityType.ENFORCEMENT_OFFICER_NAME,
        EntityType.NOTARY_NAME,
        EntityType.ARBITRATOR_NAME,
        EntityType.LEGAL_REPRESENTATIVE_NAME,
    ):
        assert _of_type(found, entity_type) == [], (entity_type, _of_type(found, entity_type))
    assert any(item.type == EntityType.LAWYER_NAME and "Kerem Aslan" in item.text for item in found)


def test_distinct_roles_stay_distinct() -> None:
    pairs = [
        ("DAVACI : LALE ÖZTÜRK", EntityType.CLAIMANT_NAME, "LALE ÖZTÜRK"),
        ("MÜŞTEKİ : HASAN DEMİR", EntityType.COMPLAINANT_NAME, "HASAN DEMİR"),
        ("DAVALI : KEMAL YURT", EntityType.DEFENDANT_NAME, "KEMAL YURT"),
        ("SANIK : MEHMET ÇELİK", EntityType.ACCUSED_NAME, "MEHMET ÇELİK"),
        ("ŞÜPHELİ : ALİ KAYA", EntityType.SUSPECT_NAME, "ALİ KAYA"),
        ("Bilirkişi Deniz Aksoy raporunu sundu.", EntityType.EXPERT_NAME, "Deniz Aksoy"),
        ("Hakem Emre Öztürk karar verdi.", EntityType.ARBITRATOR_NAME, "Emre Öztürk"),
    ]
    for text, entity_type, name in pairs:
        found = _scan(text, "tr")
        assert any(item.type == entity_type and name in item.text for item in found), (
            text,
            [(item.type.value, item.text) for item in found],
        )
        if entity_type == EntityType.COMPLAINANT_NAME:
            assert not _has(found, EntityType.CLAIMANT_NAME, name)
        if entity_type == EntityType.ACCUSED_NAME:
            assert not _has(found, EntityType.DEFENDANT_NAME, name)
        if entity_type == EntityType.DEFENDANT_NAME:
            assert not _has(found, EntityType.ACCUSED_NAME, name)
        if entity_type == EntityType.ARBITRATOR_NAME:
            assert not _has(found, EntityType.EXPERT_NAME, name)
        if entity_type == EntityType.EXPERT_NAME:
            assert not _has(found, EntityType.ARBITRATOR_NAME, name)


def test_same_person_can_carry_two_roles_without_an_automatic_merge() -> None:
    text = "MAĞDUR : AYŞE YILMAZ\nMÜŞTEKİ : AYŞE YILMAZ\nSANIK : MEHMET ÇELİK\n"
    found = _scan(text, "tr")
    victim = next(item for item in found if item.type == EntityType.VICTIM_NAME)
    complainant = next(item for item in found if item.type == EntityType.COMPLAINANT_NAME)
    accused = next(item for item in found if item.type == EntityType.ACCUSED_NAME)
    resolved = assign_resolved_entities([victim, complainant, accused])
    assert resolved[0].resolved_entity_id != resolved[1].resolved_entity_id
    assert resolved[0].resolved_entity_id != resolved[2].resolved_entity_id
    suggestions = generate_possible_matches(resolved, text)
    paired = {
        tuple(sorted(member.text for member in item.members))
        for item in suggestions
    }
    assert ("AYŞE YILMAZ", "AYŞE YILMAZ") in paired
    assert all("MEHMET ÇELİK" not in pair or pair == ("MEHMET ÇELİK", "MEHMET ÇELİK") for pair in paired)


def test_english_roles_require_an_attributable_name() -> None:
    text = (
        "Victim: Elena Marlow\n"
        "Complainant Hasan Demir filed the report.\n"
        "Reporting Party Nora Blake\n"
        "Suspect Ali Kaya was interviewed.\n"
        "Accused Mehmet Celik entered a plea.\n"
        "Criminal Defendant Mehmet Celik appeared.\n"
        "Intervenor Zeynep Arslan joined.\n"
        "Intervening Party Zeynep Arslan\n"
        "Legal Representative Fatma Aksoy attended.\n"
        "Legal Guardian Fatma Aksoy attended.\n"
        "Mediator Deniz Sahin opened the session.\n"
        "Court Interpreter Selin Koc translated.\n"
        "Interpreter Selin Koc translated.\n"
        "Enforcement Officer Murat Yildiz served the writ.\n"
        "Enforcement Bailiff Murat Yildiz served the writ.\n"
        "Notary Public Ece Aydin certified the copy.\n"
        "Sole Arbitrator Emre Ozturk signed.\n"
        "Presiding Arbitrator Emre Ozturk signed.\n"
    )
    found = _scan(text, "en")
    expect = [
        (EntityType.VICTIM_NAME, "Elena Marlow"),
        (EntityType.COMPLAINANT_NAME, "Hasan Demir"),
        (EntityType.COMPLAINANT_NAME, "Nora Blake"),
        (EntityType.SUSPECT_NAME, "Ali Kaya"),
        (EntityType.ACCUSED_NAME, "Mehmet Celik"),
        (EntityType.INTERVENOR_NAME, "Zeynep Arslan"),
        (EntityType.LEGAL_REPRESENTATIVE_NAME, "Fatma Aksoy"),
        (EntityType.MEDIATOR_NAME, "Deniz Sahin"),
        (EntityType.INTERPRETER_NAME, "Selin Koc"),
        (EntityType.ENFORCEMENT_OFFICER_NAME, "Murat Yildiz"),
        (EntityType.NOTARY_NAME, "Ece Aydin"),
        (EntityType.ARBITRATOR_NAME, "Emre Ozturk"),
    ]
    for entity_type, name in expect:
        assert _has(found, entity_type, name), (name, [(item.type.value, item.text) for item in found])

    plain = _scan(
        "The victim left the room.\n"
        "Defendant Jane Roe answered the claim.\n"
        "The party filed a brief.\n"
        "Representative Owen Blake appeared.\n"
        "The clerk kept the record.\n"
        "Referee John Smith started the match.\n"
        "A bailiff called the case.\n",
        "en",
    )
    assert _of_type(plain, EntityType.VICTIM_NAME) == []
    assert _of_type(plain, EntityType.ACCUSED_NAME) == []
    assert _of_type(plain, EntityType.INTERVENOR_NAME) == []
    assert _of_type(plain, EntityType.LEGAL_REPRESENTATIVE_NAME) == []
    assert _of_type(plain, EntityType.ENFORCEMENT_OFFICER_NAME) == []
    assert _of_type(plain, EntityType.ARBITRATOR_NAME) == []
    assert any(item.type == EntityType.LAWYER_NAME and "Owen Blake" in item.text for item in plain)
    assert not any(item.type == EntityType.COURT_CLERK_NAME for item in plain)
    assert not any(item.type == EntityType.ENFORCEMENT_OFFICER_NAME for item in plain)


def test_placeholders_numbering_locale_and_transformations() -> None:
    expected = {
        EntityType.VICTIM_NAME: ("MAGDUR", "VICTIM"),
        EntityType.COMPLAINANT_NAME: ("MÜŞTEKİ", "COMPLAINANT"),
        EntityType.COMPLAINANT_ACCUSED_NAME: ("MÜŞTEKİ_SANIK", "COMPLAINANT_ACCUSED"),
        EntityType.SUSPECT_NAME: ("SUPHELI", "SUSPECT"),
        EntityType.ACCUSED_NAME: ("SANIK", "ACCUSED"),
        EntityType.INTERVENOR_NAME: ("KATILAN", "INTERVENOR"),
        EntityType.LEGAL_REPRESENTATIVE_NAME: ("KANUNI_TEMSILCI", "LEGAL_REPRESENTATIVE"),
        EntityType.MEDIATOR_NAME: ("ARABULUCU", "MEDIATOR"),
        EntityType.INTERPRETER_NAME: ("TERCUMAN", "INTERPRETER"),
        EntityType.ENFORCEMENT_OFFICER_NAME: ("ICRA_MEMURU", "ENFORCEMENT_OFFICER"),
        EntityType.NOTARY_NAME: ("NOTER", "NOTARY"),
        EntityType.ARBITRATOR_NAME: ("HAKEM", "ARBITRATOR"),
    }
    people = []
    for index, (entity_type, (tr, en)) in enumerate(expected.items()):
        spec = spec_for(entity_type)
        assert spec.labels_tr == tr
        assert spec.labels_en == en
        assert spec.example_tr == f"[{tr}_1]"
        assert spec.example_en == f"[{en}_1]"
        people.append(_person(f"Kisi {index}", entity_type, index * 20, spec.family))
    stamped = stamp_placeholder_tokens(people, "tr")
    assert [item.placeholder_token for item in stamped] == [f"[{tr}_1]" for tr, _en in expected.values()]
    english = stamp_placeholder_tokens(people, "en")
    assert [item.placeholder_token for item in english] == [f"[{en}_1]" for _tr, en in expected.values()]
    assert tag_locale_for_document(resolved_document_language="en", job_locale="tr") == "en"

    first = _person("Ayşe Yılmaz", EntityType.VICTIM_NAME, 0, "VICTIM")
    again = _person("Ayşe Yılmaz", EntityType.PERSON_NAME, 30)
    other = _person("Hasan Demir", EntityType.VICTIM_NAME, 60, "VICTIM")
    numbered = stamp_placeholder_tokens([first, again, other], "tr")
    assert numbered[0].placeholder_token == numbered[1].placeholder_token == "[MAGDUR_1]"
    assert numbered[2].placeholder_token == "[MAGDUR_2]"
    assert initials_value("Ayşe Yılmaz") == "A.Y."
    assert attach_turkish_suffix("[SANIK_1]", "ın").startswith("[SANIK_1]")


def test_manual_reclassification_uses_the_new_label() -> None:
    manual = EntityCandidate(
        id="manual-1",
        text="Ebru Tan",
        type=EntityType.PERSON_NAME,
        start=0,
        end=8,
        page=0,
        detector="USER_SELECTION",
        method=DetectionMethod.MANUAL,
    )
    job = Job(
        id="job-roles",
        directory=Path("."),
        source_path=Path("synthetic.txt"),
        document_kind=DocumentKind.DOCX,
        created_at=0,
        source_document_type=SourceDocumentType.DOCX,
        workspace_mode=WorkspaceMode.TEXT,
        locale="tr",
        requested_document_language="tr",
        analysis=AnalysisResponse(
            job_id="job-roles",
            file_name="synthetic.docx",
            document_kind=DocumentKind.DOCX,
            source_document_type=SourceDocumentType.DOCX,
            workspace_mode=WorkspaceMode.TEXT,
            document_hash="synthetic",
            page_count=1,
            text="Ebru Tan",
            entities=[manual],
            detectors_executed=["USER_SELECTION"],
            profile=PrivacyProfile.KVKK,
            detection_mode=DetectionMode.RULES_ONLY,
            analysis_status=AnalysisStatus.COMPLETE,
            local_ner_status=LocalNERStatus.NOT_REQUESTED,
            requested_document_language="tr",
            resolved_document_language="tr",
        ),
    )
    reclassify_entities(job, ["manual-1"], EntityType.NOTARY_NAME)
    assert job.analysis is not None
    updated = job.analysis.entities[0]
    assert updated.type is EntityType.NOTARY_NAME
    assert updated.method is DetectionMethod.MANUAL
    assert updated.placeholder_token == "[NOTER_1]"
    assert updated.recommended_strategy is TransformationStrategy.PLACEHOLDER


def test_reclassify_moves_every_copy_of_the_word_onto_the_new_tag() -> None:
    complainant = _person("Eda Kurt", EntityType.COMPLAINANT_NAME, 0, "COMPLAINANT")
    repeat = _person("Eda Kurt", EntityType.PERSON_NAME, 15)
    repeat = repeat.model_copy(update={"resolved_entity_id": "other-eda"})
    complainant = complainant.model_copy(update={"resolved_entity_id": "eda"})
    stamped = stamp_placeholder_tokens([complainant, repeat], "tr")
    assert {item.placeholder_token for item in stamped} == {"[MÜŞTEKİ_1]"}
    job = Job(
        id="job-reclass",
        directory=Path("."),
        source_path=Path("synthetic.txt"),
        document_kind=DocumentKind.DOCX,
        created_at=0,
        source_document_type=SourceDocumentType.DOCX,
        workspace_mode=WorkspaceMode.TEXT,
        locale="tr",
        requested_document_language="tr",
        analysis=AnalysisResponse(
            job_id="job-reclass",
            file_name="synthetic.docx",
            document_kind=DocumentKind.DOCX,
            source_document_type=SourceDocumentType.DOCX,
            workspace_mode=WorkspaceMode.TEXT,
            document_hash="synthetic",
            page_count=1,
            text="Eda Kurt dedi. Eda Kurt sustu.",
            entities=stamped,
            detectors_executed=["test"],
            profile=PrivacyProfile.KVKK,
            detection_mode=DetectionMode.RULES_ONLY,
            analysis_status=AnalysisStatus.COMPLETE,
            local_ner_status=LocalNERStatus.NOT_REQUESTED,
            requested_document_language="tr",
            resolved_document_language="tr",
        ),
    )
    reclassify_entities(job, [stamped[0].id], EntityType.ACCUSED_NAME)
    assert job.analysis is not None
    assert {item.type for item in job.analysis.entities} == {EntityType.ACCUSED_NAME}
    assert {item.placeholder_token for item in job.analysis.entities} == {"[SANIK_1]"}
    assert {item.role for item in job.analysis.entities} == {"ACCUSED"}
    preview = preview_transformations(job, RedactionRequest(decisions=[], locale="tr"))
    assert "[SANIK_1]" in preview.text
    assert "MÜŞTEKİ" not in preview.text
    assert set(preview.placeholder_tokens.values()) == {"[SANIK_1]"}


def test_reclassified_numbered_tags_keep_an_index_when_preview_uses_another_method() -> None:
    """Two different spans changed to sanık stay [SANIK_1] and [SANIK_2].

    The same index is kept for every other numbered family. A preview that
    masks those spans with black redaction must not rewrite the tag as [SANIK].
    Date stays unnumbered.
    """
    text = "Eda Kurt. Lale Demir. Kemal Yurt. 01.01.2020"
    eda = _person("Eda Kurt", EntityType.COMPLAINANT_NAME, text.index("Eda Kurt"), "COMPLAINANT")
    lale = _person("Lale Demir", EntityType.WITNESS_NAME, text.index("Lale Demir"), "WITNESS")
    kemal = _person("Kemal Yurt", EntityType.PERSON_NAME, text.index("Kemal Yurt"))
    when = EntityCandidate(
        id="date-1",
        text="01.01.2020",
        type=EntityType.DATE,
        start=text.index("01.01.2020"),
        end=text.index("01.01.2020") + len("01.01.2020"),
        page=0,
        detector="test",
        method=DetectionMethod.DETERMINISTIC,
    )
    job = Job(
        id="job-numbered-reclass",
        directory=Path("."),
        source_path=Path("synthetic.txt"),
        document_kind=DocumentKind.DOCX,
        created_at=0,
        source_document_type=SourceDocumentType.DOCX,
        workspace_mode=WorkspaceMode.TEXT,
        locale="tr",
        requested_document_language="tr",
        analysis=AnalysisResponse(
            job_id="job-numbered-reclass",
            file_name="synthetic.docx",
            document_kind=DocumentKind.DOCX,
            source_document_type=SourceDocumentType.DOCX,
            workspace_mode=WorkspaceMode.TEXT,
            document_hash="synthetic",
            page_count=1,
            text=text,
            entities=[eda, lale, kemal, when],
            detectors_executed=["test"],
            profile=PrivacyProfile.KVKK,
            detection_mode=DetectionMode.RULES_ONLY,
            analysis_status=AnalysisStatus.COMPLETE,
            local_ner_status=LocalNERStatus.NOT_REQUESTED,
            requested_document_language="tr",
            resolved_document_language="tr",
        ),
    )
    reclassify_entities(job, [eda.id], EntityType.ACCUSED_NAME)
    reclassify_entities(job, [lale.id], EntityType.ACCUSED_NAME)
    reclassify_entities(job, [kemal.id], EntityType.LAWYER_NAME)
    assert job.analysis is not None
    by_text = {item.text: item for item in job.analysis.entities}
    preview = preview_transformations(
        job,
        RedactionRequest(
            decisions=[
                RedactionDecision(
                    entity_id=item.id,
                    action="REDACT",
                    strategy=TransformationStrategy.REDACT,
                )
                for item in job.analysis.entities
            ],
            category_defaults=[],
            locale="tr",
        ),
    )
    assert preview.placeholder_tokens[by_text["Eda Kurt"].id] == "[SANIK_1]"
    assert preview.placeholder_tokens[by_text["Lale Demir"].id] == "[SANIK_2]"
    assert preview.placeholder_tokens[by_text["Kemal Yurt"].id] == "[AVUKAT_1]"
    assert preview.placeholder_tokens[by_text["01.01.2020"].id] == "[TARİH]"


def test_every_workspace_uses_the_shared_detection_pipeline() -> None:
    assert "_build_analysis(" in inspect.getsource(analyze_pdf)
    assert "_build_analysis(" in inspect.getsource(analyze_textual_document)
    assert pdf_transformation_route(DocumentKind.PDF, WorkspaceMode.DOCUMENT, rebuild=False) == "secure_pdf"
    assert pdf_transformation_route(DocumentKind.PDF, WorkspaceMode.TEXT, rebuild=False) == "text_copy"
    assert pdf_transformation_route(DocumentKind.DOCX, WorkspaceMode.TEXT, rebuild=False) == "text_copy"
    assert pdf_transformation_route(DocumentKind.UDF, WorkspaceMode.TEXT, rebuild=False) == "text_copy"
    found = _scan(ROSTER, "tr")
    assert _has(found, EntityType.ACCUSED_NAME, "MEHMET ÇELİK")
    assert _has(found, EntityType.NOTARY_NAME, "ECE AYDIN")


def test_claimant_name_repeats_and_request_captions_are_not_names() -> None:
    text = """
TESPİT İSTEYEN
DAVACI : AYŞE YILMAZ - T.C. Kimlik No: 10000000000
Kuzeykent Mah. 3141 Sk. No: 1 Su Vadi Konutları A Blok Kat: 10

DELİL TESPİTİ İSTEYEN DAVACI
AYŞE YILMAZ
EKLER:
1. Fatura fotokopisi

HACİZ İSTEYEN : KEREM AKSOY
"""
    found = assign_resolved_entities(_scan(text, "tr"))
    claimants = [
        item
        for item in found
        if item.type is EntityType.CLAIMANT_NAME and "YILMAZ" in item.text.upper()
    ]
    assert len(claimants) >= 2
    assert len({item.resolved_entity_id for item in claimants}) == 1
    assert all("EKLER" not in item.text.upper() for item in claimants)
    banned = ("tespit isteyen", "delil tespiti isteyen", "delil tespiti")
    for item in found:
        folded = item.text.casefold()
        assert not any(phrase in folded for phrase in banned)
    assert _has(found, EntityType.CLAIMANT_NAME, "KEREM AKSOY")


def test_complainant_and_accused_keep_their_own_tags() -> None:
    complainant = _person("Lale Demir", EntityType.COMPLAINANT_NAME, 0, "COMPLAINANT")
    accused = _person("Tarık Koç", EntityType.ACCUSED_NAME, 40, "ACCUSED")
    stamped = stamp_placeholder_tokens([complainant, accused], "tr")
    assert stamped[0].type is EntityType.COMPLAINANT_NAME
    assert stamped[1].type is EntityType.ACCUSED_NAME
    assert stamped[0].placeholder_token == "[MÜŞTEKİ_1]"
    assert stamped[1].placeholder_token == "[SANIK_1]"

    shared = stamp_placeholder_tokens(
        [
            _person("Eda Kurt", EntityType.COMPLAINANT_NAME, 0, "COMPLAINANT"),
            _person("Eda Kurt", EntityType.ACCUSED_NAME, 20, "ACCUSED"),
            _person("Eda Kurt", EntityType.PERSON_NAME, 40),
        ],
        "tr",
    )
    assert {item.type for item in shared} == {EntityType.COMPLAINANT_ACCUSED_NAME}
    assert {item.placeholder_token for item in shared} == {"[MÜŞTEKİ_SANIK_1]"}

    found = _scan(
        "MÜŞTEKİ : LALE DEMİR\n"
        "Şikâyetçi: LALE DEMİR\n"
        "SANIK : TARIK KOÇ\n"
        "MÜŞTEKİ/SANIK : SEDA AKIN\n"
        "Müşteki-sanık Seda Akın beyan etti.\n",
        "tr",
    )
    assert _has(found, EntityType.COMPLAINANT_NAME, "LALE DEMİR")
    assert _has(found, EntityType.ACCUSED_NAME, "TARIK KOÇ")
    assert _has(found, EntityType.COMPLAINANT_ACCUSED_NAME, "SEDA AKIN")
    assert not _has(found, EntityType.COMPLAINANT_NAME, "SEDA AKIN")
    assert not _has(found, EntityType.ACCUSED_NAME, "SEDA AKIN")


def test_legal_prose_beside_a_role_word_is_not_a_person_name() -> None:
    found = _scan(
        "5- ŞÜPHEDEN SANIK YARARLANIR İLKESİ GEREĞİNCE MÜVEKKİL HAKKINDA "
        "MAHKUMİYET HÜKMÜ KURULAMAZ. "
        "HEM TEKNİK DELİLLERLE HEM TANIK ANLATIMLARIYLA SABİT HALE GELDİĞİNDEN "
        "CEZALANDIRILMASI GEREKİR. "
        "DOSYA KAPSAMINDAKİ CD ÇÖZÜM TUTANAĞI VE TANIK BEYANLARI "
        "SALDIRININ KAYNAĞINI GÖSTERİR.\n"
        "TANIK LALE DEMİR ANLATIMLARIYLA DOĞRULADI.\n"
        "SANIK : AYŞE YILMAZ\n",
        "tr",
    )
    surfaces = {_fold(item.text) for item in found}
    for phrase in (
        "yararlanir",
        "ilkesi",
        "geregince",
        "teknik",
        "delil",
        "anlatim",
        "tutanak",
        "cozum",
        "sabit",
        "hale",
    ):
        assert not any(phrase in surface for surface in surfaces), phrase
    assert _has(found, EntityType.ACCUSED_NAME, "AYŞE YILMAZ")
    assert _has(found, EntityType.WITNESS_NAME, "LALE DEMİR")


def test_merging_a_short_name_with_the_full_name_keeps_one_tag() -> None:
    full = _person("Eda Kurt", EntityType.COMPLAINANT_ACCUSED_NAME, 0, "COMPLAINANT_ACCUSED")
    short = _person("Eda", EntityType.COMPLAINANT_ACCUSED_NAME, 20, "COMPLAINANT_ACCUSED")
    stray = _person("Eda Kurt", EntityType.WITNESS_NAME, 40, "WITNESS")
    full = full.model_copy(update={"resolved_entity_id": "eda-full"})
    stray = stray.model_copy(update={"resolved_entity_id": "eda-full"})
    short = short.model_copy(update={"resolved_entity_id": "eda-short"})
    job = Job(
        id="job-merge-short-name",
        directory=Path("."),
        source_path=Path("synthetic.txt"),
        document_kind=DocumentKind.DOCX,
        created_at=0,
        source_document_type=SourceDocumentType.DOCX,
        workspace_mode=WorkspaceMode.TEXT,
        locale="tr",
        requested_document_language="tr",
        analysis=AnalysisResponse(
            job_id="job-merge-short-name",
            file_name="synthetic.docx",
            document_kind=DocumentKind.DOCX,
            source_document_type=SourceDocumentType.DOCX,
            workspace_mode=WorkspaceMode.TEXT,
            document_hash="synthetic",
            page_count=1,
            text="Eda Kurt dedi. Eda sustu. Eda Kurt dinledi.",
            entities=[full, short, stray],
            detectors_executed=["test"],
            profile=PrivacyProfile.KVKK,
            detection_mode=DetectionMode.RULES_ONLY,
            analysis_status=AnalysisStatus.COMPLETE,
            local_ner_status=LocalNERStatus.NOT_REQUESTED,
            requested_document_language="tr",
            resolved_document_language="tr",
        ),
    )
    confirm_entity_merge(job, [full.id, short.id])
    assert job.analysis is not None
    assert {item.type for item in job.analysis.entities} == {EntityType.COMPLAINANT_ACCUSED_NAME}
    assert {item.placeholder_token for item in job.analysis.entities} == {"[MÜŞTEKİ_SANIK_1]"}
