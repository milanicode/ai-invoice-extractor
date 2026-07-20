"""Brazilian NF-e helpers: fill missing emitente CNPJ from Chave de Acesso."""

from __future__ import annotations

import re
from typing import Any

ACCESS_KEY_DIGITS = re.compile(r"(?<!\d)(\d{40,45})(?!\d)")
CNPJ_PATTERN = re.compile(r"(?<!\d)(\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2})(?!\d)")

VENDOR_LABEL_PATTERN = re.compile(
    r"(?:raz[aã]o\s*social|nome\s*/?\s*raz[aã]o\s*social|emitente|fornecedor|"
    r"remetente(?!\s*/)|vendedor|empresa\s*emitente)[\s:\-]+"
    r"([A-Za-zÀ-Üà-ü0-9][^\n]{2,90})",
    re.I,
)
VENDOR_COMPANY_PATTERN = re.compile(
    r"\b([A-ZÀ-Ü0-9][A-Za-zÀ-Üà-ü0-9\s\.\&\'\-]{2,70}"
    r"(?:LTDA\.?|S/?A\.?|S\.A\.|ME|EIRELI|EPP|SS))\b",
)

BAD_VENDOR_NAMES = {
    "danfe",
    "nfe",
    "nf-e",
    "documento",
    "documento auxiliar",
    "natureza da operação",
    "natureza da operacao",
    "destinatario",
    "destinatário",
    "remetente",
    "transportador",
    "homologacao",
    "homologação",
    "sem valor fiscal",
}


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"null", "none", "-", "n/a", "na"}


def normalize_vendor_name(value: str | None) -> str | None:
    if is_blank(value):
        return None
    name = re.sub(r"\s+", " ", str(value)).strip(" \t\r\n-:|")
    if len(name) < 3:
        return None
    if name.lower() in BAD_VENDOR_NAMES:
        return None
    if name.lower().startswith(("destinat", "transport", "chave de acesso")):
        return None
    return name


def find_vendor_name(*blobs: str | None) -> str | None:
    for blob in blobs:
        if not blob:
            continue
        for match in VENDOR_LABEL_PATTERN.finditer(blob):
            name = normalize_vendor_name(match.group(1))
            if name:
                return name
        for match in VENDOR_COMPANY_PATTERN.finditer(blob):
            name = normalize_vendor_name(match.group(1))
            if name:
                return name
    return None


def format_cnpj(digits14: str) -> str:
    d = only_digits(digits14)
    if len(d) != 14:
        return digits14
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def is_valid_cnpj(value: str | None) -> bool:
    d = only_digits(value or "")
    if len(d) != 14 or d == d[0] * 14:
        return False

    def check(base: str, weights: list[int]) -> str:
        total = sum(int(n) * w for n, w in zip(base, weights))
        rest = total % 11
        return "0" if rest < 2 else str(11 - rest)

    d1 = check(d[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = check(d[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return d[-2:] == d1 + d2


def cnpj_from_access_key(key: str) -> str | None:
    """
    NF-e access key layout starts with cUF(2)+AAMM(4)+CNPJ(14)+...
    Emitente CNPJ is always digits[6:20]. Vision OCR often drops trailing
    digits; the CNPJ block is near the start so this still works.
    """
    digits = only_digits(key)
    if len(digits) < 20:
        return None
    return format_cnpj(digits[6:20])


def find_access_key(*blobs: str | None) -> str | None:
    best: str | None = None
    for blob in blobs:
        if not blob:
            continue
        digits = only_digits(blob)
        exact = re.search(r"(?<!\d)(\d{44})(?!\d)", digits)
        if exact:
            return exact.group(1)
        match = ACCESS_KEY_DIGITS.search(digits)
        if match and (best is None or abs(len(match.group(1)) - 44) < abs(len(best) - 44)):
            best = match.group(1)
    return best


def enrich_invoice_data(data: dict[str, Any], *, source_text: str | None = None) -> dict[str, Any]:
    """
    Fill/correct emitente fields when the LLM leaves them blank or invalid:
    - vendor_tax_id from Chave de Acesso / CNPJ patterns
    - vendor_name from labels like Razão Social / Emitente in text
    """
    out = dict(data)
    current = out.get("vendor_tax_id")

    key = find_access_key(out.get("access_key"), out.get("notes"), source_text) or out.get(
        "access_key"
    )
    derived = cnpj_from_access_key(str(key)) if key else None

    # Also try an explicitly formatted CNPJ in notes/text (no sliding-window guessing)
    if not derived:
        for blob in (out.get("notes"), source_text):
            if not blob:
                continue
            for match in CNPJ_PATTERN.finditer(blob):
                cand = format_cnpj(match.group(1))
                if is_valid_cnpj(cand):
                    derived = cand
                    break
            if derived:
                break

    should_replace = bool(derived) and (
        not current
        or not is_valid_cnpj(current)
        or only_digits(str(current)) != only_digits(derived)
    )

    # If current is a valid CNPJ and differs from derived, keep current
    # (visible CNPJ box can differ from OCR noise on chave in rare cases).
    if current and is_valid_cnpj(current) and derived and only_digits(str(current)) != only_digits(derived):
        should_replace = False

    if should_replace and derived:
        out["vendor_tax_id"] = derived
        key_digits = only_digits(str(key)) if key else ""
        if key_digits:
            out["access_key"] = key_digits[:44]
        note = (out.get("notes") or "").strip()
        suffix = (
            "vendor_tax_id derived from chave de acesso"
            if not current
            else "vendor_tax_id corrected from chave de acesso (invalid/mismatched CNPJ)"
        )
        if suffix not in note:
            out["notes"] = f"{note}; {suffix}" if note else suffix
    elif is_valid_cnpj(current):
        out["vendor_tax_id"] = format_cnpj(str(current))

    # --- vendor_name ---
    name = normalize_vendor_name(out.get("vendor_name"))
    if name:
        out["vendor_name"] = name
    else:
        found = find_vendor_name(out.get("notes"), source_text)
        if found:
            out["vendor_name"] = found
            note = (out.get("notes") or "").strip()
            suffix = "vendor_name recovered from document text"
            if suffix not in note:
                out["notes"] = f"{note}; {suffix}" if note else suffix
        else:
            out["vendor_name"] = None

    return out
