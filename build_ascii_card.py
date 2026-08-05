"""
Build a neofetch-style ASCII portrait card (SVG) from a photo.

Usage:
    pip install opencv-python numpy
    python build_ascii_card.py /path/to/photo.jpg

Outputs:
    assets/huy-ascii-card.svg     - the card embedded in the README
    assets/ascii-portrait.txt     - plain-text ASCII portrait

Pipeline: GrabCut background removal -> CLAHE local contrast ->
downsample to a character grid -> map inverted luminance to a density ramp.
"""
import sys, html, os
import cv2, numpy as np

PHOTO = sys.argv[1] if len(sys.argv) > 1 else "photo.jpg"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
COLS, ROWS = 50, 32
RAMP = " .,:;i1tfLCG08@"

# ---------------------------------------------------------------- portrait ---
def cutout(path):
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

# -------------------------------------------------------------------- card ---
FS, LH, PAD, GAP, LAB_COL, VAL_MAX = 12.0, 14.0, 22, 28, 24, 44
CW = FS * 0.60
C_BG, C_BORDER, C_ART = "#0d1117", "#30363d", "#b9c2cc"
C_HEAD, C_LABEL, C_VAL, C_DOT = "#f0883e", "#ff7b72", "#c9d1d9", "#343b45"
FAMILY = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace'

ROWS_INFO = [
    ("sec", "ryan@huy"),
    ("row", "Host", "University of Technology Sydney"),
    ("row", "Kernel", "BSc Artificial Intelligence (Jul 2025 - now)"),
    ("row", "Prev", "BSc Computer Science, HCMUT - GPA 3.6/4.0"),
    ("row", "Role", "Research Assistant - VLM / GAN"),
    ("row", "Awards", "FEIT Dean's List 2026"),
    ("row", "Location", "Sydney, NSW, Australia"),
    ("row", "Status", "Open to internships and graduate roles"),
    ("blank",),
    ("sec", "Stack"),
    ("row", "Languages.Programming", "Python, C++, TypeScript, JavaScript"),
    ("row", "Languages.Markup", "HTML, CSS, SQL, Markdown"),
    ("row", "Languages.Real", "Vietnamese, English"),
    ("row", "ML.Frameworks", "PyTorch, Lightning, LangChain, YOLO"),
    ("row", "Web", "Next.js, React, FastAPI, Flask, Express"),
    ("row", "Data", "Pandas, NumPy, PostgreSQL, Redis, Docker"),
    ("row", "Research", "VLM, RAG, GAN, Robust CV, Dynamic GNN"),
    ("row", "IDE", "VS Code, Jupyter, Vim"),
    ("blank",),
    ("sec", "Contact"),
    ("row", "Email.Personal", "huy.quoc1205@gmail.com"),
    ("row", "Email.University", "quochuy.dinh@student.uts.edu.au"),
    ("row", "LinkedIn", "quochuy-dinh"),
    ("row", "GitHub", "Huydinh1205"),
    ("row", "HuggingFace", "Huydinh1205"),
    ("row", "Portfolio", "cv-website-lemon.vercel.app"),
]

def svg(art):
    esc = lambda s: html.escape(s, quote=False)
    art_w = max(len(l) for l in art) * CW
    info_w = (LAB_COL + VAL_MAX) * CW
    W = int(PAD * 2 + art_w + GAP + info_w)
    H = int(PAD * 2 + max(len(art), len(ROWS_INFO)) * LH + 4)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family=\'{FAMILY}\'>',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="10" fill="{C_BG}" stroke="{C_BORDER}"/>',
         f'<g font-size="{FS}" fill="{C_ART}">']
    for i, l in enumerate(art):                       # nbsp keeps indentation in every renderer
        o.append(f'<text x="{PAD}" y="{PAD+FS+i*LH:.1f}">{esc(l).replace(" ", chr(160))}</text>')
    o.append('</g>')
    x0 = PAD + art_w + GAP
    xv = x0 + LAB_COL * CW
    o.append(f'<g font-size="{FS}">')
    i = 0
    for r in ROWS_INFO:
        y = PAD + FS + i * LH
        if r[0] == "blank":
            i += 1; continue
        if r[0] == "sec":
            o.append(f'<text x="{x0:.1f}" y="{y:.1f}" fill="{C_HEAD}" font-weight="bold">{esc(r[1])}</text>')
            o.append(f'<line x1="{x0+(len(r[1])+1)*CW:.1f}" y1="{y-4:.1f}" x2="{x0+info_w:.1f}" '
                     f'y2="{y-4:.1f}" stroke="{C_BORDER}"/>')
        else:
            lab = r[1] + ":"
            o.append(f'<text x="{x0:.1f}" y="{y:.1f}" fill="{C_LABEL}">{esc(lab)}</text>')
            o.append(f'<text x="{xv:.1f}" y="{y:.1f}" fill="{C_VAL}">{esc(r[2])}</text>')
            a, b = x0 + (len(lab) + 1) * CW, xv - CW * 0.6
            if b - a > 6:
                o.append(f'<line x1="{a:.1f}" y1="{y-3.5:.1f}" x2="{b:.1f}" y2="{y-3.5:.1f}" '
                         f'stroke="{C_DOT}" stroke-width="1" stroke-dasharray="1 3"/>')
        i += 1
    o.append('</g></svg>')
    return "\n".join(o)

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    art = asciify(*cutout(PHOTO))
    open(os.path.join(OUT_DIR, "ascii-portrait.txt"), "w").write("\n".join(art) + "\n")
    open(os.path.join(OUT_DIR, "huy-ascii-card.svg"), "w").write(svg(art))
    print("\n".join(art))
    print("\nwrote assets/huy-ascii-card.svg")
