r"""Build the story pages: stories/<story>/story.md -> stories/<story>/index.html.

    python scripts/build_stories.py

story.md conventions
- front matter (--- ... ---) with title, subtitle, status
- citations: [text](cat:<catalogue id>) link to the source's entry on the index site
- figures:   ::: figure <file in figures/> [narrow]
             caption (markdown) ...
             :::
- figure references: {ch5-route-map} (the figure's file name without .jpg) becomes its number, e.g. 5.1;
  figures are numbered in the order they appear, per chapter (from the chN- prefix)
"""
import html
import re
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent.parent
TEMPLATE = HERE / "scripts" / "story_template.html"


def build(folder):
    src = (folder / "story.md").read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"---\n(.*?)\n---\n", src, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
        src = src[m.end():]
    # number figures in order of appearance, per chapter
    numbers, counts = {}, {}
    for name in re.findall(r"^::: figure (\S+)", src, re.M):
        slug = name.rsplit(".", 1)[0]
        ch = re.match(r"ch(\d+)-", slug)
        ch = ch.group(1) if ch else "0"
        counts[ch] = counts.get(ch, 0) + 1
        numbers[slug] = f"{ch}.{counts[ch]}"
    missing = [s for s in re.findall(r"\{(ch\d+-[\w-]+)\}", src) if s not in numbers]
    if missing:
        raise SystemExit(f"figure references with no figure: {missing}")
    src = re.sub(r"\{(ch\d+-[\w-]+)\}", lambda k: numbers[k.group(1)], src)
    src = re.sub(r"\]\(cat:([^)\s]+)\)", lambda k: f"](../../site/#{k.group(1)})", src)

    def fig(k):
        name, opts, cap = k.group(1), (k.group(2) or "").split(), k.group(3)
        if not (folder / "figures" / name).exists():
            raise SystemExit(f"missing figure file {name}")
        caption = markdown.markdown(cap.strip())[3:-4]  # strip <p></p>
        slug = name.rsplit(".", 1)[0]
        cls = "fig narrow" if "narrow" in opts else "fig"
        return (f'\n<figure class="{cls}" id="fig-{slug}"><a href="figures/{name}"><img loading="lazy" '
                f'src="figures/{name}" alt=""></a><figcaption>{caption}</figcaption></figure>\n')

    src = re.sub(r"^::: figure (\S+)([^\n]*)\n(.*?)\n:::\s*$", fig, src, flags=re.M | re.S)
    body = markdown.markdown(src, extensions=["extra"])
    body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', body)
    page = (TEMPLATE.read_text(encoding="utf-8")
            .replace("{{title}}", html.escape(meta.get("title", folder.name)))
            .replace("{{subtitle}}", html.escape(meta.get("subtitle", "")))
            .replace("{{status}}", html.escape(meta.get("status", "")))
            .replace("{{body}}", body))
    (folder / "index.html").write_text(page, encoding="utf-8")
    print(f"{folder.relative_to(HERE)}/index.html: {len(numbers)} figures")


def main():
    for folder in sorted((HERE / "stories").iterdir()):
        if (folder / "story.md").exists():
            build(folder)


if __name__ == "__main__":
    main()
