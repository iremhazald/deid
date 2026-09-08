"""Gazetteers for Turkish legal entities and geographic locations."""

from __future__ import annotations

# Turkish courts (representative sample, not exhaustive)
TURKISH_COURTS = frozenset({
    "Yargıtay",
    "Danıştay",
    "Anayasa Mahkemesi",
    "Sayıştay",
    "Uyuşmazlık Mahkemesi",
    "Bölge Adliye Mahkemesi",
    "Bölge İdare Mahkemesi",
    "Asliye Hukuk Mahkemesi",
    "Asliye Ceza Mahkemesi",
    "Asliye Ticaret Mahkemesi",
    "İş Mahkemesi",
    "İdare Mahkemesi",
    "Vergi Mahkemesi",
    "Sulh Hukuk Mahkemesi",
    "Sulh Ceza Mahkemesi",
    "Ağır Ceza Mahkemesi",
    "İcra Hukuk Mahkemesi",
    "İcra Ceza Mahkemesi",
    "Aile Mahkemesi",
    "Çocuk Mahkemesi",
    "Tüketici Mahkemesi",
    "Fikri ve Sınai Haklar Hukuk Mahkemesi",
    "Fikri ve Sınai Haklar Mahkemesi",
    "Denizcilik İhtisas Mahkemesi",
})

# Turkish cities (81 provinces)
TURKISH_CITIES = frozenset({
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya",
    "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu",
    "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır",
    "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep",
    "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul",
    "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli",
    "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla",
    "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt",
    "Sinop", "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa",
    "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova",
    "Karabük", "Kilis", "Osmaniye", "Düzce",
})

# Turkish districts (representative major ones)
TURKISH_DISTRICTS = frozenset({
    "Çankaya", "Keçiören", "Yenimahalle", "Mamak", "Etimesgut", "Sincan",
    "Altındağ", "Pursaklar", "Gölbaşı", "Polatlı",
    "Kadıköy", "Üsküdar", "Şişli", "Beşiktaş", "Beyoğlu", "Fatih", "Bakırköy",
    "Kartal", "Maltepe", "Ataşehir", "Pendik", "Ümraniye", "Küçükçekmece",
    "Esenler", "Bağcılar", "Gaziosmanpaşa", "Sultanbeyli", "Eyüpsultan",
    "Konak", "Karşıyaka", "Bornova", "Buca", "Çiğli", "Gaziemir", "Bayraklı",
    "Muratpaşa", "Kepez", "Konyaaltı", "Döşemealtı", "Aksu",
    "Silifke",
})

# Turkish legal roles and titles
TURKISH_LEGAL_TITLES = frozenset({
    "Hakim", "Yargıç", "Savcı", "Cumhuriyet Savcısı", "Başsavcı",
    "Avukat", "Müdafi", "Vekil", "Noter", "Bilirkişi", "Uzman",
    "Zabıt Katibi", "Zabıt Katibi", "Mübaşir",
})

# Turkish government institutions
TURKISH_INSTITUTIONS = frozenset({
    "Cumhuriyet Başsavcılığı", "Adliye", "Emniyet Müdürlüğü",
    "Kaymakamlık", "Valilik", "Belediye", "Müdürlük", "Başkanlık",
    "Bakanlık", "Genel Müdürlük", "Daire Başkanlığı",
    "Adli Tıp Kurumu", "İcra Müdürlüğü", "Jandarma",
    "Nüfus Müdürlüğü", "Tapu Müdürlüğü", "Vergi Dairesi",
})

TURKISH_BANKS = frozenset({
    "Ziraat Bankası", "Halkbank", "Vakıfbank", "VakıfBank",
    "İş Bankası", "Türkiye İş Bankası", "Garanti BBVA", "Garanti Bankası",
    "Yapı Kredi", "Yapı Kredi Bankası", "Akbank", "QNB Finansbank",
    "Denizbank", "TEB", "ING Bank", "İNG Bank", "HSBC", "Şekerbank",
    "Fiba Banka", "Fibabanka", "FibaBanka",
})

TURKISH_TELECOM = frozenset({
    "Turkcell", "Vodafone", "Türk Telekom", "Türk Telekomünikasyon",
    "Avea", "TTNET",
})

# Official geographic area codes (BTK). Mobile 5xx is excluded.
TURKISH_AREA_CODES = frozenset({
    "212", "216",
    "222", "224", "226", "228",
    "232", "236",
    "242", "246", "248",
    "252", "256", "258",
    "262", "264", "266",
    "272", "274", "276",
    "282", "284", "286", "288",
    "312", "318",
    "322", "324", "326", "328",
    "332", "338",
    "342", "344", "346", "348",
    "352", "354", "356", "358",
    "362", "364", "366", "368",
    "370", "372", "374", "376", "378",
    "380", "382", "384", "386", "388",
    "412", "414", "416",
    "422", "424", "426", "428",
    "432", "434", "436", "438",
    "442", "446",
    "452", "454", "456", "458",
    "462", "464", "466",
    "472", "474", "476", "478",
    "482", "484", "486", "488",
})

AUTHORITY_PHRASES = frozenset({
    "Cumhuriyet Başsavcılığı",
    "Bölge Adliye Mahkemesi",
    "Bölge İdare Mahkemesi",
    "Adli Tıp Kurumu",
    "İcra Müdürlüğü",
    "Emniyet Müdürlüğü",
})


def is_turkish_court(text: str) -> bool:
    """Check if text contains a Turkish court name."""
    normalized = text.strip()
    for court in TURKISH_COURTS:
        if court in normalized:
            return True
    return False


def is_turkish_city(text: str) -> bool:
    """Check if text is a Turkish city name."""
    return text.strip() in TURKISH_CITIES


def is_turkish_district(text: str) -> bool:
    """Check if text is a Turkish district name."""
    return text.strip() in TURKISH_DISTRICTS


def is_turkish_legal_title(text: str) -> bool:
    """Check if text contains a Turkish legal title."""
    normalized = text.strip()
    return any(title in normalized for title in TURKISH_LEGAL_TITLES)


def is_turkish_institution(text: str) -> bool:
    """Check if text contains a Turkish government institution."""
    normalized = text.strip()
    return any(inst in normalized for inst in TURKISH_INSTITUTIONS)
