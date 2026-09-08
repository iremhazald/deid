"""English-General legal vocabularies. Jurisdiction-neutral; not UK/US-specific."""

from __future__ import annotations

# Party / participant roles. Evidence only — never become identity tokens.
PARTY_ROLES: tuple[tuple[str, str], ...] = (
    ("claimant", "CLAIMANT"),
    ("plaintiff", "CLAIMANT"),
    ("defendant", "DEFENDANT"),
    ("applicant", "APPLICANT"),
    ("respondent", "RESPONDENT"),
    ("petitioner", "PETITIONER"),
    ("appellant", "APPELLANT"),
    ("appellee", "APPELLEE"),
    ("complainant", "COMPLAINANT"),
    ("accused", "ACCUSED"),
    ("suspect", "SUSPECT"),
    ("witness", "WITNESS"),
    ("deponent", "DEPONENT"),
    ("affiant", "AFFIANT"),
)

COUNSEL_ROLES: tuple[tuple[str, str], ...] = (
    ("counsel for the claimant", "COUNSEL"),
    ("counsel for the defendant", "COUNSEL"),
    ("counsel for the applicant", "COUNSEL"),
    ("counsel for the respondent", "COUNSEL"),
    ("counsel for the plaintiff", "COUNSEL"),
    ("legal representative", "COUNSEL"),
    ("attorney-at-law", "COUNSEL"),
    ("attorney at law", "COUNSEL"),
    ("representative", "COUNSEL"),
    ("solicitor for", "COUNSEL"),
    ("counsel for", "COUNSEL"),
    ("barrister", "COUNSEL"),
    ("solicitor", "COUNSEL"),
    ("advocate", "COUNSEL"),
    ("attorney", "COUNSEL"),
    ("counsel", "COUNSEL"),
    ("lawyer", "COUNSEL"),
)

DECISION_ROLES: tuple[tuple[str, str], ...] = (
    ("employment judge", "JUDGE"),
    ("arbitrator", "ARBITRATOR"),
    ("magistrate", "JUDGE"),
    ("mediator", "MEDIATOR"),
    ("registrar", "REGISTRAR"),
    ("justice", "JUDGE"),
    ("judge", "JUDGE"),
    ("clerk", "CLERK"),
)

EXPERT_ROLES: tuple[tuple[str, str], ...] = (
    ("expert witness", "EXPERT"),
    ("consultant", "CONSULTANT"),
    ("interpreter", "INTERPRETER"),
    ("translator", "TRANSLATOR"),
    ("expert", "EXPERT"),
)

PERSON_TITLES: tuple[str, ...] = (
    "professor",
    "prof",
    "miss",
    "mrs",
    "ms",
    "mr",
    "mx",
    "dr",
    "sir",
    "dame",
)

SIGNATURE_LABELS: tuple[str, ...] = (
    "name of signatory",
    "authorised signatory",
    "authorized signatory",
    "signed by",
    "signature",
    "signed",
    "name",
)

ADDRESS_LABELS: tuple[str, ...] = (
    "address for service",
    "correspondence address",
    "residential address",
    "registered address",
    "service address",
    "postal address",
    "home address",
    "address",
)

POSTAL_LABELS: tuple[str, ...] = (
    "postal code",
    "postcode",
    "zip code",
    "zip",
)

PHONE_LABELS: tuple[str, ...] = (
    "contact number",
    "telephone number",
    "phone number",
    "telephone",
    "mobile",
    "phone",
    "cell",
    "tel",
)

EMAIL_LABELS: tuple[str, ...] = (
    "email address",
    "e-mail",
    "email",
)

URL_LABELS: tuple[str, ...] = (
    "website",
    "web",
    "url",
)

BIRTH_DATE_LABELS: tuple[str, ...] = (
    "date of birth",
    "birth date",
    "d.o.b.",
    "dob",
    "born on",
    "born",
)

BIRTH_PLACE_LABELS: tuple[str, ...] = (
    "place of birth",
    "birthplace",
    "born in",
)

