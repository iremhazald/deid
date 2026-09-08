"""Global locale pack with jurisdiction-agnostic patterns."""
from app.detectors.locale_pack import LocalePack
from app.detectors.registry import detect_global

GLOBAL_PACK = LocalePack(
    locale_id="global",
    name="Global Patterns",
    detectors=[
        ("GLOBAL_STRUCTURED", detect_global),
    ],
)
