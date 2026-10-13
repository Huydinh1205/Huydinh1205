"""
Build a neofetch-style ASCII portrait card (SVG, dark + light) from a photo.

Usage:
    pip install opencv-python numpy
    python scripts/build_ascii_card.py /path/to/photo.jpg   # new portrait + card
    python scripts/build_ascii_card.py --card-only          # keep portrait, refresh info panel

Outputs:
    assets/huy-ascii-card.svg        - dark card (GitHub dark theme)
    assets/huy-ascii-card-light.svg  - light card (GitHub light theme)
    assets/ascii-portrait.txt        - plain-text ASCII portrait
    assets/github-stats.json         - last fetched GitHub numbers (fallback when offline)

Pipeline: GrabCut background removal -> CLAHE local contrast ->
downsample to a character grid -> map inverted luminance to a density ramp.

The GitHub section (uptime, repos, last push) is pulled from the GitHub API.
A scheduled workflow (.github/workflows/refresh-card.yml) re-runs this daily
with --card-only, so the card stays live without touching the portrait.
"""
import sys, html, os, json, datetime, urllib.request

PHOTO = sys.argv[1] if len(sys.argv) > 1 else "photo.jpg"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT_DIR = os.path.join(ROOT, "assets")
GH_USER = os.environ.get("GH_USER", "Huydinh1205")
COLS, ROWS = 50, 32
RAMP = " .,:;i1tfLCG08@"

# ---------------------------------------------------------------- portrait ---
def cutout(path):
    import cv2, numpy as np
    img = cv2.imread(path)
    H, W = img.shape[:2]
    mask = np.full((H, W), cv2.GC_PR_BGD, np.uint8)
    cv2.rectangle(mask, (int(W*.06), int(H*.03)), (int(W*.94), H-1), cv2.GC_PR_FGD, -1)
    cv2.ellipse(mask, (W//2, int(H*.35)), (int(W*.18), int(H*.16)), 0, 0, 360, cv2.GC_FGD, -1)
    cv2.rectangle(mask, (int(W*.3), int(H*.88)), (int(W*.7), H-1), cv2.GC_FGD, -1)
    mask[:int(H*.02), :] = cv2.GC_BGD
    mask[:, :int(W*.04)] = cv2.GC_BGD
    mask[:, int(W*.93):] = cv2.GC_BGD
    cv2.grabCut(img, mask, None, np.zeros((1, 65), np.float64),
                np.zeros((1, 65), np.float64), 6, cv2.GC_INIT_WITH_MASK)
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n > 1:
        fg = ((lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])) * 255).astype(np.uint8)
    return img, fg

def asciify(img, fg):
    import cv2, numpy as np
    ys, xs = np.where(fg > 0)
    x0, x1, y0 = xs.min(), xs.max(), ys.min()
    y1 = min(ys.max(), y0 + int((ys.max() - y0) * 0.80))     # trim lower torso
    crop, m = img[y0:y1, x0:x1], fg[y0:y1, x0:x1]
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gc = cv2.createCLAHE(clipLimit=3.2, tileGridSize=(8, 8)).apply(g).astype(np.float32)
    G = cv2.resize(0.8 * gc + 0.2 * g.astype(np.float32), (COLS, ROWS), interpolation=cv2.INTER_AREA)
    G = G + 0.55 * (G - cv2.GaussianBlur(G, (0, 0), 1.1))    # unsharp
    inside = cv2.resize(m, (COLS, ROWS), interpolation=cv2.INTER_AREA) > 110
    lo, hi = np.percentile(G[inside], 1), np.percentile(G[inside], 99)
    v = 1.0 - np.clip((G - lo) / (hi - lo + 1e-6), 0, 1)     # dark pixels -> dense glyphs
    return ["".join(RAMP[min(len(RAMP)-1, int(v[r, x] * len(RAMP)))] if inside[r, x] else " "
                    for x in range(COLS)).rstrip() for r in range(ROWS)]

# ------------------------------------------------------------ github stats ---
STATS_FILE = os.path.join(OUT_DIR, "github-stats.json")

def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": GH_USER})
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def github_stats():
    """Fetch live numbers; fall back to the last saved ones when offline."""
    try:
        user = _get(f"https://api.github.com/users/{GH_USER}")
        repos = _get(f"https://api.github.com/users/{GH_USER}/repos?sort=pushed&per_page=20&type=owner")
        latest = next((r for r in repos if not r["fork"] and r["name"].lower() != GH_USER.lower()), None)
        stats = {"created_at": user["created_at"], "public_repos": user["public_repos"],
                 "last_repo": latest["name"] if latest else "",
                 "last_push": latest["pushed_at"] if latest else ""}
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
        return stats
    except Exception as e:                                     # offline / rate-limited
        print(f"GitHub API unavailable ({e}); using {os.path.basename(STATS_FILE)}")
        try:
            return json.load(open(STATS_FILE))
        except Exception:
            return None