NON_BIRTH_DATE_LABELS: tuple[str, ...] = (
    "hearing date",
    "decision date",
    "order date",
    "filing date",
    "service date",
    "contract date",
    "execution date",
)

PASSPORT_LABELS: tuple[str, ...] = (
    "passport number",
    "passport no",
    "passport #",
    "passport",
)

NATIONAL_ID_LABELS: tuple[str, ...] = (
    "national identification number",
    "national id no",
    "national id",
    "identity number",
    "id number",
)

FINANCIAL_LABELS: tuple[tuple[str, str], ...] = (
    ("account number", "ACCOUNT"),
    ("bank account", "ACCOUNT"),
    ("account no", "ACCOUNT"),
    ("routing number", "ROUTING"),
    ("sort code", "SORT"),
    ("iban", "IBAN"),
)

CASE_REF_LABELS: tuple[tuple[str, str], ...] = (
    ("proceeding number", "FILE"),
    ("application no", "CASE"),
    ("proceeding no", "FILE"),
    ("reference number", "FILE"),
    ("docket number", "CASE"),
    ("matter number", "FILE"),
    ("claim number", "CASE"),
    ("case number", "CASE"),
    ("file number", "FILE"),
    ("appeal no", "CASE"),
    ("reference no", "FILE"),
    ("docket no", "CASE"),
    ("matter no", "FILE"),
    ("claim no", "CASE"),
    ("case no", "CASE"),
    ("file no", "FILE"),
    ("reference", "FILE"),
    ("ref.", "FILE"),
    ("ref", "FILE"),
)

STREET_TYPES: tuple[str, ...] = (
    "boulevard",
    "parkway",
    "highway",
    "crescent",
    "terrace",
    "avenue",
    "street",
    "drive",
    "lane",
    "road",
    "court",
    "place",
    "square",
    "close",
    "way",
    "blvd",
    "ave",
    "str",
    "rd",
    "st",
    "ln",
    "ct",
    "pl",
    "sq",
    "dr",
)

UNIT_TYPES: tuple[str, ...] = (
    "apartment",
    "building",
    "suite",
    "floor",
    "house",
    "flat",
    "unit",
    "room",
    "apt",
)

COMPANY_SUFFIXES: tuple[str, ...] = (
    "incorporated",
    "corporation",
    "limited",
    "p.l.c.",
    "l.p.",
    "plc",
    "llp",
    "llc",
    "ltd",
    "inc",
    "corp",
    "lp",
)

COURT_PHRASES: tuple[str, ...] = (
    "court of appeals",
    "court of appeal",
    "constitutional court",
    "administrative court",
    "arbitration tribunal",
    "employment tribunals",
    "employment tribunal",
    "employment court",
    "commercial court",
    "criminal court",
    "district court",
    "circuit court",
    "county court",
    "family court",
    "labour court",
    "civil court",
    "supreme court",
    "high court",
)

COURT_HEAD_ADJECTIVES: frozenset[str] = frozenset(
    {
        "supreme",
        "high",
        "district",
        "circuit",
        "county",
        "family",
        "commercial",
        "civil",
        "criminal",
        "employment",
        "labour",
        "labor",
        "administrative",
        "constitutional",
        "arbitration",
        "appeal",
        "appeals",
        "federal",
        "state",
        "crown",
        "magistrates",
        "magistrate",
    }
)

INSTITUTION_PHRASES: tuple[str, ...] = (
    "department of justice",
    "ministry of justice",
    "legal department",
    "human rights act",
    "civil procedure rules",
    "united kingdom",
    "united states",
    "new york",
    "london",
)

LEGAL_NARRATIVE_CUES: tuple[str, ...] = (
    "represented by",
    "gave evidence",
    "testified that",
    "on behalf of",
    "acting for",
    "witnessed by",
    "counsel for",
    "solicitor for",
    "stated that",
    "appeared",
    "attended",
    "submitted",
    "filed",
    "signed",
)

