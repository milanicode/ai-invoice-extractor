# ROI — ai-invoice-extractor

Estimated comparison: **traditional RPA** vs **lightweight AI agent** (this project).

## Scenario

A small company processes **50 invoices/month** (PDF or photos), extracts key fields, and consolidates them into Excel for finance/ops.

| Item | Traditional RPA | AI agent (#1) |
|------|-----------------|---------------|
| License | UiPath / AA / Power Automate (paid) | **$0** (OSS + Gemini free tier) |
| Initial setup | 2–5 days (selectors, exceptions) | **~2 h** (prompt + pdfplumber) |
| Maintenance/month | 4–8 h (layout changes break flows) | **~30 min** (LLM tolerates variation) |
| Infrastructure | Dedicated VM / bot runner | **Any office PC** (+ optional local Ollama) |
| Dependencies | Heavy, vendor lock-in | **5 pip packages** (Dockerized) |

## Estimated savings (annual)

| Item | RPA | AI agent |
|------|-----|----------|
| Licenses | $600–3,000/year | $0 |
| Maintenance hours (50 invoices/month) | ~60 h/year | ~6 h/year |
| Staff hourly rate (reference) | $80 | $80 |
| **Estimated total** | **$5,400–7,800** | **~$480** |

> Illustrative values in USD. Adjust with your actual volume and hourly cost.

## When regex is enough

For **standardized** text PDFs (same layout), the regex fallback already removes manual entry with no API cost. **Vision + LLM** handles scanned documents, phone photos, and layout variation — the typical cases that broke RPA.
