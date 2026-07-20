import base64
import json
import re
import urllib.error
import urllib.request
from typing import Any

from google import genai
from google.genai import types

from br_tax_id import enrich_invoice_data, is_blank, is_valid_cnpj, only_digits
from config import GEMINI_API_KEY, GEMINI_MODEL, OLLAMA_HOST, OLLAMA_MODEL

JSON_SCHEMA = """Return ONLY valid JSON with these keys (use null if missing):
{
  "vendor_name": string,
  "vendor_tax_id": string,
  "access_key": string,
  "invoice_number": string,
  "issue_date": string,
  "due_date": string,
  "currency": string,
  "subtotal": number,
  "tax": number,
  "total": number,
  "notes": string
}
Rules:
- vendor_* = EMITENTE / issuer (seller), NEVER destinatário/remetente (buyer) or transportador.
- vendor_name = razão social / nome do emitente (header / logo area on DANFE). Never leave it
  null if the issuer name is visible anywhere on the page.
- For Brazil NF-e/DANFE: vendor_tax_id = emitente CNPJ (14 digits, keep punctuation if visible).
- If the CNPJ box next to the issuer is hard to read, STILL fill vendor_tax_id by reading the
  Chave de Acesso (44 digits). The emitente CNPJ is digits 7-20 of that key
  (0-based index 6:20). Also put the full 44-digit key in access_key.
- Do not use CPF/CNPJ from Destinatário or Transportador for vendor_tax_id.
- Use ISO dates when possible. Amounts as numbers without currency symbols.
- Prefer currency BRL when R$ appears."""

PROMPT_TEXT = f"Extract invoice data from the document below.\n{JSON_SCHEMA}\n\nDOCUMENT:\n"
PROMPT_VISION = (
    "Extract invoice data from the Brazilian (or other) invoice image(s) below. "
    "Handle DANFE / NF-e layouts carefully.\n"
    f"{JSON_SCHEMA}"
)

EMITENTE_RETRY_PROMPT = """This is a Brazilian DANFE / NF-e image.
Return ONLY JSON:
{
  "vendor_name": string|null,
  "vendor_tax_id": string|null,
  "access_key": string|null
}

Rules:
- vendor_name = EMITENTE / issuer razão social only (top/header). Never destinatário or transportador.
- vendor_tax_id = EMITENTE CNPJ only.
- If CNPJ is hard to read, use Chave de Acesso digits 7-20 and also return the full 44-digit access_key.
- Do not leave vendor_name null if any issuer name/logo text is visible.
"""

SCANNED_PDF_HELP = (
    "Image or scanned PDF needs a vision model. "
    "Set GEMINI_API_KEY or OLLAMA_HOST with a vision-capable model "
    "(e.g. llava, llama3.2-vision)."
)


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=GEMINI_API_KEY)


def _retry_emitente_from_vision(images: list[tuple[bytes, str]]) -> dict[str, Any]:
    client = _gemini_client()
    contents: list[Any] = [EMITENTE_RETRY_PROMPT]
    for data, mime_type in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return _parse_json(response.text or "{}")


def extract_with_gemini(text: str) -> dict[str, Any]:
    client = _gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=PROMPT_TEXT + text,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    return enrich_invoice_data(_parse_json(response.text or "{}"), source_text=text)


def extract_with_gemini_vision(images: list[tuple[bytes, str]]) -> dict[str, Any]:
    """images: list of (bytes, mime_type)."""
    client = _gemini_client()
    contents: list[Any] = [PROMPT_VISION]
    for data, mime_type in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0,
        ),
    )
    data = enrich_invoice_data(_parse_json(response.text or "{}"))
    needs_retry = is_blank(data.get("vendor_name")) or not is_valid_cnpj(data.get("vendor_tax_id"))
    if needs_retry:
        retry = _retry_emitente_from_vision(images)
        if retry.get("vendor_name") and is_blank(data.get("vendor_name")):
            data["vendor_name"] = retry["vendor_name"]
        if retry.get("access_key"):
            if is_blank(data.get("access_key")) or len(only_digits(str(retry["access_key"]))) > len(
                only_digits(str(data.get("access_key") or ""))
            ):
                data["access_key"] = retry["access_key"]
        if retry.get("vendor_tax_id") and not is_valid_cnpj(data.get("vendor_tax_id")):
            data["vendor_tax_id"] = retry["vendor_tax_id"]
        before_name = data.get("vendor_name")
        before_tax = data.get("vendor_tax_id")
        data = enrich_invoice_data(data)
        note = (data.get("notes") or "").strip()
        extras: list[str] = []
        if is_blank(before_name) and not is_blank(data.get("vendor_name")):
            extras.append("vendor_name recovered via emitente-focused vision retry")
        if (not is_valid_cnpj(before_tax)) and (
            is_valid_cnpj(data.get("vendor_tax_id")) or not is_blank(data.get("vendor_tax_id"))
        ):
            if "chave de acesso" not in note.lower() and "CNPJ-focused" not in note:
                extras.append("vendor_tax_id recovered via emitente-focused vision retry")
        for suffix in extras:
            if suffix not in note:
                note = f"{note}; {suffix}" if note else suffix
        data["notes"] = note or data.get("notes")
    return data

