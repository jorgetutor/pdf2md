# pdf2md

Convert PDF documents (books, papers, reports, manuals...) into clean, LLM-friendly Markdown. Only Docker is required on the host.

- Headings follow the PDF's bookmarks (e.g. chapter `#`, section `##`, subsection `###`)
- Lists, tables and paragraphs reconstructed by [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm)'s layout model
- Figures saved as the **original embedded images** (no re-rendering), linked from the Markdown
- OCR for scanned pages (tesseract, English + Spanish)

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/jorgetutor/pdf2md/main/pdf2md.sh -o ~/.local/bin/pdf2md
chmod +x ~/.local/bin/pdf2md
```

The first run pulls `ghcr.io/jorgetutor/pdf2md:latest`.

## Usage

```bash
pdf2md document.pdf                  # -> ./<document name>/<document name>.md + images/
pdf2md *.pdf --out-root ~/llm-docs   # several documents, custom output folder
pdf2md document.pdf --no-images      # text only
pdf2md document.pdf --pages 1-40 --lang spa
pdf2md --help                        # all options
```

Output:

```
<document name>/
├── <document name>.md
└── images/p031-1.jpg, p032-1.jpg, ...
```

Pin a version with `PDF2MD_IMAGE=ghcr.io/jorgetutor/pdf2md:1.0.0 pdf2md document.pdf`.

## Without the wrapper

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/in:ro -v "$PWD":/out \
  ghcr.io/jorgetutor/pdf2md "/in/document.pdf" --out-root /out
```

## Releases

Every push to `main` publishes `:latest`; a tag `vX.Y.Z` publishes `:X.Y.Z` and `:X.Y`
(GitHub Actions, linux/amd64 + linux/arm64).

## License

[MIT](LICENSE): use, copy, modify and distribute freely. Provided as is, without warranty
of any kind; the author is not liable for any damages arising from its use.
