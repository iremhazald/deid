"""A petition title is not the small running header from the top centimetre."""

from pathlib import Path

from docx import Document
from docx.shared import Pt

from app.detectors.legal.court import parse_courts, promote_running_header_courts
from app.detectors.registry import PageText
from app.services.document_processing import extract_docx_text
from app.services.udf_package import _text_from_content_xml


TITLE = "MERSİN 23. ASLİYE CEZA MAHKEMESİ'NE\nDOSYA NO : 2026/111 Esas\nKONU : kayıt silme"
SMALL = "MERSİN 8. ASLİYE CEZA MAHKEMESİ"


def _page(text: str) -> PageText:
    return PageText(page=0, text=text, document_offset=0)


def test_petition_title_is_not_a_running_header() -> None:
    found = parse_courts(_page(TITLE))
    courts = [item for item in found if "MAHKEMESİ" in item.text]
    assert courts
    assert all(item.attributes.get("mask_scope") != "header_line" for item in courts)
    assert all("DOSYA NO" not in item.text for item in courts)


def test_footnote_sized_court_can_be_a_running_header() -> None:
    text = f"{SMALL}\n{TITLE}"
    found = parse_courts(_page(text))
    promote_running_header_courts(found, [(0, len(SMALL))])
    small = next(item for item in found if item.text.startswith("MERSİN 8."))
    title = next(item for item in found if "23." in item.text)
    assert small.attributes.get("mask_scope") == "header_line"
    assert title.attributes.get("mask_scope") != "header_line"
    assert "DOSYA NO" not in title.text


def test_udf_title_without_a_small_font_is_not_a_header_span() -> None:
    source = TITLE
    title_end = TITLE.index("\n")
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<template format_id="1.8">
  <content><![CDATA[{source}]]></content>
  <elements>
    <paragraph Alignment="1">
      <content startOffset="0" length="{title_end}" bold="true"/>
    </paragraph>
    <paragraph>
      <content startOffset="{title_end + 1}" length="{len(source) - title_end - 1}"/>
    </paragraph>
  </elements>
  <styles>
    <style name="hvl-default" family="Times New Roman" size="12" description="Gövde"/>
  </styles>
</template>
""".encode()
    text, _warning, spans = _text_from_content_xml(payload)
    assert "DOSYA NO" in text
    assert spans == ()


def test_udf_footnote_font_is_a_header_span() -> None:
    source = f"{SMALL}\n{TITLE}"
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<template format_id="1.8">
  <content><![CDATA[{source}]]></content>
  <elements>
    <paragraph>
      <content startOffset="0" length="{len(SMALL)}" size="8"/>
    </paragraph>
    <paragraph>
      <content startOffset="{len(SMALL) + 1}" length="{len(source) - len(SMALL) - 1}" size="12"/>
    </paragraph>
  </elements>
  <styles>
    <style name="hvl-default" family="Times New Roman" size="12" description="Gövde"/>
  </styles>
</template>
""".encode()
    text, _warning, spans = _text_from_content_xml(payload)
    assert spans == ((0, len(SMALL)),)
    found = parse_courts(_page(text))
    promote_running_header_courts(found, list(spans))
    assert any(
        item.attributes.get("mask_scope") == "header_line" and item.text.startswith("MERSİN 8.")
        for item in found
    )
    assert all(
        item.attributes.get("mask_scope") != "header_line"
        for item in found
        if "23." in item.text
    )


def test_word_header_story_is_a_running_header_and_the_title_is_not(tmp_path: Path) -> None:
    document = Document()
    document.sections[0].header.paragraphs[0].text = SMALL
    title = document.add_paragraph()
    title_run = title.add_run("MERSİN 23. ASLİYE CEZA MAHKEMESİ'NE")
    title_run.bold = True
    title_run.font.size = Pt(14)
    body = document.add_paragraph()
    body_run = body.add_run(
        "Bu gövde metni on iki punto ile yazılmıştır ve başlıktan ayrı durur."
    )
    body_run.font.size = Pt(12)
    path = tmp_path / "petition.docx"
    document.save(path)
    extracted = extract_docx_text(path)
    assert extracted.running_header_spans
    start, end = extracted.running_header_spans[0]
    assert extracted.text[start:end] == SMALL
    title_at = extracted.text.index("MERSİN 23.")
    assert all(not (span_start <= title_at < span_end) for span_start, span_end in extracted.running_header_spans)
