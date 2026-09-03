"""Simulate browser layout: at common viewports, does posting-split give
side-by-side columns or stacked?
"""
# Bootstrap 3.3.6 breakpoints
BREAKPOINTS = [
    ("iPhone SE",  375),
    ("iPhone 12",  390),
    ("iPad portrait", 768),
    ("iPad landscape", 1024),
    ("Laptop 1280", 1280),
    ("Laptop 1366", 1366),
    ("Laptop 1440", 1440),
    ("FullHD",     1920),
]

# .container is Bootstrap 3 width per breakpoint
CONTAINER_W = {
    375:  None,  # no .container, just padding
    390:  None,
    768:  750,
    1024: 970,
    1280: 1170,
    1366: 1170,
    1440: 1170,
    1920: 1170,
}

# .posting-split rules per breakpoint
def layout_for(vw):
    if vw < 992:
        return "STACKED", 100, 100  # form%, preview%
    elif vw < 1200:
        return "SPLIT", 60, 40
    elif vw < 1600:
        return "SPLIT", 65, 35
    else:
        return "SPLIT", 60, 40

print(f"{'Device':<18} {'Viewport':>9} {'Container':>10} {'Layout':<8} {'Form':>8} {'Preview':>9}")
print("-" * 60)
for name, vw in BREAKPOINTS:
    layout, fp, pp = layout_for(vw)
    cw = CONTAINER_W[vw]
    if cw:
        form_w = int(cw * fp / 100) - 15   # minus half gutter
        prev_w = int(cw * pp / 100) - 15
        print(f"{name:<18} {vw:>9} {cw:>10} {layout:<8} {form_w:>7}px {prev_w:>8}px")
    else:
        print(f"{name:<18} {vw:>9} {'n/a':>10} {layout:<8} {'100%':>8} {'100%':>9}")
