#!/usr/bin/env python3
"""Convert a PDF to Markdown with pymupdf4llm (runs inside the pdf2md Docker image)."""
import argparse
import os
import re
import sys

import pymupdf
import pymupdf4llm


def parse_pages(spec, count):
    pages = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        pages.extend(range(int(a) - 1, int(b or a)))
    return [p for p in pages if 0 <= p < count]


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower().replace("’", "'"))


def fix_headings(md, toc):
    """Strip bold/italic from headings and, when the PDF has bookmarks, use them for levels.

    Headings not in the bookmarks go one level below the deepest bookmark; table-of-contents
    lines that the layout model promoted to headings (repeats of a later real heading,
    appearing before it) are turned back into plain lines.
    """
    levels, toc_count = {}, {}
    for lvl, title, _page in toc:
        levels.setdefault(norm(title), lvl)
        toc_count[norm(title)] = toc_count.get(norm(title), 0) + 1
    minor = max(levels.values(), default=2) + 1

    lines = md.split("\n")
    heads = [(i, m) for i, l in enumerate(lines) if (m := re.match(r"^(#{1,6})\s+(.*?)\s*$", l))]
    # if a title appears as a heading more often than in the bookmarks, the extra
    # (earliest) occurrences come from the printed table of contents
    head_count = {}
    for _i, m in heads:
        k = norm(re.sub(r"[*_]", "", m.group(2)))
        head_count[k] = head_count.get(k, 0) + 1
    extra = {k: n - toc_count[k] for k, n in head_count.items() if n > toc_count.get(k, n)}
    for i, m in heads:
        text = re.sub(r"(\*\*|__|\*|_)(.+?)\1", r"\2", m.group(2)).strip()
        text = re.sub(r"^[*_]+|[*_]+$", "", text).strip().rstrip(":")
        key = norm(text)
        if levels:
            if extra.get(key, 0) > 0:   # TOC entry promoted to heading
                extra[key] -= 1
                lines[i] = text
                continue
            lvl = levels.get(key, minor)
        else:
            lvl = len(m.group(1))
        lines[i] = "#" * min(lvl, 6) + " " + text
    return "\n".join(lines)


def join_page_breaks(md):
    """Re-join paragraphs split by a page break (line not ending a sentence + lowercase next)."""
    return re.sub(r"(?m)([a-z,;’'\-])[ \t]*\n\n+(?=[a-z])", r"\1 ", md)


def doc_name(pdf_path):
    """Folder/file name for a document: the PDF file name without extension."""
    return os.path.splitext(os.path.basename(pdf_path))[0] or "document"


def main():
    ap = argparse.ArgumentParser(description="Convert a PDF to LLM-friendly Markdown.")
    ap.add_argument("pdf")
    ap.add_argument("--out-root", default=".",
                    help="each document goes to <out-root>/<document name>/<document name>.md (+ images/)")
    ap.add_argument("--pages", help="1-based pages, e.g. 1-20 or 3,5,10-12")
    ap.add_argument("--no-images", action="store_true",
                    help="do not extract images (default: save to images/ and link them)")
    ap.add_argument("--page-separators", action="store_true",
                    help="mark page boundaries in the output")
    ap.add_argument("--no-ocr", action="store_true", help="never OCR pages")
    ap.add_argument("--force-ocr", action="store_true", help="OCR every page")
    ap.add_argument("--lang", default="eng", help="OCR language(s), e.g. eng, spa, eng+spa")
    ap.add_argument("--keep-headers", action="store_true",
                    help="keep running page headers/footers")
    a = ap.parse_args()
    print(f"converting {os.path.basename(a.pdf)} ...", file=sys.stderr)

    slug = doc_name(a.pdf)
    out_dir = os.path.abspath(os.path.join(a.out_root, slug))
    os.makedirs(out_dir, exist_ok=True)
    output = os.path.join(out_dir, slug + ".md")
    doc = pymupdf.open(a.pdf)
    os.chdir(out_dir)  # image links in the markdown become relative (images/...)
    kwargs = dict(
        show_progress=False,
        page_separators=a.page_separators,
        use_ocr=not a.no_ocr,
        force_text=False,  # don't dump text found inside charts/pictures
        force_ocr=a.force_ocr,
        ocr_language=a.lang,
        header=a.keep_headers,
        footer=a.keep_headers,
    )
    if a.pages:
        kwargs["pages"] = parse_pages(a.pages, doc.page_count)
    if not a.no_images:
        os.makedirs("images", exist_ok=True)
        # fallback renders (vector figures) at 300 dpi instead of the default 150
        kwargs.update(write_images=True, image_path="images", dpi=300)

    md = pymupdf4llm.to_markdown(doc, **kwargs)
    if not a.no_images:
        md = use_original_images(md, doc)
    md = fix_headings(md, doc.get_toc())
    md = join_page_breaks(md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)

    meta = doc.metadata or {}
    front = [f"{k}: {meta[k].strip()}" for k in ("title", "author") if meta.get(k, "").strip()]
    if front:
        front.append(f"source: {slug}.pdf")
        md = "---\n" + "\n".join(front) + "\n---\n\n" + md

    with open(output, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote {output} ({doc.page_count} pages, {len(md.split())} words)", file=sys.stderr)


if __name__ == "__main__":
    main()
