"""Conservative Turkish person-name morphology for legal parsers."""

from __future__ import annotations

import re

from app.detectors.gazetteers import TURKISH_CITIES, TURKISH_DISTRICTS
from app.detectors.textutil import fold_tr, fold_tr_identity

# 2–4 tokens: proper-name casing or full uppercase. Optional apostrophe suffix.
_TOKEN = (
    r"[A-ZÇĞİÖŞÜÂÎÛ]"
    r"(?:[A-ZÇĞİÖŞÜÂÎÛ]{1,}|[a-zçğıöşüâîû]{1,})"
    r"(?:['’`´ʼ′][A-Za-zÇĞİÖŞÜçğıöşüâîû]+)?"
)
_INITIAL = r"[A-ZÇĞİÖŞÜÂÎÛ]\."
# Token without a case suffix, so 'in / 'nin can sit after the name.
BARE_NAME_TOKEN = (
    r"[A-ZÇĞİÖŞÜÂÎÛ]"
    r"(?:[A-ZÇĞİÖŞÜÂÎÛ]{1,}|[a-zçğıöşüâîû]{1,})"
)
NAME_TOKEN = rf"(?:{_TOKEN}|{_INITIAL})"
# Same-line names stay space-separated. A single newline is only used to join a
# wrapped given name + surname (İPEK / OKYAY), not to swallow the next label.
_NAME_GAP = r"[ \t\u00a0\u00ad\u2000-\u200d\u202f]{1,40}"
_WRAP_GAP = r"\n[ \t]*"
PERSON_NAME_RE = re.compile(
    rf"(?<![\wÇĞİÖŞÜçğıöşü])("
    rf"{NAME_TOKEN}(?:{_NAME_GAP}{NAME_TOKEN}){{1,3}}"
    rf"|{NAME_TOKEN}{_WRAP_GAP}{NAME_TOKEN}"
    rf")(?![\wÇĞİÖŞÜçğıöşü])"
)

# Possessive / case leftovers commonly attached in running text.
_POSSESSIVE = re.compile(
    r"^(.+?)['’`´ʼ′](in|ın|un|ün|nin|nın|nun|nün|e|a|ye|ya|i|ı|u|ü)$",
    re.IGNORECASE,
)