def extract_with_ollama(text: str) -> dict[str, Any]:
    if not OLLAMA_HOST:
        raise RuntimeError("OLLAMA_HOST not set")

    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": PROMPT_TEXT + text + "\n\nJSON:",
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unavailable at {OLLAMA_HOST}") from exc

    return enrich_invoice_data(_parse_json(body.get("response", "{}")), source_text=text)


def extract_with_ollama_vision(images: list[tuple[bytes, str]]) -> dict[str, Any]:
    """images: list of (bytes, mime_type). Ollama chat API uses raw base64 only."""
    if not OLLAMA_HOST:
        raise RuntimeError("OLLAMA_HOST not set")

    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT_VISION,
                    "images": [
                        base64.b64encode(data).decode("ascii") for data, _mime in images
                    ],
                }
            ],
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama unavailable at {OLLAMA_HOST}") from exc

    message = body.get("message", {})
    return enrich_invoice_data(_parse_json(message.get("content", "{}")))


def extract_with_regex(text: str) -> dict[str, Any]:
    def first(pattern: str, flags: int = re.I) -> str | None:
        match = re.search(pattern, text, flags)
        return match.group(1).strip() if match else None

    def amount(pattern: str) -> float | None:
        raw = first(pattern)
        if not raw:
            return None
        # US: 1,500.00 | BR: 1.500,00
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                normalized = raw.replace(".", "").replace(",", ".")
            else:
                normalized = raw.replace(",", "")
        elif "," in raw:
            normalized = raw.replace(".", "").replace(",", ".")
        else:
            normalized = raw
        try:
            return float(normalized)
        except ValueError:
            return None

    currency = None
    if "R$" in text:
        currency = "BRL"
    elif re.search(r"\$\s*[\d]", text):
        currency = "USD"

    data = {
        "vendor_name": first(r"(?:emitente|fornecedor|vendor)[\s:]+(.+)"),
        "vendor_tax_id": first(r"(?:cnpj|cpf|tax id)[\s:]*([\d./-]+)", re.I),
        "invoice_number": first(r"(?:nota|invoice|nf)[\s#:.-]*([A-Z0-9-]+)", re.I),
        "issue_date": first(r"(?:emiss[aã]o|issue date)[\s:]*([\d/-]+)", re.I),
        "due_date": first(r"(?:vencimento|due date)[\s:]*([\d/-]+)", re.I),
        "currency": currency,
        "subtotal": amount(r"(?:subtotal)[\s:]*R?\$?\s*([\d.,]+)"),
        "tax": amount(r"(?:impostos?|tax)[\s:]*R?\$?\s*([\d.,]+)"),
        "total": amount(r"(?:valor total|total)[\s:]*R?\$?\s*([\d.,]+)"),
        "notes": "regex fallback (no LLM)",
    }
    return enrich_invoice_data(data, source_text=text)


def extract_invoice(
    *,
    text: str | None = None,
    images: list[tuple[bytes, str]] | None = None,
) -> tuple[dict[str, Any], str]:
    """Returns (data, provider_used). images: list of (bytes, mime_type)."""
    gemini_error: Exception | None = None

    if images:
        if GEMINI_API_KEY:
            try:
                return extract_with_gemini_vision(images), "gemini-vision"
            except Exception as exc:
                gemini_error = exc

        if OLLAMA_HOST:
            try:
                return extract_with_ollama_vision(images), "ollama-vision"
            except Exception:
                pass

        if gemini_error:
            raise RuntimeError(f"Gemini vision failed: {gemini_error}") from gemini_error
        raise ValueError(SCANNED_PDF_HELP)

    if not text:
        raise ValueError("No invoice content to extract.")

    if GEMINI_API_KEY:
        try:
            return extract_with_gemini(text), "gemini"
        except Exception as exc:
            gemini_error = exc

    if OLLAMA_HOST:
        try:
            return extract_with_ollama(text), "ollama"
        except Exception:
            pass

    if gemini_error:
        print(f"WARN  Gemini failed, using regex fallback: {gemini_error}", flush=True)

    return extract_with_regex(text), "regex"
