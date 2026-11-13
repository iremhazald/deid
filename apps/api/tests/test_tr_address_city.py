"""The city stays inside a Turkish street address."""

from app.detectors.registry import PageText, run_detectors
from app.domain.models import EntityType


def _addresses(text: str) -> list[str]:
    found, _names = run_detectors([PageText(page=0, text=text, document_offset=0)], None)
    return [item.text for item in found if item.type == EntityType.ADDRESS]


def test_district_and_city_stay_in_the_street_address() -> None:
    text = "ikamet: Atatürk Caddesi 78/9 Kadıköy İstanbul, tel: 0216 555 1234"
    assert "Atatürk Caddesi 78/9 Kadıköy İstanbul" in _addresses(text)


def test_door_number_does_not_cut_the_city() -> None:
    text = (
        "Teslimat adresi: Barbaros Mahallesi Dereboyu Caddesi No:156/A "
        "Beşiktaş/İstanbul 34353. Alıcı: Kemal Yıldız."
    )
    assert "Barbaros Mahallesi Dereboyu Caddesi No:156/A Beşiktaş/İstanbul 34353" in _addresses(
        text
    )


def test_slashed_city_stays_in_the_street_address() -> None:
    text = "Adres: Kordonboyu No: 4 Konak/İzmir. Telefon +90 532 010 1107."
    assert "Kordonboyu No: 4 Konak/İzmir" in _addresses(text)