def uptime(created_iso, today=None):
    c = datetime.date.fromisoformat(created_iso[:10])
    t = today or datetime.datetime.now(datetime.timezone.utc).date()
    months = (t.year - c.year) * 12 + (t.month - c.month) - (t.day < c.day)
    anchor_m = c.month + months
    anchor = datetime.date(c.year + (anchor_m - 1) // 12, (anchor_m - 1) % 12 + 1, min(c.day, 28))
    days = (t - anchor).days
    y, m = divmod(months, 12)
    unit = lambda n, w: f"{n} {w}" + ("" if n == 1 else "s")
    return ", ".join([unit(y, "year"), unit(m, "month"), unit(days, "day")])

def github_rows(s):
    if not s:
        return []
    rows = [("blank",), ("sec", "GitHub"),
            ("row", "Uptime", uptime(s["created_at"])),
            ("row", "Repos", f'{s["public_repos"]} public, more in private')]
    if s.get("last_repo"):
        rows.append(("row", "Last.Push", f'{s["last_repo"]} ({s["last_push"][:10]})'))
    return rows

# -------------------------------------------------------------------- card ---
FS, LH, PAD, GAP, LAB_COL, VAL_MAX = 12.0, 14.0, 22, 28, 24, 44
CW = FS * 0.60
FAMILY = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace'
THEMES = {
    "dark":  dict(bg="#0d1117", border="#30363d", art="#b9c2cc", head="#f0883e",
                  label="#ff7b72", val="#c9d1d9", dot="#343b45"),
    "light": dict(bg="#ffffff", border="#d0d7de", art="#57606a", head="#bc4c00",
                  label="#cf222e", val="#24292f", dot="#c3cad3"),
}

INFO_TOP = [
    ("sec", "ryan@huy"),
    ("row", "Host", "University of Technology Sydney"),
    ("row", "Kernel", "B. Artificial Intelligence (2025 - 2027)"),
    ("row", "Prev", "B. Computer Science, HCMUT - GPA 3.6/4.0"),
    ("row", "Benchmark", "WAM 88.88 - GPA 6.75/7.0"),
    ("row", "Role", "Data Engineer @ Nallawilli Bunjil"),
    ("row", "Next", "CV Research Intern @ CSIRO (Nov 2026)"),
    ("row", "Awards", "FEIT Dean's List 2026"),
    ("row", "Location", "Sydney, NSW, Australia"),
    ("row", "Status", "Open to internships and graduate roles"),
    ("blank",),
    ("sec", "Stack"),
    ("row", "Languages.Programming", "Python, C++, TypeScript, Java, SQL"),
    ("row", "Languages.Real", "Vietnamese, English"),
    ("row", "ML.Frameworks", "PyTorch, Lightning, LangChain, YOLO"),
    ("row", "Research", "VLM, RAG, GAN, Robust CV, Dynamic GNN"),
    ("row", "Geo", "rasterio, GeoPandas, GDAL, NDVI/NDRE"),
    ("row", "Web", "Next.js, React, FastAPI, Spring Boot"),
    ("row", "Data", "Pandas, NumPy, PostgreSQL, Redis, Docker"),
]
INFO_BOTTOM = [
    ("blank",),
    ("sec", "Contact"),
    ("row", "Email", "huy.quoc1205@gmail.com"),
    ("row", "LinkedIn", "quoc-huy-dinh-773550387"),
    ("row", "HuggingFace", "Huydinh1205"),
    ("row", "Portfolio", "dinhquochuy.vercel.app"),
]

def svg(art, info, t):
    esc = lambda s: html.escape(s, quote=False)
    art_w = max(len(l) for l in art) * CW
    info_w = (LAB_COL + VAL_MAX) * CW
    rows = max(len(art), len(info))
    W = int(PAD * 2 + art_w + GAP + info_w)
    H = int(PAD * 2 + rows * LH + 4)
    art_off = (rows - len(art)) // 2                          # centre portrait vertically
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family=\'{FAMILY}\'>',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{t["bg"]}" stroke="{t["border"]}"/>',
         f'<g font-size="{FS}" fill="{t["art"]}">']
    for i, l in enumerate(art):                       # nbsp keeps indentation in every renderer
        o.append(f'<text x="{PAD}" y="{PAD+FS+(i+art_off)*LH:.1f}">{esc(l).replace(" ", chr(160))}</text>')
    o.append('</g>')
    x0 = PAD + art_w + GAP
    xv = x0 + LAB_COL * CW
    o.append(f'<g font-size="{FS}">')
    for i, r in enumerate(info):
        y = PAD + FS + i * LH
        if r[0] == "blank":
            continue
        if r[0] == "sec":
            o.append(f'<text x="{x0:.1f}" y="{y:.1f}" fill="{t["head"]}" font-weight="bold">{esc(r[1])}</text>')
            o.append(f'<line x1="{x0+(len(r[1])+1)*CW:.1f}" y1="{y-4:.1f}" x2="{x0+info_w:.1f}" '
                     f'y2="{y-4:.1f}" stroke="{t["border"]}"/>')
        else:
            lab = r[1] + ":"
            o.append(f'<text x="{x0:.1f}" y="{y:.1f}" fill="{t["label"]}">{esc(lab)}</text>')
            o.append(f'<text x="{xv:.1f}" y="{y:.1f}" fill="{t["val"]}">{esc(r[2])}</text>')
            a, b = x0 + (len(lab) + 1) * CW, xv - CW * 0.6
            if b - a > 6:
                o.append(f'<line x1="{a:.1f}" y1="{y-3.5:.1f}" x2="{b:.1f}" y2="{y-3.5:.1f}" '
                         f'stroke="{t["dot"]}" stroke-width="1" stroke-dasharray="1 3"/>')
    o.append('</g></svg>')
    return "\n".join(o)

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    portrait = os.path.join(OUT_DIR, "ascii-portrait.txt")
    if PHOTO == "--card-only":
        art = open(portrait).read().rstrip("\n").split("\n")
    else:
        art = asciify(*cutout(PHOTO))
        open(portrait, "w").write("\n".join(art) + "\n")
    info = INFO_TOP + github_rows(github_stats()) + INFO_BOTTOM
    for name, theme in THEMES.items():
        fn = "huy-ascii-card.svg" if name == "dark" else f"huy-ascii-card-{name}.svg"
        open(os.path.join(OUT_DIR, fn), "w").write(svg(art, info, theme))
        print(f"wrote assets/{fn}")
