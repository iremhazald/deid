"""Synthetic prosecutor and court-clerk role labels.

Names below are invented. Detection stays on the shared normalized-text
pipeline used by PDF, DOCX, and UYAP UDF jobs.
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
    SourceDocumentType,
    TransformationStrategy,
    WorkspaceMode,
)
from app.services.jobs import Job
from app.services.pipeline import analyze_pdf, analyze_textual_document
from app.transforms.catalog import allowed_strategies, build_catalog, recommended_strategy
from app.transforms.entity_merge import reclassify_entities
from app.transforms.resolution import assign_resolved_entities
from app.transforms.tag_registry import stamp_placeholder_tokens, tag_locale_for_document
from app.transforms.tag_taxonomy import resolve_person_family, spec_for

CLERK_TAG = "KAT\u0130P"
PERSON_STRATEGIES = {
    TransformationStrategy.REDACT,
    TransformationStrategy.PLACEHOLDER,
    TransformationStrategy.INITIALS,
    TransformationStrategy.KEEP,
}


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


def test_schema_accepts_both_labels() -> None:
    assert EntityType("PROSECUTOR_NAME") is EntityType.PROSECUTOR_NAME
    assert EntityType("COURT_CLERK_NAME") is EntityType.COURT_CLERK_NAME
    request = ReclassifyRequest(entity_ids=["span-1"], entity_type=EntityType.COURT_CLERK_NAME)
    assert request.entity_type is EntityType.COURT_CLERK_NAME

    catalog = build_catalog()
    categories = {item["category"]: item for item in catalog["categories"]}
    for label in ("PROSECUTOR_NAME", "COURT_CLERK_NAME"):
        assert label in categories
        assert set(categories[label]["allowed_strategies"]) == {item.value for item in PERSON_STRATEGIES}
        assert "PARTIAL_MASK" not in categories[label]["allowed_strategies"]
        assert categories[label]["recommended_strategy"] == "PLACEHOLDER"
    legal = next(group["types"] for group in catalog["scan_scope_groups"] if group["id"] == "legal")
    assert "PROSECUTOR_NAME" in legal
    assert "COURT_CLERK_NAME" in legal
    assert "JUDGE_NAME" in legal


def test_person_transformations_match_existing_name_policy() -> None:
    for entity_type in (
        EntityType.PROSECUTOR_NAME,
        EntityType.COURT_CLERK_NAME,
        EntityType.JUDGE_NAME,
        EntityType.LAWYER_NAME,
    ):
        assert set(allowed_strategies(entity_type)) == PERSON_STRATEGIES
        assert recommended_strategy(entity_type) is TransformationStrategy.PLACEHOLDER


def test_turkish_court_officer_roster_assigns_role_labels() -> None:
    text = (
        "BAŞKAN              : HASAN IŞIK\n"
        "ÜYE                 : MEHMET DEMİRCİOĞLU\n"
        "CUMHURİYET SAVCISI  : ENES DEMİR\n"
        "KÂTİP               : NİLAY GÜLEÇ\n"
    )
    found = _scan(text, "tr")
    assert _has(found, EntityType.JUDGE_NAME, "HASAN IŞIK")
    assert _has(found, EntityType.JUDGE_NAME, "MEHMET DEMİRCİOĞLU")
    assert _has(found, EntityType.PROSECUTOR_NAME, "ENES DEMİR")
    assert _has(found, EntityType.COURT_CLERK_NAME, "NİLAY GÜLEÇ")
    for role in ("BAŞKAN", "ÜYE", "CUMHURİYET SAVCISI", "KÂTİP", "SAVCISI", "KATİP"):
        assert not any(_fold(item.text) == _fold(role) for item in found)


def test_turkish_role_layouts_case_colon_space_and_linebreak() -> None:
    samples = [
        ("Cumhuriyet Savcısı: Enes Demir", EntityType.PROSECUTOR_NAME, "Enes Demir"),
        ("C. Savcısı Enes Demir", EntityType.PROSECUTOR_NAME, "Enes Demir"),
        ("Duruşma Savcısı : Kerem Aslan", EntityType.PROSECUTOR_NAME, "Kerem Aslan"),
        ("SAVCI    SELİN AKSOY", EntityType.PROSECUTOR_NAME, "SELİN AKSOY"),
        ("Savcı\nEbru Tan", EntityType.PROSECUTOR_NAME, "Ebru Tan"),
        ("Zabıt Kâtibi: Nilay Güleç", EntityType.COURT_CLERK_NAME, "Nilay Güleç"),
        ("Zabıt Katibi Nilay Güleç", EntityType.COURT_CLERK_NAME, "Nilay Güleç"),
        ("Mahkeme Kâtibi : Sevgi Er", EntityType.COURT_CLERK_NAME, "Sevgi Er"),
        ("Mahkeme Katibi Sevgi Er", EntityType.COURT_CLERK_NAME, "Sevgi Er"),
        ("KATİP\nNİLAY GÜLEÇ", EntityType.COURT_CLERK_NAME, "NİLAY GÜLEÇ"),
        ("KÂTİP : NİLAY GÜLEÇ", EntityType.COURT_CLERK_NAME, "NİLAY GÜLEÇ"),
    ]
    for text, entity_type, name in samples:
        found = _scan(text, "tr")
        assert _has(found, entity_type, name), (text, _of_type(found, entity_type))


def test_registry_number_stays_a_professional_id() -> None:
    text = (
        "CUMHURİYET SAVCISI : ENES DEMİR 376901\n"
        "KÂTİP : NİLAY GÜLEÇ 284513\n"
    )
    found = _scan(text, "tr")
    assert _has(found, EntityType.PROSECUTOR_NAME, "ENES DEMİR")
    assert _has(found, EntityType.COURT_CLERK_NAME, "NİLAY GÜLEÇ")
    registries = _of_type(found, EntityType.PROFESSIONAL_ID)
    assert "376901" in registries
    assert "284513" in registries


def test_role_keyword_without_a_name_is_not_a_person() -> None:
    text = (
        "CUMHURİYET SAVCISI\n"
        "KÂTİP\n"
        "Savcı mütalaayı sundu.\n"
        "Kâtip tutanağı hazırladı.\n"
        "Cumhuriyet savcısının katılımı ile duruşma yapılmıştır.\n"
        "Mahkeme katibi kalemi kapattı.\n"
    )
    found = _scan(text, "tr")
    assert _of_type(found, EntityType.PROSECUTOR_NAME) == []
    assert _of_type(found, EntityType.COURT_CLERK_NAME) == []


def test_english_role_names_and_generic_mentions() -> None:
    text = (
        "Public Prosecutor: Elena Marlow\n"
        "State Prosecutor Marcus Hale appeared for the state.\n"
        "Prosecutor Elena Marlow addressed the court.\n"
        "Court Clerk Helen Ward certified the record.\n"
        "Clerk of Court\n"
        "Nora Blake\n"
        "Judge Hart delivered the ruling.\n"
    )
    found = _scan(text, "en")
    assert _has(found, EntityType.PROSECUTOR_NAME, "Elena Marlow")
    assert _has(found, EntityType.PROSECUTOR_NAME, "Marcus Hale")
    assert _has(found, EntityType.COURT_CLERK_NAME, "Helen Ward")
    assert _has(found, EntityType.COURT_CLERK_NAME, "Nora Blake")
    assert _has(found, EntityType.JUDGE_NAME, "Hart") or _has(found, EntityType.JUDGE_NAME, "Judge Hart")
    narrative = (
        "The prosecutor submitted the indictment.\n"
        "A clerk of court keeps the official record.\n"
        "The public prosecutor addressed the bench.\n"
    )
    plain = _scan(narrative, "en")
    assert _of_type(plain, EntityType.PROSECUTOR_NAME) == []
    assert _of_type(plain, EntityType.COURT_CLERK_NAME) == []


def test_existing_party_and_counsel_roles_stay_in_place() -> None:
    # Separate documents. A following line in one party block is existing
    # continuation behavior, not a new role assignment.
    turkish = [
        ("DAVACI : LALE ÖZTÜRK", EntityType.CLAIMANT_NAME, "LALE ÖZTÜRK"),
        ("SANIK : KEMAL YURT", EntityType.ACCUSED_NAME, "KEMAL YURT"),
        ("DAVALI : KEMAL YURT", EntityType.DEFENDANT_NAME, "KEMAL YURT"),
        ("Tanık Selim Kaya duruşmada dinlendi.", EntityType.WITNESS_NAME, "Selim Kaya"),
        ("Av. Kerem Aslan hazır bulundu.", EntityType.LAWYER_NAME, "Kerem Aslan"),
        ("Bilirkişi Deniz Aksoy raporunu sundu.", EntityType.EXPERT_NAME, "Deniz Aksoy"),
    ]
    for text, entity_type, name in turkish:
        found = _scan(text, "tr")
        assert any(item.type == entity_type and name in item.text for item in found), (
            text,
            [(item.type.value, item.text) for item in found],
        )

    english = [
        ("Judge Hart granted the application.", EntityType.JUDGE_NAME, "Hart"),
        ("Counsel Owen Blake appeared.", EntityType.LAWYER_NAME, "Owen Blake"),
        ("Witness Mara Quinn testified.", EntityType.PERSON_NAME, "Mara Quinn"),
        ("Expert Witness Lena Ortiz reported.", EntityType.EXPERT_NAME, "Lena Ortiz"),
    ]
    for text, entity_type, name in english:
        found = _scan(text, "en")
        assert any(item.type == entity_type and name in item.text for item in found), (
            text,
            [(item.type.value, item.text) for item in found],
        )


def test_placeholders_numbering_locale_and_conflicts() -> None:
    prosecutor = spec_for(EntityType.PROSECUTOR_NAME)
    clerk = spec_for(EntityType.COURT_CLERK_NAME)
    assert prosecutor.labels_tr == "SAVCI"
    assert prosecutor.labels_en == "PROSECUTOR"
    assert clerk.labels_tr == CLERK_TAG
    assert clerk.labels_en == "COURT_CLERK"
    assert prosecutor.example_tr == "[SAVCI_1]"
    assert clerk.example_tr == f"[{CLERK_TAG}_1]"
    assert prosecutor.example_en == "[PROSECUTOR_1]"
    assert clerk.example_en == "[COURT_CLERK_1]"

    enes = _person("Enes Demir", EntityType.PROSECUTOR_NAME, 0, "PROSECUTOR")
    enes_again = _person("Enes Demir", EntityType.PERSON_NAME, 40)
    kerem = _person("Kerem Aslan", EntityType.PROSECUTOR_NAME, 80, "PROSECUTOR")
    nilay = _person("Nilay Güleç", EntityType.COURT_CLERK_NAME, 120, "CLERK")
    stamped = stamp_placeholder_tokens([enes, enes_again, kerem, nilay], "tr")
    assert stamped[0].placeholder_token == stamped[1].placeholder_token == "[SAVCI_1]"
    assert stamped[2].placeholder_token == "[SAVCI_2]"
    assert stamped[3].placeholder_token == f"[{CLERK_TAG}_1]"

    english = stamp_placeholder_tokens([enes, nilay], "en")
    assert english[0].placeholder_token == "[PROSECUTOR_1]"
    assert english[1].placeholder_token == "[COURT_CLERK_1]"
    assert tag_locale_for_document(resolved_document_language="en", job_locale="tr") == "en"
    assert tag_locale_for_document(resolved_document_language="tr", job_locale="en") == "tr"

    resolved = assign_resolved_entities([enes, enes_again, kerem, nilay])
    assert resolved[0].resolved_entity_id != resolved[2].resolved_entity_id
    assert resolved[0].resolved_entity_id != resolved[3].resolved_entity_id

    conflict = stamp_placeholder_tokens(
        [
            _person("Hasan Işık", EntityType.JUDGE_NAME, 0, "JUDGE"),
            _person("Hasan Işık", EntityType.PROSECUTOR_NAME, 20, "PROSECUTOR"),
        ],
        "tr",
    )
    assert resolve_person_family({EntityType.JUDGE_NAME, EntityType.PROSECUTOR_NAME}) == "PERSON"
    assert conflict[0].placeholder_token == conflict[1].placeholder_token == "[KİŞİ_1]"


def test_manual_finding_and_reclassification() -> None:
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
    reclassify_entities(job, ["manual-1"], EntityType.PROSECUTOR_NAME)
    assert job.analysis is not None
    prosecutor = job.analysis.entities[0]
    assert prosecutor.type is EntityType.PROSECUTOR_NAME
    assert prosecutor.method is DetectionMethod.MANUAL
    assert prosecutor.placeholder_token == "[SAVCI_1]"
    assert prosecutor.recommended_strategy is TransformationStrategy.PLACEHOLDER

    reclassify_entities(job, ["manual-1"], EntityType.COURT_CLERK_NAME)
    clerk = job.analysis.entities[0]
    assert clerk.type is EntityType.COURT_CLERK_NAME
    assert clerk.placeholder_token == f"[{CLERK_TAG}_1]"


def test_role_detection_is_shared_by_every_document_workspace() -> None:
    """PDF document mode and PDF/DOCX/UDF text mode share normalized-text detection."""
    assert "_build_analysis(" in inspect.getsource(analyze_pdf)
    assert "_build_analysis(" in inspect.getsource(analyze_textual_document)
    text = "CUMHURİYET SAVCISI : ENES DEMİR\nKÂTİP : NİLAY GÜLEÇ\n"
    found = _scan(text, "tr")
    assert _has(found, EntityType.PROSECUTOR_NAME, "ENES DEMİR")
    assert _has(found, EntityType.COURT_CLERK_NAME, "NİLAY GÜLEÇ")
