"""Checksum validation for Turkish identity numbers, IBAN, and credit cards."""

from __future__ import annotations


def validate_tckn(value: str) -> bool:
    """
    Validate Turkish Republic ID Number (TCKN) with checksum algorithm.
    
    Rules:
    - 11 digits
    - First digit cannot be 0
    - 10th digit = (sum of odd-position digits * 7 - sum of even-position digits) mod 10
    - 11th digit = sum of first 10 digits mod 10
    """
    if not value.isdigit() or len(value) != 11:
        return False
    
    if value[0] == "0":
        return False
    
    digits = [int(d) for d in value]
    
    # 10th digit check
    odd_sum = sum(digits[i] for i in range(0, 9, 2))  # 1st, 3rd, 5th, 7th, 9th
    even_sum = sum(digits[i] for i in range(1, 9, 2))  # 2nd, 4th, 6th, 8th
    check_10 = (odd_sum * 7 - even_sum) % 10
    
    if digits[9] != check_10:
        return False
    
    # 11th digit check
    check_11 = sum(digits[:10]) % 10
    if digits[10] != check_11:
        return False
    
    return True


# Official SWIFT / ISO 13616 IBAN lengths. This is the single country-length
# table for IBAN validation — do not duplicate it in detectors or scoring.
IBAN_COUNTRY_LENGTH: dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28, "BA": 20, "BE": 16, "BG": 22,
    "BH": 22, "BI": 27, "BR": 29, "BY": 28, "CH": 21, "CR": 22, "CY": 28, "CZ": 24,
    "DE": 22, "DJ": 27, "DK": 18, "DO": 28, "DZ": 26, "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27,
    "GT": 28, "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IR": 26, "IS": 26,
    "IT": 27, "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20,
    "LU": 20, "LV": 21, "LY": 25, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MR": 27,
    "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24, "PL": 28, "PS": 29, "PT": 25,
    "QA": 29, "RO": 24, "RS": 22, "RU": 33, "SA": 24, "SC": 31, "SD": 18, "SE": 24,
    "SI": 19, "SK": 24, "SM": 27, "SO": 23, "ST": 25, "SV": 28, "TL": 23, "TN": 24,
    "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}


def looks_like_tr_iban(value: str) -> bool:
    """True for the official TR + 24-digit shape, even when the checksum is wrong."""
    compact = "".join(char for char in value.upper() if char.isalnum())
    return compact.startswith("TR") and len(compact) == 26 and compact[2:].isdigit()


def validate_iban(value: str) -> bool:
    """
    Validate IBAN with country, official length, and mod-97 checksum.

    A candidate is IBAN only if normalization is syntactically possible, the
    prefix is a registered country, the length matches that country, and
    MOD-97 equals 1. Newlines, dashes, and other separators are ignored;
    junk never raises. Failed checksums cannot be rescued by scoring.
    """
    iban = "".join(char for char in value.upper() if char.isalnum())
    if not 15 <= len(iban) <= 34:
        return False
    if not iban[:2].isalpha() or not iban[2:4].isdigit():
        return False
    if not iban[4:].isalnum():
        return False
    expected = IBAN_COUNTRY_LENGTH.get(iban[:2])
    if expected is None or len(iban) != expected:
        return False

    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for char in rearranged:
        if char.isdigit():
            numeric += char
        elif char.isalpha():
            numeric += str(ord(char) - 55)
        else:
            return False
    try:
        return int(numeric) % 97 == 1
    except ValueError:
        return False


def validate_luhn(value: str) -> bool:
    """
    Validate credit card number using Luhn algorithm.
    
    Works for Visa, Mastercard, Amex, etc.
    """
    # Remove spaces and dashes
    number = value.replace(" ", "").replace("-", "")
    
    if not number.isdigit() or len(number) < 13 or len(number) > 19:
        return False
    
    digits = [int(d) for d in number]
    checksum = 0
    
    # Luhn algorithm: double every second digit from right, subtract 9 if > 9
    for i in range(len(digits) - 2, -1, -2):
        doubled = digits[i] * 2
        checksum += doubled - 9 if doubled > 9 else doubled
    
    # Add remaining digits
    for i in range(len(digits) - 1, -1, -2):
        checksum += digits[i]
    
    return checksum % 10 == 0


def validate_vkn(value: str) -> bool:
    """Validate a 10-digit Turkish tax identification number (VKN).

    Uses the published GIB check-digit recurrence. A passing checksum is not
    enough to emit a finding; detectors still require a tax-label context.
    """
    compact = value.replace(" ", "").replace("-", "")
    if not compact.isdigit() or len(compact) != 10:
        return False
    total = 0
    for index, char in enumerate(compact[:9], start=1):
        step = (int(char) + 10 - index) % 10
        powered = (step * pow(2, 10 - index)) % 9
        if step != 0 and powered == 0:
            powered = 9
        total += powered
    check = (10 - (total % 10)) % 10
    return check == int(compact[9])
