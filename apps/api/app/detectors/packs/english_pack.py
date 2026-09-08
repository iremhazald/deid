"""English-General locale pack. Future en-GB / en-US packs can sit beside this."""

from app.detectors.en import detect_english_legal
from app.detectors.locale_pack import LocalePack

ENGLISH_PACK = LocalePack(
    locale_id="en",
    name="English-General Legal Documents",
    detectors=[
        ("EN_LEGAL_STRUCTURE", detect_english_legal),
    ],
    role_labels={
        "claimant": "Claimant",
        "defendant": "Defendant",
        "witness": "Witness",
        "expert": "Expert",
        "lawyer": "Counsel",
        "judge": "Judge",
    },
)
