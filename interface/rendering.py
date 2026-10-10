"""Accessible, compact HTML rendering for the simulated warehouse grid."""

from html import escape

from search_algorithm.grid import Grid
from search_algorithm.models import Position


def grid_html(grid: Grid, path: list[Position], start: Position, goal: Position) -> str:
    """Render a validated numeric map with row/column axes and a route overlay."""
    order = {cell: index for index, cell in enumerate(path)}
    cells = ['<div class="route-axis route-corner" aria-hidden="true"></div>']
    cells.extend(
        f'<div class="route-axis" aria-hidden="true">{column}</div>'
        for column in range(grid.width)
    )

    for row in range(grid.height):
        cells.append(f'<div class="route-axis" aria-hidden="true">{row}</div>')
        for column in range(grid.width):
            cell = (row, column)
            kind, label = "open", ""
            if cell in grid.blocked:
                kind, label = "blocked", ""
            elif cell in order:
                kind, label = "path", str(order[cell])
            if cell == goal:
                kind, label = "goal", "G"
            if cell == start:
                kind, label = "robot", "R/G" if start == goal else "R"
            title = escape(f"Row {row}, column {column}: {kind}")
            cells.append(
                f'<div class="route-cell route-{kind}" title="{title}" '
                f'aria-label="{title}">{label}</div>'
            )

    return f"""
    <style>
      .route-map {{ overflow-x: auto; padding: 8px 0 12px; }}
      .route-grid {{
        display: grid;
        grid-template-columns: 28px repeat({grid.width}, minmax(30px, 1fr));
        grid-auto-rows: 34px;
        gap: 3px;
        min-width: {28 + grid.width * 33}px;
        max-width: 100%;
      }}
      .route-cell {{
        display: flex; align-items: center; justify-content: center;
        border: 1px solid #c8d0d6; border-radius: 2px;
        font: 600 11px ui-monospace, SFMono-Regular, Consolas, monospace;
      }}
      .route-axis {{
        display: flex; align-items: center; justify-content: center;
        color: #596773; font: 11px ui-monospace, SFMono-Regular, Consolas, monospace;
      }}
      .route-open {{ background: #ffffff; }}
      .route-blocked {{ background: #aeb8c0; border-color: #8e9ba5; }}
      .route-path {{ background: #527b99; border-color: #3d6888; color: #ffffff; }}
      .route-robot {{ background: #1e3444; border-color: #1e3444; color: #ffffff; }}
      .route-goal {{ background: #f0c36a; border-color: #d7a642; color: #34260c; }}
      .route-legend {{ display: flex; flex-wrap: wrap; gap: 8px 18px; color: #46545f;
        font: 12px system-ui, sans-serif; }}
      .route-legend-item {{ display: inline-flex; align-items: center; gap: 7px; }}
      .route-swatch {{ width: 12px; height: 12px; border: 1px solid #aeb8c0;
        border-radius: 2px; }}
      .route-swatch-open {{ background: #ffffff; }}
      .route-swatch-blocked {{ background: #aeb8c0; }}
      .route-swatch-path {{ background: #527b99; border-color: #3d6888; }}
      .route-swatch-robot {{ background: #1e3444; border-color: #1e3444; }}
      .route-swatch-goal {{ background: #f0c36a; border-color: #d7a642; }}
    </style>
    <div class="route-map" role="img" aria-label="Warehouse map with robot, fixed goal, shelves, and selected route">
      <div class="route-grid">{''.join(cells)}</div>
    </div>
    <div class="route-legend" aria-label="Map legend">
      <span class="route-legend-item"><i class="route-swatch route-swatch-robot"></i>Robot (R)</span>
      <span class="route-legend-item"><i class="route-swatch route-swatch-goal"></i>Goal (G)</span>
      <span class="route-legend-item"><i class="route-swatch route-swatch-path"></i>Route / step</span>
      <span class="route-legend-item"><i class="route-swatch route-swatch-blocked"></i>Shelf</span>
      <span class="route-legend-item"><i class="route-swatch route-swatch-open"></i>Open cell</span>
    </div>
    """
