import phonenumbers

# WhatsApp needs a mobile line: landlines (91x...), toll-free (800...) and premium numbers are useless leads.
_MOBILE_TYPES = {phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE}


def normalize_phone(raw: str, region: str = "ES") -> str | None:
    """Return the number in E.164 (+34612345678) or None if it is not a valid number."""
    raw = (raw or "").strip()
    if not raw:
        return None
    # Telegram contacts arrive without '+', e.g. '34612345678'
    if raw.isdigit() and len(raw) >= 10 and not raw.startswith("0"):
        raw = "+" + raw
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number(num) or phonenumbers.number_type(num) not in _MOBILE_TYPES:
        return None
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def pretty_phone(e164: str) -> str:
    try:
        return phonenumbers.format_number(
            phonenumbers.parse(e164, None), phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
    except phonenumbers.NumberParseException:
        return e164
