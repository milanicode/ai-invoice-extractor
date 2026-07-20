# ai-invoice-extractor

**Project #1** of the AI portfolio: invoices (PDF / JPEG / PNG) → LLM → Excel.

Replaces manual data entry / brittle RPA with a lightweight Python script, 100% OSS.

## Stack

| Package | Purpose |
|---------|---------|
| `pdfplumber` | Read embedded PDF text |
| `pypdfium2` | Render scanned PDF pages to images |
| `openpyxl` | Write Excel |
| `python-dotenv` | Config via `.env` |
| `google-genai` | Gemini text + vision (free tier) |

**Optional:** local Ollama with a vision model (stdlib `urllib`) · **Fallback:** regex (text PDFs only)

Built for **small-company finance/ops**: drop a month’s invoices, get one Excel file — no RPA license.

## Setup (Docker — recommended)

```bash
cd ai-invoice-extractor
cp .env.example .env
docker compose up -d --build
```

Free Gemini API key: [Google AI Studio](https://aistudio.google.com/apikey) → paste into `.env`

## Usage — drop a month folder

1. Create a month folder and drop invoices (PDF / JPG / PNG):

```text
incoming/2026-07/
  nf-001.pdf
  cupom.jpg
  foto-nota.png
```

2. Run once:

```bash
docker compose run --rm --entrypoint "" python python main.py incoming/2026-07 --fresh
```

Every supported file in that folder becomes a row in `output/invoices.xlsx`.

Use **`--fresh`** to wipe previous rows and keep only this run (recommended for clean tests). Without it, rows are **appended**.

### Other commands

```bash
# Demo (no API key — regex)
docker compose run --rm --entrypoint "" python python main.py --demo

# Sample Brazilian invoices
docker compose run --rm --entrypoint "" python python main.py incoming/Example_Invoices --fresh

# Single file
docker compose run --rm --entrypoint "" python python main.py incoming/Example_Invoices/Nfe.png

# Custom Excel path
docker compose run --rm --entrypoint "" python python main.py incoming/2026-07 -o output/jul-2026.xlsx
```

Or: `bash demo/run_demo.sh`

## Supported inputs

| Type | How it’s handled |
|------|------------------|
| PDF with text | Gemini text → Ollama → regex |
| Scanned PDF | Render pages → Gemini / Ollama vision |
| JPG / PNG / WEBP | Gemini / Ollama vision |

Images and scanned PDFs need `GEMINI_API_KEY` (or Ollama vision).

## Excel output

Columns: `source_file`, `provider`, `vendor_name`, `vendor_tax_id`, `invoice_number`, `issue_date`, `due_date`, `currency`, `subtotal`, `tax`, `total`, `notes`.

`provider`: `gemini`, `gemini-vision`, `ollama`, `ollama-vision`, or `regex`.

## Structure

```
ai-invoice-extractor/
├── main.py
├── docker-compose.yml   # run from this folder
├── Dockerfile
├── incoming/            # drop folders + Example_Invoices/
├── demo/
└── output/              # sample Excel result
```

## ROI

See [ROI.md](./ROI.md).

## Limitations

- Folder scan is **one level** (not recursive)
- Images / scanned PDFs need Gemini or Ollama vision (no offline OCR)
- Regex only for simple **text** PDFs
- Brazilian NF-e: if emitente CNPJ is missing or invalid, the tool derives/corrects it from the **chave de acesso** (check-digit validated when possible)
