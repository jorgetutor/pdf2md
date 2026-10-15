# PDF -> Markdown converter for LLM use (pymupdf4llm + layout model + tesseract OCR)
FROM python:3.12-slim
LABEL org.opencontainers.image.description="Convert PDF documents to LLM-friendly Markdown (pymupdf4llm + tesseract OCR)"

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pymupdf4llm==1.28.2

ENV HOME=/tmp
COPY convert.py /app/convert.py
WORKDIR /data
ENTRYPOINT ["python", "/app/convert.py"]
