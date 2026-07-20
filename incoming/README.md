# Drop folder

Put invoice files here by month, then run once from the project root:

```bash
docker compose run --rm --entrypoint "" python python main.py incoming/2026-07 --fresh
```

Example layout:

```
incoming/
├── Example_Invoices/   # portfolio samples
├── 2026-06/
│   ├── nf-001.pdf
│   ├── cupom.jpg
│   └── nota.png
└── 2026-07/
    └── ...
```

Supported: **PDF**, **PNG**, **JPG/JPEG**, **WEBP** (one level — not recursive).