_NAME_STOP = frozenset(
    {
        "ve",
        "ile",
        "olan",
        "olarak",
        "adına",
        "adina",
        "kayıtlı",
        "kayitli",
        "nezdinde",
        "ibana",
        "iban",
        "anlaştıkları",
        "anlastiklari",
        "ait",
        "oğlu",
        "oglu",
        "kızı",
        "kizi",
        "doğumlu",
        "dogumlu",
        "mahallesi",
        "mah",
        "caddesi",
        "cad",
        "street",
        "road",
        "avenue",
        "lane",
        "drive",
        "boulevard",
        "court",
        "tribunal",
        "limited",
        "incorporated",
        "corporation",
        "ministry",
        "department",
        "sokağı",
        "sokagi",
        "sok",
        "bulvarı",
        "bulvari",
        "no",
        "kat",
        "daire",
        "adres",
        "tel",
        "telefon",
        "tc",
        "t.c",
        "kimlik",
        "tarih",
        "hakkında",
        "hakkinda",
        "karar",
        "kararı",
        "karari",
        "gerekçe",
        "gerekce",
        "hüküm",
        "hukum",
        "esas",
        "dosya",
        "mahkeme",
        "savcılık",
        "savcilik",
        "cumhuriyet",
        "bölge",
        "bolge",
        "asliye",
        "ağır",
        "agir",
        "sulh",
        "icra",
        "türkiye",
        "turkiye",
        "ankara",
        "istanbul",
        "izmir",
        "ocak",
        "şubat",
        "subat",
        "mart",
        "nisan",
        "mayıs",
        "mayis",
        "haziran",
        "temmuz",
        "ağustos",
        "agustos",
        "eylül",
        "eylul",
        "ekim",
        "kasım",
        "kasim",
        "aralık",
        "aralik",
        "pazartesi",
        "salı",
        "sali",
        "çarşamba",
        "carsamba",
        "perşembe",
        "persembe",
        "cuma",
        "cumartesi",
        "pazar",
        "beyanında",
        "beyaninda",
        "beyanı",
        "beyani",
        "beyan",
        "ifadesinde",
        "ifadesi",
        "ifade",
        "karşı",
        "karsi",
        "taraf",
        "savunmasında",
        "savunması",
        "savunmasi",
        "savunma",
        "anlatımında",
        "anlatiminda",
        "müdafii",
        "mudafii",
        "mütalaası",
        "mutaalasi",
        "av",
        "avukat",
        "hakim",
        "hâkim",
        "yargıç",
        "yargic",
        "sanık",
        "sanik",
        "davacı",
        "davaci",
        "davalı",
        "davali",
        "tanık",
        "tanik",
        "katılan",
        "katilan",
        "müşteki",
        "musteki",
        "mağdur",
        "magdur",
        "vekil",
        "müdafi",
        "mudafi",
        "şahıs",
        "sahis",
        "kişi",
        "kisi",
        "iban",
        "gsm",
        "tl",
        "try",
        "ip",
        "port",
        "portu",
        "para",
        "ceza",
        "cezası",
        "cezasi",
        "cezalandırılmasına",
        "cezalandirilmasina",
        "adli",
        "takdiren",
        "asgari",
        "suç",
        "suc",
        "yeri",
        "tarihi",
        "suretiyle",
        "dolandırıcılık",
        "dolandiricilik",
        "kredi",
        "araç",
        "arac",
        "kurum",
        "kurumu",
        "kurumlar",
        "kurumların",
        "kurumlarin",
        "bilgi",
        "bilgilerini",
        "numara",
        "numaraları",
        "numaralari",
        "hatları",
        "hatlari",
        "hatlarının",
        "hatlarinin",
        "hattı",
        "hatti",
        "olay",
        "soruşturma",
        "sorusturma",
        "iddianame",
        "hüküm",
        "hukum",
        "ago",
        "bam",
        "cmk",
        "tck",
        "sgk",
        "egm",
        "segbis",
        "uyap",
        "uets",
        "müvekkil",
        "muvekkil",
        "müvekkilim",
        "muvekkilim",
        "şirket",
        "sirket",
        "özelinde",
        "ozelinde",
        "fabrika",
        "fabrikası",
        "konu",
        "konusu",
        "tebliğ",
        "teblig",
        "tebliğe",
        "teblige",
        "tebellüğ",
        "tebellug",
        "tebellüğü",
        "tebellugu",
        "hukuku",
        "hukukuna",
        "fabrikasi",
        "müdürlük",
        "mudurluk",
        "müdürlüğü",
        "mudurlugu",
        "şeflik",
        "seflik",
        "şefliği",
        "sefligi",
        "şefi",
        "sefi",
        "memurluk",
        "memurluğu",
        "memurlugu",
        "paketleme",
        "üretim",
        "uretim",
        "planlama",
        "malzeme",
        "kimyasal",
        "kimyasallar",
        "nöbetçi",
        "nobetci",
        "hâkimliği",
        "hakimligi",
        "hâkimliğine",
        "hakimligine",
        "mahkemesi",
    }
)
_LEGAL_LABELS = {
    fold_tr_identity(item)
    for item in (
        "suç yeri",
        "suc yeri",
        "suç tarihi",
        "suc tarihi",
        "olay yeri",
        "olay tarihi",
        "karar tarihi",
        "duruşma tarihi",
        "durusma tarihi",
        "suçun işlendiği yer",
        "sucun islendigi yer",
        "kredi kurumlarının araç",
        "kredi kurumlarinin arac",
        "suretiyle dolandırıcılık",
        "suretiyle dolandiricilik",
        "konu",
        "konusu",
        "tebliğ",
        "teblig",
        "tebliğe",
        "teblige",
        "tebellüğ",
        "tebellug",
        "tebellüğü",
        "tebellugu",
        "iş hukuku",
        "is hukuku",
        "hukuku",
        "hukukuna",
        "uets",
    )
}
_NAME_STOP = {fold_tr_identity(item) for item in _NAME_STOP} | {
    fold_tr(item) for item in _NAME_STOP
}

