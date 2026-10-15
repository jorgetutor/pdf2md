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
        # repeated titles ("Introduction" in every chapter) take their levels in order
        levels.setdefault(norm(title), []).append(lvl)
        toc_count[norm(title)] = toc_count.get(norm(title), 0) + 1
    minor = max((max(v) for v in levels.values()), default=2) + 1

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
            queue = levels.get(key)
            lvl = (queue.pop(0) if len(queue) > 1 else queue[0]) if queue else minor
        else:
            lvl = len(m.group(1))
        lines[i] = "#" * min(lvl, 6) + " " + text
    return "\n".join(lines)


def title_keys(title):
    """Match keys for a bookmark title, with and without a leading '1 ', 'B ', 'Chapter 3:'."""
    keys = {norm(title)}
    short = re.sub(r"^\s*(chapter|part|appendix)?\s*([0-9]+|[A-Z]|[IVXLC]+)[.:]?\s+", "", title, flags=re.I)
    if short.strip():
        keys.add(norm(short))
    return keys - {""}


def add_missing_headings(chunks, toc):
    """Make sure every bookmark appears as a heading on its page.

    Some PDFs put chapter titles in images or decorative text the layout model does not
    tag as headings. For each bookmark: rename a matching heading on that page to the
    bookmark title, else promote a matching plain line, else insert the title at the top
    of the page.
    """
    by_page = {}
    for _lvl, title, page in toc:
        by_page.setdefault(page, []).append(title.strip())
    for chunk in chunks:
        titles = by_page.get(chunk["metadata"]["page_number"])
        if not titles:
            continue
        lines = chunk["text"].split("\n")
        inserted = []
        for title in titles:
            keys = title_keys(title)
            for i, line in enumerate(lines):
                plain = re.sub(r"^#{1,6}\s+|[*_]", "", line).strip()
                if plain and norm(plain) in keys:
                    lines[i] = "# " + title
                    break
            else:
                inserted.append("# " + title)
        chunk["text"] = "\n\n".join(inserted + ["\n".join(lines)])
    return chunks


def join_page_breaks(md):
    """Re-join paragraphs split by a page break (line not ending a sentence + lowercase next)."""
    return re.sub(r"(?m)([a-z,;’'\-])[ \t]*\n\n+(?=[a-z])", r"\1 ", md)


def use_original_images(md, doc, img_dir="images"):
    """Replace the library's re-rendered figure PNGs with the original embedded images.

    pymupdf4llm renders each picture area of the page (resampled, re-encoded). When the
    figures on a page map one-to-one to embedded raster images, save those images'
    original bytes instead (exact pixels, original JPEG/PNG). Otherwise keep the render.
    Files are renamed to images/p<page>-<n>.<ext>.
    """
    link_re = re.compile(r"!\[([^\]]*)\]\((" + re.escape(img_dir) + r"/[^)]*?-(\d{4})-(\d+)\.(\w+))\)")
    by_page = {}
    for m in link_re.finditer(md):
        by_page.setdefault(int(m.group(3)), []).append(m)

    replace = {}
    for pno, links in by_page.items():
        page = doc[pno - 1]  # file names use 1-based page numbers
        infos = [i for i in page.get_image_info(xrefs=True)
                 if i["xref"] and i["bbox"][2] - i["bbox"][0] > 20 and i["bbox"][3] - i["bbox"][1] > 20]
        infos.sort(key=lambda i: (round(i["bbox"][1]), i["bbox"][0]))
        links.sort(key=lambda m: int(m.group(4)))
        exact = len(infos) == len(links)
        for n, m in enumerate(links, 1):
            old = m.group(2)
            if exact:
                img = doc.extract_image(infos[n - 1]["xref"])
                ext = img["ext"] if img["ext"] in ("jpeg", "jpg", "png") else None
                if ext:
                    new = f"{img_dir}/p{pno:03d}-{n}.{'jpg' if ext == 'jpeg' else ext}"
                    with open(new, "wb") as fh:
                        fh.write(img["image"])
                    os.remove(old)
                    replace[old] = new
                    continue
            new = f"{img_dir}/p{pno:03d}-{n}.{m.group(5)}"
            os.replace(old, new)
            replace[old] = new
    return link_re.sub(lambda m: f"![{m.group(1)}]({replace.get(m.group(2), m.group(2))})", md)


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
        page_chunks=True,
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

    chunks = pymupdf4llm.to_markdown(doc, **kwargs)
    toc = doc.get_toc()
    chunks = add_missing_headings(chunks, toc)
    if a.page_separators:
        md = "".join(f"{c['text']}\n\n<!-- end of page {c['metadata']['page_number']} -->\n\n"
                     for c in chunks)
    else:
        md = "\n\n".join(c["text"] for c in chunks)
    if not a.no_images:
        md = use_original_images(md, doc)
    md = fix_headings(md, toc)
    md = join_page_breaks(md)
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)

    meta = doc.metadata or {}
    front = [f"{k}: {meta[k].strip()}" for k in ("title", "author") if meta.get(k, "").strip()]
    if front:
        front.append(f"source: {os.path.basename(a.pdf)}")
        md = "---\n" + "\n".join(front) + "\n---\n\n" + md

    with open(output, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"wrote {output} ({doc.page_count} pages, {len(md.split())} words)", file=sys.stderr)


if __name__ == "__main__":
    main()
