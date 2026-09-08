"""Optional Turkish given-name lexicon used only as evidence.

A lexicon hit is never enough to emit PERSON. Words such as Deniz, Barış,
Duru, Eylül, Yalın, and Umut also occur outside person-name use.

Provenance: compiled locally from commonly attested Turkish given names
(public-domain factual data). No third-party dictionary dump. No network
lookup during scanning. Not a copyrighted word list.
"""

from __future__ import annotations

from functools import lru_cache

from app.detectors.textutil import fold_tr_identity

# Ambiguous surfaces that must never decide PERSON by themselves.
AMBIGUOUS_GIVEN_NAMES = frozenset(
    {
        "deniz",
        "baris",
        "duru",
        "eylul",
        "yalin",
        "umut",
        "umit",
        "yagmur",
        "nehir",
        "ruzgar",
        "toprak",
        "gunes",
        "ay",
        "su",
        "can",
        "nur",
        "ozgur",
        "yildiz",
        "mehtap",
        "bahar",
        "sever",
        "soylu",
        "yaman",
    }
)

_RAW_FIRST_NAMES = """
Ahmet Mehmet Ali Mustafa Hüseyin Hasan Abdullah Berk İbrahim İsmail Osman Yusuf
Murat Emre Burak Can Cem Cenk Cihan Eren Furkan Kaan Kerem Mert Onur
Oğuz Oğuzhan Serkan Tolga Uğur Volkan Yasin Yiğit Baran Berk Emir Ege
Arda Alp Alper Enes Efe Halil Harun Hakan Gökhan Gökçe Koray Levent
Orhan Ömer Özgür Recep Salih Selim Sinan Taner Tarık Tuncay Vedat Yavuz
Zeki Adem Adnan Akif Altan Aydın Ayhan Bahadır Bülent Cengiz Coşkun
Doğan Ercan Erdal Erhan Erkan Ertuğrul Fatih Ferhat Fırat Gürkan Halis
İlhan İlker İzzet Kadir Kemal Levent Mahmut Mesut Metin Muzaffer Necati
Nihat Nuri Orkun Ozan Polat Rıza Sami Sedat Semih Serdar Sezgin Suat
Şaban Şahin Tanju Tayfun Tekin Tevfik Ufuk Ümit Yaşar Yüksel Zafer
Ziya Batuhan Günay Günayhan Berkay Doruk Egehan Kaanhan Metehan Göktuğ
Kağan Tuğra Alparslan Atakan Ayaz Bilal Cemil Cevdet Davut Eşref Fazıl
Hamza Hayri İhsan İskender Kazım Lütfi Münir Nurettin Rafet Rüstem
Saffet Süleyman Turgut Vehbi Yalçın Yunus Zafer
Ayşe Fatma Emine Hatice Zeynep Elif Merve Büşra Esra Zehra
Hatice Hülya Sevgi Sibel Sema Serap Şule Şeyma Tuğba Yasemin Dilek
Aysel Aynur Ayla Banu Berna Bilge Burcu Cansu Ceyda Damla Deniz Derya
Didem Duygu Ebru Ece Eda Elif Elvan Emel Esin Eylül Feride Filiz
Fulya Funda Gamze Gizem Gül Gülay Gülçin Gülşen Güneş Hacer Handan
Havva Hayriye Hilal İpek İrem Jale Kadriye Kamile Leyla Melike Melis
Meltem Mine Müge Nalan Nazan Nazlı Necla Neşe Nilgün Nuran Nuray
Nurcan Nurhan Özge Özlem Pınar Rabia Rukiye Seda Selda Selma Semra
Sevil Sevim Şenay Şengül Tülay Ülkü Yeliz Yonca Zahide Zeliha
Günay Nisan Nehir Yağmur Duru Yalın Beren Defne Doğa Ecrin Asya
Azra Ceren Dilara Ece Ada Asli Aslı Bahar Beste Beyza Buse Çağla
Dilan Eslem Eylül Feray Gökçe Hiranur İkra Lina Melek Meryem
Nisa Rana Sude Yağmur Yaren Zehra Zümra
Mehmetali Aliye Ayten Bedriye Cahide Dursun Ekrem Fadime Gülizar
Hikmet İclal Kudret Lale Münire Nevzat Oya Pakize Remziye Sabriye
Şerife Türkan Ulviye Vesile Yıldız Zahide
Nursu İrem İpek
"""


@lru_cache(maxsize=1)
def first_name_set() -> frozenset[str]:
    names: set[str] = set()
    for token in _RAW_FIRST_NAMES.split():
        folded = fold_tr_identity(token)
        if len(folded) >= 2:
            names.add(folded)
    names.update(AMBIGUOUS_GIVEN_NAMES)
    return frozenset(names)


def is_known_first_name(token: str) -> bool:
    folded = fold_tr_identity(token.strip(".,;:'’`´ʼ′"))
    return folded in first_name_set()


def is_ambiguous_first_name(token: str) -> bool:
    folded = fold_tr_identity(token.strip(".,;:'’`´ʼ′"))
    return folded in AMBIGUOUS_GIVEN_NAMES
