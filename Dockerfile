FROM python:3.12-slim

WORKDIR /workspace/ai-invoice-extractor

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: keep container alive for interactive dev (see docker-compose.yml)
CMD ["sleep", "infinity"]