_PLACE_FOLD = {fold_tr(name) for name in TURKISH_CITIES | TURKISH_DISTRICTS} | {
    fold_tr_identity(name) for name in TURKISH_CITIES | TURKISH_DISTRICTS
}

# Inflected prose that is never a given name / surname.
_INFLECTED_SUFFIXES = (
    "larinda",
    "lerinde",
    "larini",
    "lerini",
    "lardan",
    "lerden",
    "larin",
    "lerin",
    "larda",
    "lerde",
    "lari",
    "leri",
    "masina",
    "mesine",
    "masi",
    "mesi",
    "digini",
    "digi",
    "makta",
    "mekte",
    "lüğü",
    "lığı",
    "liği",
    "luğu",
    "lugu",
    "ligi",
    "liginde",
    "lugunda",
    "luğunda",
    "liğinde",
    "inde",
    "inda",
)

# Stems of workplace / unit / job-title tokens that must never seed a person.
_WORKPLACE_STEMS = (
    "fabrika",
    "mudurluk",
    "seflik",
    "memurluk",
    "baskanlik",
    "sirket",
    "ozelinde",
    "paketleme",
    "uretim",
    "planlama",
    "malzeme",
    "kimyasal",
)

_ROLE_LABEL_RE = re.compile(
    r"^(?:"
    r"muvekkil(?:im|in|imin|imiz|imizin|i|ler|lerim)?"
    r"|vekil(?:i|in|ler|leri)?"
    r"|mudafii?"
    r"|davaci(?:lar)?"
    r"|davali(?:lar)?"
    r"|sanik(?:lar)?"
    r"|katilan(?:lar)?"
    r"|musteki(?:ler)?"
    r"|magdur(?:lar)?"
    r"|tanik(?:lar)?"
    r"|avukat"
    r"|av"
    r")$"
)


_EN_POSSESSIVE_TAIL = re.compile(r"^(.+[^'’])['’]s$", re.IGNORECASE)


def strip_possessive(value: str) -> str:
    stripped = value.strip()
    match = _POSSESSIVE.match(stripped)
    if match:
        return match.group(1).strip()
    english = _EN_POSSESSIVE_TAIL.match(stripped)
    if english:
        return english.group(1).strip()
    return stripped


_ASCII_TR = str.maketrans(
    {"ğ": "g", "ü": "u", "ş": "s", "ı": "i", "ö": "o", "ç": "c", "â": "a"}
)


def _fold_token(token: str) -> str:
    return fold_tr_identity(token.strip(".,;:()[]'\""))


def _ascii_fold(token: str) -> str:
    return _fold_token(token).translate(_ASCII_TR)


def _looks_inflected(token: str) -> bool:
    folded = _fold_token(token)
    ascii_folded = folded.translate(_ASCII_TR)
    if len(folded) < 6:
        return False
    return any(
        folded.endswith(suffix) or ascii_folded.endswith(suffix.translate(_ASCII_TR))
        for suffix in _INFLECTED_SUFFIXES
    )


def _is_workplace_token(token: str) -> bool:
    ascii_folded = _ascii_fold(token)
    if not ascii_folded:
        return False
    return any(
        ascii_folded == stem or ascii_folded.startswith(stem) for stem in _WORKPLACE_STEMS
    )


def is_legal_role_label(value: str) -> bool:
    """True for a bare procedural label (müvekkilim, vekili) with no person name."""
    compact = re.sub(r"\s+", "", _ascii_fold(value))
    if not compact:
        return False
    return bool(_ROLE_LABEL_RE.match(compact))


def is_isolated_letter_person_surface(value: str) -> bool:
    """True for a standalone one-letter token such as H, M, K, or A.

    Initials inside a multi-token name (``A. Yılmaz``, ``M. K. Demir``) are
    not isolated. Optional trailing period is ignored so ``A.`` alone still
    counts as a single glyph.
    """
    compact = _compact_alpha_token(value)
    return len(compact) == 1 and compact.isalpha()


_GEO_SHORT_KEEP = frozenset({"uk", "us", "eu", "gb"})
_NOTICE_STEMS = ("tebligat", "teblig", "tebellug")


