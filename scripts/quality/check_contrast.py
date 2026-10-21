#!/usr/bin/env python3
"""WCAG 2.2 contrast check of the design-token pairs in frontend/src/styles/tokens.css.

Checks every theme block (dark default, light, and the dark sidebar inside the light theme) for the
text/background pairs the components actually combine. Semi-transparent backgrounds are composited
over the surface they sit on. Exit status 1 if a pair is below its threshold:
4.5:1 for text, 3:1 for focus indicators and form-control borders (WCAG 1.4.3, 1.4.11, 2.4.13).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[2] / "frontend/src/styles/tokens.css"
TEXT, UI = 4.5, 3.0


def parse_color(value: str) -> tuple[float, float, float, float]:
    value = value.strip()
    if value.startswith("#"):
        h = value[1:]
        h = "".join(c * 2 for c in h) if len(h) == 3 else h
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)  # type: ignore[return-value]
    m = re.match(r"rgba?\(([^)]*)\)", value)
    if not m:
        raise ValueError(value)
    parts = [float(p) for p in m.group(1).split(",")]
    return (parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else 1.0)


def over(fg: tuple[float, float, float, float], bg: tuple[float, float, float, float]):
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3)) + (1.0,)


def luminance(c: tuple[float, ...]) -> float:
    def lin(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def ratio(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def blocks(css: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", css, flags=re.S)):
        sel = " ".join(selector.split())
        decls = dict(re.findall(r"(--color-[\w-]+)\s*:\s*([^;]+);", body))
        if decls:
            out.setdefault(sel, {}).update(decls)
    return out


def main() -> int:
    b = blocks(TOKENS.read_text())
    dark = {**b.get(":root, [data-theme='dark']", {})}
    light = {**dark, **b.get("[data-theme='light']", {})}
    sidebar = {**light, **b.get("[data-theme='light'] .sidebar, [data-theme='light'] .shell__bar", {})}
    themes = {"dark": dark, "light": light, "light sidebar/bar": sidebar}
    failures = 0
    for name, t in themes.items():
        c = {k: parse_color(v) for k, v in t.items()}
        surfaces = ["--color-bg", "--color-surface", "--color-surface-raised", "--color-field"]
        if name == "dark":
            surfaces += ["--color-auth-panel"]
        if name == "light sidebar/bar":
            surfaces = ["--color-sidebar", "--color-surface-raised"]
        checks: list[tuple[str, float, float]] = []
        for s in surfaces:
            bg = over(c[s], c["--color-bg"])
            for fg in ("--color-text", "--color-text-secondary", "--color-text-muted"):
                if name == "light sidebar/bar" and s != "--color-sidebar" and fg == "--color-text-muted":
                    pass
                checks.append((f"{fg} on {s}", ratio(over(c[fg], bg), bg), TEXT))
            checks.append((f"--color-focus on {s}", ratio(c["--color-focus"], bg), UI))
            checks.append((f"--color-control-border on {s}", ratio(over(c["--color-control-border"], bg), bg), UI))
        if name != "light sidebar/bar":
            for kind in ("success", "warning", "danger", "info"):
                for s in ("--color-surface", "--color-bg", "--color-surface-raised"):
                    base = over(c[s], c["--color-bg"])
                    bg = over(c[f"--color-{kind}-bg"], base)
                    checks.append((f"{kind}-text on {kind}-bg over {s}", ratio(c[f"--color-{kind}-text"], bg), TEXT))
                    checks.append((f"{kind}-text on {s}", ratio(c[f"--color-{kind}-text"], base), TEXT))
            for s_ in ("--color-surface", "--color-bg", "--color-surface-raised"):
                base = over(c[s_], c["--color-bg"])
                checks.append((f"accent-text on {s_}", ratio(c["--color-accent-text"], base), TEXT))
                # Metric/alert icons sit on a 24% tint of their own colour (bright brand values).
                for kind, tint in (("info", "--color-info"), ("danger", "--color-danger"), ("warning", "--color-warning")):
                    t_ = c.get(tint) or parse_color("#000")
                    chip = over(t_[:3] + (0.24,), base)
                    checks.append((f"{kind}-text icon on tint over {s_}", ratio(c[f"--color-{kind}-text"], chip), UI))
            nav = c["--color-nav-active"]
            checks.append(("white on --color-nav-active", ratio((255, 255, 255, 1), nav), TEXT))
        else:
            checks.append(("white on --color-nav-active", ratio((255, 255, 255, 1), c["--color-nav-active"]), TEXT))
        if "--color-danger-solid" in c:
            checks.append(("white on --color-danger-solid", ratio((255, 255, 255, 1), c["--color-danger-solid"]), TEXT))
        for label, got, need in checks:
            ok = got >= need
            failures += not ok
            if not ok:
                print(f"FAIL [{name}] {label}: {got:.2f}:1 (needs {need}:1)")
        print(f"{name}: {len(checks)} pairs checked")
    print("contrast: FAIL" if failures else "contrast: ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
