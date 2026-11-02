# pdf2md

Convert PDF documents (books, papers, reports, manuals...) into clean, LLM-friendly Markdown. Only Docker is required on the host.

- Headings follow the PDF's bookmarks (e.g. chapter `#`, section `##`, subsection `###`)
- Lists, tables and paragraphs reconstructed by [pymupdf4llm](https://github.com/pymupdf/pymupdf4llm)'s layout model
- Figures saved as the **original embedded images** (no re-rendering), linked from the Markdown
- Repeated images (byte-identical files, e.g. a logo on every chapter) stored once, all links point to it
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
pdf2md *.pdf -o ~/llm-docs          # several documents, custom output folder
pdf2md document.pdf --no-images      # text only
pdf2md document.pdf --pages 1-40 --lang spa
pdf2md --dedupe "<document name>"/  # dedupe images of an already converted folder
pdf2md --help                        # all options
```

Output:

```
<document name>/
├── <document name>.md
└── images/p031-1.jpg, p032-1.jpg, ...
```

## Options

| Option | Description |
|---|---|
| `-o`, `--output-dir DIR` | Each document goes to `DIR/<document name>/<document name>.md` (+ `images/`). Default: current directory. |
| `--pages SPEC` | Convert only these pages (1-based), e.g. `1-20` or `3,5,10-12`. |
| `--no-images` | Don't extract images (text only). Default: save them to `images/` and link them. |
| `--no-dedupe` | Keep byte-identical duplicate images. Default: store one copy and point all links to it. |
| `--page-separators` | Add a `<!-- end of page N -->` comment after each page. |
| `--no-ocr` | Never OCR pages. Default: OCR only pages that need it (e.g. scanned pages). |
| `--force-ocr` | OCR every page, even those with text. |
| `--lang LANG` | OCR language(s): `eng` (default), `spa` or `eng+spa`. |
| `--keep-headers` | Keep running page headers/footers. Default: remove them. |
| `--dedupe DIR...` | Don't convert: deduplicate the images of already converted folders (must be the first argument). |
| `-h`, `--help` | Show usage and options. |

Environment:

| Variable | Description |
|---|---|
| `PDF2MD_IMAGE` | Docker image to run. Default: `ghcr.io/jorgetutor/pdf2md:latest`. Pin a version with e.g. `PDF2MD_IMAGE=ghcr.io/jorgetutor/pdf2md:1.0.0`. |

## Without the wrapper

```bash
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/in:ro -v "$PWD":/out \
  ghcr.io/jorgetutor/pdf2md "/in/document.pdf" -o /out

# dedupe images of an already converted folder (the wrapper's --dedupe)
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD/<document name>":/doc \
  ghcr.io/jorgetutor/pdf2md /doc --dedupe-only
```

The options above apply as well, except `--dedupe` (use `--dedupe-only` on the folder).

## Releases

Every push to `main` publishes `:latest`; a tag `vX.Y.Z` publishes `:X.Y.Z` and `:X.Y`
(GitHub Actions, linux/amd64 + linux/arm64).

## License

[MIT](LICENSE): use, copy, modify and distribute freely. Provided as is, without warranty
of any kind; the author is not liable for any damages arising from its use.