def _compact_alpha_token(value: str) -> str:
    compact = (value or "").strip()
    if compact.endswith("."):
        compact = compact[:-1].strip()
    return compact


def is_isolated_uppercase_fragment(value: str) -> bool:
    """True for a standalone two-letter all-caps token such as OP.

    Title-case place names (``Of``) and closed geo shorts (``UK``/``US``)
    are kept. Multi-token spans are not fragments.
    """
    compact = _compact_alpha_token(value)
    if len(compact) != 2 or not compact.isalpha() or not compact.isupper():
        return False
    if compact.casefold() in _GEO_SHORT_KEEP:
        return False
    if _is_place(compact):
        return False
    return True


def is_procedural_notice_surface(value: str) -> bool:
    """True for notification wording such as tebligatın / tebliğine / tebellüğ."""
    tokens = [token for token in (value or "").split() if token]
    if len(tokens) != 1:
        return False
    folded = _ascii_fold(tokens[0])
    return any(folded == stem or folded.startswith(stem) for stem in _NOTICE_STEMS)


_TRAILING_UETS = re.compile(
    r"(?is)(?:^|[\s/]+)UETS\s*[:.\-]?\s*(?:\d{5}-\d{5}-\d{5})?\s*$"
)
_UETS_NUMBER = re.compile(r"(?<!\d)(\d{5}-\d{5}-\d{5})(?!\d)")


def is_uets_label_surface(value: str) -> bool:
    """True when the surface is only the UETS field label, not the mailbox number."""
    compact = re.sub(r"[\s:.\-]+", "", fold_tr_identity(value or ""))
    return compact == "uets"


def clip_trailing_uets_span(text: str) -> tuple[int, int] | None:
    """Relative [start, end) after dropping a trailing UETS: label (and optional number).

    None means the span is only that label — callers should drop it.
    """
    if is_uets_label_surface(text):
        return None
    match = _TRAILING_UETS.search(text)
    if match is None:
        return (0, len(text))
    end = match.start()
    while end > 0 and text[end - 1] in " \t\r\n/,;.":
        end -= 1
    if end <= 0 or is_uets_label_surface(text[:end]):
        return None
    return (0, end)


def uets_number_span(text: str) -> tuple[str, int, int] | None:
    """Return (number, start, end) for a 5-5-5 UETS mailbox id inside ``text``."""
    match = _UETS_NUMBER.search(text or "")
    if match is None:
        return None
    return match.group(1), match.start(1), match.end(1)


def is_workplace_or_job_title(value: str) -> bool:
    """True for factory / department / job-title spans, not a natural person."""
    tokens = [token for token in re.findall(r"\S+", value) if _ascii_fold(token)]
    if not tokens:
        return False
    return any(_is_workplace_token(token) for token in tokens)


def is_non_person_surface(value: str) -> bool:
    """Legal-role, court-addressee, or workplace wording that is not a person name."""
    if is_legal_role_label(value):
        return True
    if is_workplace_or_job_title(value):
        return True
    folded = _ascii_fold(value)
    # Procedural labels only as whole words — "konutları" must not match "konu".
    if re.search(r"(?<!\w)(?:konu|hukuku)(?!\w)", folded):
        return True
    if is_procedural_notice_surface(value):
        return True
    if "nobetci" in folded and "mahkemes" in folded:
        return True
    if "hakimlig" in folded and (
        "sayin" in folded
        or folded.endswith("hakimligine")
        or folded.endswith("hakimligi")
    ):
        return True
    if any(
        phrase in folded
        for phrase in (
            "supreme court",
            "high court",
            "court of appeal",
            "ministry of justice",
            "department of justice",
            "employment tribunals",
            "employment tribunal",
            "human rights act",
            "civil procedure rules",
        )
    ):
        return True
    return False


def _is_place(token: str) -> bool:
    folded = _fold_token(token)
    folded_raw = fold_tr(token)
    return folded in _PLACE_FOLD or folded_raw in _PLACE_FOLD


def _is_org_abbrev(token: str) -> bool:
    folded = _fold_token(token)
    return folded in {
        "ago",
        "bam",
        "cmk",
        "tck",
        "sgk",
        "egm",
        "segbis",
        "uyap",
        "vkn",
        "tckn",
    }