# Cue-before-name only. Clause-taking verbs ("stated that X") introduce a
# proposition, not a person, and must not use this list.
NARRATIVE_PRE_NAME_CUES: tuple[str, ...] = (
    "represented by",
    "on behalf of",
    "acting for",
    "witnessed by",
    "counsel for",
    "solicitor for",
)

# Clause-initial function words. These are grammatical openers, not given names.
EN_DISCOURSE_OPENERS: frozenset[str] = frozenset(
    {
        "whilst",
        "while",
        "whereas",
        "although",
        "though",
        "however",
        "therefore",
        "accordingly",
        "furthermore",
        "moreover",
        "nevertheless",
        "thereafter",
        "meanwhile",
        "subsequently",
        "notwithstanding",
        "provided",
        "following",
        "applying",
        "including",
        "pursuant",
        "wherefore",
        "hereby",
        "herein",
    }
)

# Trading-name markers. The following span is organisation context, not PERSON.
TRADING_AS_MARKERS: tuple[str, ...] = (
    "doing business as",
    "trading as",
    "d/b/a",
    "d.b.a.",
    "t/a",
    "dba",
)

# Procedural heading cues. ALLCAPS / title-line surfaces containing these
# are legal headings, not person names.
LEGAL_HEADING_CUES: frozenset[str] = frozenset(
    {
        "judgment",
        "judgement",
        "reasons",
        "notice",
        "order",
        "decision",
        "application",
        "hearing",
        "directions",
        "ruling",
    }
)

# Standalone representative / decision-maker role words. Evidence only.
LEGAL_ROLE_WORDS: frozenset[str] = frozenset(
    {
        "counsel",
        "solicitor",
        "barrister",
        "attorney",
        "lawyer",
        "advocate",
        "representative",
        "judge",
        "justice",
        "magistrate",
        "arbitrator",
        "registrar",
        "clerk",
    }
)

# Closed ordinal set for party designations only. Not an open number grammar.
LITIGATION_ORDINALS: frozenset[str] = frozenset(
    {
        "first",
        "second",
        "third",
        "fourth",
        "fifth",
        "1st",
        "2nd",
        "3rd",
        "4th",
        "5th",
    }
)

# Representation status after a party label. Not a person name.
REPRESENTATION_STATUS: frozenset[str] = frozenset(
    {
        "in person",
        "litigant in person",
        "acting in person",
    }
)

PARTY_ROLE_WORDS: frozenset[str] = frozenset(label for label, _role in PARTY_ROLES)
DECISION_ROLE_LABELS: frozenset[str] = frozenset(label for label, _role in DECISION_ROLES)


def ordinal_party_role_labels() -> tuple[tuple[str, str], ...]:
    """Complete ordinal + party-role surfaces. Tokens such as First stay free."""
    found: list[tuple[str, str]] = []
    for ordinal in sorted(LITIGATION_ORDINALS, key=len, reverse=True):
        for label, role in PARTY_ROLES:
            found.append((f"{ordinal} {label}", role))
    return tuple(found)


def _the_role_cues() -> tuple[str, ...]:
    cues: list[str] = []
    seen: set[str] = set()
    for label, _role in PARTY_ROLES:
        for surface in (f"the {label}",):
            if surface not in seen:
                seen.add(surface)
                cues.append(surface)
        for ordinal in sorted(LITIGATION_ORDINALS, key=len, reverse=True):
            surface = f"the {ordinal} {label}"
            if surface not in seen:
                seen.add(surface)
                cues.append(surface)
    return tuple(cues)


THE_ROLE_CUES: tuple[str, ...] = _the_role_cues()

