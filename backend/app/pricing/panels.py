"""How the detector's panels map onto cost-book panel types, and which panels touch."""

from app.schemas import Panel

PANEL_TYPES: dict[Panel, str] = {
    Panel.FRONT_BUMPER: "front_bumper",
    Panel.REAR_BUMPER: "rear_bumper",
    Panel.GRILLE: "grille",
    Panel.HOOD: "hood",
    Panel.ROOF: "roof",
    Panel.TRUNK: "trunk",
    Panel.LEFT_FRONT_FENDER: "front_fender",
    Panel.RIGHT_FRONT_FENDER: "front_fender",
    Panel.LEFT_FRONT_DOOR: "front_door",
    Panel.RIGHT_FRONT_DOOR: "front_door",
    Panel.LEFT_REAR_DOOR: "rear_door",
    Panel.RIGHT_REAR_DOOR: "rear_door",
    Panel.LEFT_QUARTER_PANEL: "quarter_panel",
    Panel.RIGHT_QUARTER_PANEL: "quarter_panel",
    Panel.LEFT_ROCKER: "rocker",
    Panel.RIGHT_ROCKER: "rocker",
    Panel.LEFT_MIRROR: "mirror",
    Panel.RIGHT_MIRROR: "mirror",
    Panel.LEFT_HEADLIGHT: "headlight",
    Panel.RIGHT_HEADLIGHT: "headlight",
    Panel.LEFT_TAILLIGHT: "taillight",
    Panel.RIGHT_TAILLIGHT: "taillight",
    Panel.WINDSHIELD: "windshield",
    Panel.REAR_WINDOW: "rear_window",
    Panel.LEFT_SIDE_GLASS: "side_glass",
    Panel.RIGHT_SIDE_GLASS: "side_glass",
    Panel.LEFT_FRONT_WHEEL: "wheel",
    Panel.RIGHT_FRONT_WHEEL: "wheel",
    Panel.LEFT_REAR_WHEEL: "wheel",
    Panel.RIGHT_REAR_WHEEL: "wheel",
}

# Painted panels that meet along a visible edge. When one is repainted, its neighbours
# are blended so the colour matches. Assumes a four-door body.
_TOUCHING = [
    (Panel.HOOD, Panel.LEFT_FRONT_FENDER),
    (Panel.HOOD, Panel.RIGHT_FRONT_FENDER),
    (Panel.LEFT_FRONT_FENDER, Panel.LEFT_FRONT_DOOR),
    (Panel.RIGHT_FRONT_FENDER, Panel.RIGHT_FRONT_DOOR),
    (Panel.LEFT_FRONT_DOOR, Panel.LEFT_REAR_DOOR),
    (Panel.RIGHT_FRONT_DOOR, Panel.RIGHT_REAR_DOOR),
    (Panel.LEFT_REAR_DOOR, Panel.LEFT_QUARTER_PANEL),
    (Panel.RIGHT_REAR_DOOR, Panel.RIGHT_QUARTER_PANEL),
    (Panel.TRUNK, Panel.LEFT_QUARTER_PANEL),
    (Panel.TRUNK, Panel.RIGHT_QUARTER_PANEL),
]


def _symmetric(pairs: list[tuple[Panel, Panel]]) -> dict[Panel, frozenset[Panel]]:
    neighbours: dict[Panel, set[Panel]] = {panel: set() for panel in Panel}
    for a, b in pairs:
        neighbours[a].add(b)
        neighbours[b].add(a)
    return {panel: frozenset(found) for panel, found in neighbours.items()}


ADJACENT = _symmetric(_TOUCHING)

# The window each body panel carries. Shattered glass reported on the panel means its window.
WINDOW_OF: dict[Panel, Panel] = {
    Panel.LEFT_FRONT_DOOR: Panel.LEFT_SIDE_GLASS,
    Panel.LEFT_REAR_DOOR: Panel.LEFT_SIDE_GLASS,
    Panel.LEFT_QUARTER_PANEL: Panel.LEFT_SIDE_GLASS,
    Panel.RIGHT_FRONT_DOOR: Panel.RIGHT_SIDE_GLASS,
    Panel.RIGHT_REAR_DOOR: Panel.RIGHT_SIDE_GLASS,
    Panel.RIGHT_QUARTER_PANEL: Panel.RIGHT_SIDE_GLASS,
    Panel.TRUNK: Panel.REAR_WINDOW,
}

PANEL_ORDER = {panel: index for index, panel in enumerate(Panel)}


def panel_label(panel: Panel) -> str:
    return panel.value.replace("_", " ")
