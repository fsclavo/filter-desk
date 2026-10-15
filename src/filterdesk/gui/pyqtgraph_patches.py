"""Workarounds for third-party GUI library bugs."""

# Patched snippets must match upstream source whitespace/line lengths.
# ruff: noqa: E501

from __future__ import annotations

import importlib
import inspect
import textwrap


def apply_pyqtgraph_svg_exporter_qt6_patch() -> None:
    """Fix PyQtGraph 0.14 SVG export crash on Qt6 path closepath tokens (``Z``).

    Qt6 emits ``d="M0,0 L1,0 … Z"``; PyQtGraph 0.14 assumes every token is ``x,y``.
    Upstream master already handles single-token commands; apply the same fix until
    a release includes it.
    """
    svg_mod = importlib.import_module("pyqtgraph.exporters.SVGExporter")

    if getattr(svg_mod, "_filterdesk_svg_qt6_patch", False):
        return

    src = textwrap.dedent(inspect.getsource(svg_mod.correctCoordinates))
    old = """                for c in oldCoords.split(' '):
                    x,y = c.split(',')
                    if x[0].isalpha():
                        t = x[0]
                        x = x[1:]
                    else:
                        t = ''
                    nc = fn.transformCoordinates(tr, np.array([[float(x),float(y)]]), transpose=True)
                    newCoords += t+str(nc[0,0])+','+str(nc[0,1])+' '
                # If coords start with L instead of M, then the entire path will not be rendered.
                # (This can happen if the first point had nan values in it--Qt will skip it on export)
                if newCoords[0] != 'M':
                    newCoords = f'M{newCoords[1:]}'
                ch.setAttribute('d', newCoords)
"""
    new = """                new_coords: list[str] = []
                for c in oldCoords.split(' '):
                    tokens = c.split(',')
                    if len(tokens) == 1:
                        # Closepath / bare command (e.g. Z) — Qt6 SVG generator.
                        new_coords.append(tokens[0])
                        continue
                    x, y = tokens
                    if x[0].isalpha():
                        t = x[0]
                        x = x[1:]
                    else:
                        t = ''
                    nc = fn.transformCoordinates(
                        tr, np.array([[float(x), float(y)]]), transpose=True
                    )
                    new_coords.append(t + str(nc[0, 0]) + ',' + str(nc[0, 1]))
                newCoords = ' '.join(new_coords)
                # Leading L (after skipped NaN points) would drop the path; force M.
                if newCoords and newCoords[0] != 'M':
                    newCoords = f'M{newCoords[1:]}'
                ch.setAttribute('d', newCoords)
"""
    if old not in src:
        # Already fixed or different pyqtgraph version — leave alone.
        svg_mod.__dict__["_filterdesk_svg_qt6_patch"] = True
        return
    exec(
        compile(src.replace(old, new), "<filterdesk_svg_patch>", "exec"),
        svg_mod.__dict__,
    )
    svg_mod.__dict__["_filterdesk_svg_qt6_patch"] = True