# Optional first-name signal only. Never a detector by itself.
ENGLISH_FIRST_NAMES: frozenset[str] = frozenset(
    {
        "james",
        "john",
        "robert",
        "michael",
        "william",
        "david",
        "richard",
        "joseph",
        "thomas",
        "charles",
        "andrew",
        "daniel",
        "matthew",
        "anthony",
        "mark",
        "steven",
        "paul",
        "joshua",
        "kevin",
        "brian",
        "george",
        "edward",
        "ronald",
        "timothy",
        "jason",
        "jeffrey",
        "ryan",
        "jacob",
        "gary",
        "nicholas",
        "eric",
        "jonathan",
        "stephen",
        "larry",
        "justin",
        "scott",
        "brandon",
        "benjamin",
        "samuel",
        "raymond",
        "alexander",
        "patrick",
        "jack",
        "dennis",
        "jerry",
        "tyler",
        "aaron",
        "henry",
        "douglas",
        "peter",
        "adam",
        "nathan",
        "zachary",
        "walter",
        "kyle",
        "harold",
        "carl",
        "arthur",
        "gerald",
        "roger",
        "keith",
        "jeremy",
        "terry",
        "lawrence",
        "sean",
        "christian",
        "albert",
        "joe",
        "ethan",
        "austin",
        "jesse",
        "willie",
        "billy",
        "bryan",
        "bruce",
        "noah",
        "jordan",
        "dylan",
        "alan",
        "ralph",
        "gabriel",
        "roy",
        "juan",
        "wayne",
        "eugene",
        "logan",
        "randy",
        "louis",
        "russell",
        "vincent",
        "philip",
        "bobby",
        "johnny",
        "bradley",
        "mary",
        "patricia",
        "jennifer",
        "linda",
        "elizabeth",
        "barbara",
        "susan",
        "jessica",
        "sarah",
        "karen",
        "lisa",
        "nancy",
        "betty",
        "margaret",
        "sandra",
        "ashley",
        "kimberly",
        "emily",
        "donna",
        "michelle",
        "dorothy",
        "carol",
        "amanda",
        "melissa",
        "deborah",
        "stephanie",
        "rebecca",
        "sharon",
        "laura",
        "cynthia",
        "kathleen",
        "amy",
        "angela",
        "shirley",
        "anna",
        "brenda",
        "pamela",
        "emma",
        "nicole",
        "helen",
        "samantha",
        "katherine",
        "christine",
        "debra",
        "rachel",
        "carolyn",
        "janet",
        "catherine",
        "maria",
        "heather",
        "diane",
        "ruth",
        "julie",
        "olivia",
        "joyce",
        "virginia",
        "victoria",
        "kelly",
        "lauren",
        "christina",
        "joan",
        "evelyn",
        "judith",
        "megan",
        "andrea",
        "cheryl",
        "hannah",
        "jacqueline",
        "martha",
        "gloria",
        "teresa",
        "sara",
        "janice",
        "marie",
        "julia",
        "grace",
        "judy",
        "theresa",
        "madison",
        "beverly",
        "denise",
        "marilyn",
        "amber",
        "danielle",
        "brittany",
        "diana",
        "abigail",
        "jane",
        "lori",
        "frances",
        "jean",
        "alice",
        "kathryn",
        "louise",
        "anne",
        "ann",
        "lucy",
        "claire",
        "sophie",
        "charlotte",
        "hannah",
        "amelia",
        "isla",
        "freya",
        "lily",
        "eva",
        "chloe",
        "mia",
        "poppy",
        "ellie",
        "harper",
        "willow",
        "eleanor",
        "florence",
        "sienna",
        "phoebe",
        "alice",
        "jessica",
        "oliver",
        "george",
        "harry",
        "noah",
        "jack",
        "leo",
        "oscar",
        "charlie",
        "jacob",
        "alfie",
        "freddie",
        "arthur",
        "henry",
        "archie",
        "theo",
        "teddy",
        "alexander",
        "lucas",
        "william",
        "thomas",
        "isaac",
        "edward",
        "max",
        "tommy",
        "finley",
        "hugo",
    }
)

MONTHS: frozenset[str] = frozenset(
    {
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "jan",
        "feb",
        "mar",
        "apr",
        "jun",
        "jul",
        "aug",
        "sep",
        "sept",
        "oct",
        "nov",
        "dec",
    }
)
