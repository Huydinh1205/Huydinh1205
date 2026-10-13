"""
Build a self-hosted animated "typing terminal" SVG for the README header.

Usage:
    python scripts/build_typing_svg.py      # writes assets/typing.svg

Each frame is its own <text> element toggled with SMIL, so the cursor sits
exactly after the last character in any monospace font (no width guessing).
Self-hosted on purpose: no third-party image service that can go down.
"""
import html, os

PHRASES = [
    "Data Engineer @ Nallawilli Bunjil",
    "Computer Vision Research Intern @ CSIRO (incoming)",
    "Final-year AI student @ UTS, Dean's List 2026",
    "Building CV + VLM pipelines for sports and traffic",
]
USER, PATH = "ryan@huy", ":~$ "
TYPE, DELETE, DEL_STEP, BLINK, HOLD_BLINKS, GAP = 0.055, 0.025, 3, 0.45, 4, 0.35
FS, W, H = 17, 760, 34
C_USER, C_PATH, C_TEXT, C_CURSOR = "#f0883e", "#8b949e", "#58a6ff", "#8b949e"
FAMILY = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "DejaVu Sans Mono", monospace'

def frames():
    out = []                                     # (text, cursor_visible, duration)
    for p in PHRASES:
        for k in range(1, len(p) + 1):
            out.append((p[:k], True, TYPE))
        for b in range(HOLD_BLINKS * 2):
            out.append((p, b % 2 == 0, BLINK))
        for k in range(len(p) - DEL_STEP, 0, -DEL_STEP):
            out.append((p[:k], True, DELETE))
        out.append(("", True, GAP))
    return out

def build():
    fr = frames()
    total = sum(d for *_, d in fr)
    esc = lambda s: html.escape(s, quote=False)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family=\'{FAMILY}\' font-size="{FS}">']
    t = 0.0
    for text, cur, d in fr:
        s, e = t / total, (t + d) / total
        if s == 0:
            anim = f'values="1;0" keyTimes="0;{e:.5f}"'
        else:
            anim = f'values="0;1;0" keyTimes="0;{s:.5f};{e:.5f}"'
        cursor = f'<tspan fill="{C_CURSOR}">▌</tspan>' if cur else ""
        o.append(f'<text x="4" y="{H/2+FS*0.35:.1f}" opacity="0">'
                 f'<tspan fill="{C_USER}" font-weight="bold">{USER}</tspan>'
                 f'<tspan fill="{C_PATH}">{esc(PATH).replace(" ", chr(160))}</tspan>'
                 f'<tspan fill="{C_TEXT}">{esc(text).replace(" ", chr(160))}</tspan>{cursor}'
                 f'<animate attributeName="opacity" {anim} dur="{total:.2f}s" '
                 f'calcMode="discrete" repeatCount="indefinite"/></text>')
        t += d
    o.append('</svg>')
    return "\n".join(o)

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "typing.svg")
    open(out, "w").write(build())
    print("wrote assets/typing.svg")