def _token_ok(token: str) -> bool:
    bare = token.strip(".,;:()[]")
    if not bare or bare.endswith("."):
        return bool(re.fullmatch(_INITIAL, bare))
    folded = _fold_token(bare)
    folded_raw = fold_tr(bare)
    if folded in _NAME_STOP or folded_raw in _NAME_STOP:
        return False
    if is_procedural_notice_surface(bare):
        return False
    if _is_workplace_token(bare) or is_legal_role_label(bare):
        return False
    if _is_org_abbrev(bare):
        return False
    if _looks_inflected(bare):
        return False
    if any(char.isdigit() for char in bare):
        return False
    letters = [char for char in bare if char.isalpha()]
    if len(letters) < 2:
        return False
    return letters[0].isupper() or bare.isupper()


def take_person_name(raw: str) -> tuple[str, int, int] | None:
    """Strip legal labels from both ends. Return (name, lead, trail) or None."""
    pieces = [(match.group(0), match.start(), match.end()) for match in re.finditer(r"\S+", raw)]
    while pieces and not _token_ok(strip_possessive(pieces[0][0])):
        pieces.pop(0)
    while pieces and not _token_ok(strip_possessive(pieces[-1][0])):
        pieces.pop()
    # "Nursu Karakan'ın Silifke AGO" — the name ends at the case suffix.
    for index, (token, _start, _end) in enumerate(pieces):
        if _POSSESSIVE.match(token.strip()) and index >= 1:
            pieces = pieces[: index + 1]
            break
    while len(pieces) > 2 and (
        _is_place(strip_possessive(pieces[-1][0])) or _is_org_abbrev(pieces[-1][0])
    ):
        pieces.pop()
    if not 2 <= len(pieces) <= 4:
        return None
    names = [strip_possessive(token).strip(".,;:") for token, _start, _end in pieces]
    if any(not _token_ok(name) for name in names):
        return None
    folded = fold_tr_identity(" ".join(names))
    if folded in _LEGAL_LABELS:
        return None
    if any(_is_workplace_token(name) or is_legal_role_label(name) for name in names):
        return None
    # A given name may also be a district (Fatih, Van). Reject only when
    # every token — or the whole phrase — is a place, not a person.
    if all(_is_place(name) for name in names):
        return None
    if folded in _PLACE_FOLD or fold_tr(" ".join(names)) in _PLACE_FOLD:
        return None
    lead = pieces[0][1]
    trail = len(raw) - pieces[-1][2]
    return " ".join(names), lead, trail


def clipped_name_span(raw: str, raw_start: int) -> tuple[str, int, int] | None:
    taken = take_person_name(raw)
    if taken is None:
        return None
    name, lead, trail = taken
    return name, raw_start + lead, raw_start + len(raw) - trail


def is_plausible_person_name(value: str) -> bool:
    """True only for 2–4 proper-name tokens after legal-label stripping."""
    return take_person_name(value) is not None


def collapse_name(value: str) -> str:
    return " ".join(value.split())


def first_person_span(text: str, start: int = 0, end: int | None = None) -> re.Match[str] | None:
    window = text if end is None else text[:end]
    for match in PERSON_NAME_RE.finditer(window, start):
        if take_person_name(match.group(1)):
            return match
    return None


def iter_person_spans(text: str) -> list[re.Match[str]]:
    found: list[re.Match[str]] = []
    for match in PERSON_NAME_RE.finditer(text):
        if take_person_name(match.group(1)):
            found.append(match)
    return found


__all__ = [
    "BARE_NAME_TOKEN",
    "NAME_TOKEN",
    "PERSON_NAME_RE",
    "clipped_name_span",
    "collapse_name",
    "first_person_span",
    "is_isolated_letter_person_surface",
    "is_isolated_uppercase_fragment",
    "is_legal_role_label",
    "is_non_person_surface",
    "is_plausible_person_name",
    "is_procedural_notice_surface",
    "is_uets_label_surface",
    "is_workplace_or_job_title",
    "clip_trailing_uets_span",
    "uets_number_span",
    "iter_person_spans",
    "strip_possessive",
    "take_person_name",
]
