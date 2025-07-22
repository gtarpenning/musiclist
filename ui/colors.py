from typing import Literal, Dict, Optional

# Color palette for the music calendar application
# Change colors here to update the entire app's theme

# Type definition for available color keys
ColorKey = Literal[
    "header",
    "title",
    "date",
    "time",
    "artists",
    "venue",
    "cost",
    "success",
    "error",
    "info",
    "warning",
    "weekend",
    "pinned",
    "pin_marker",
    "dim",
    "bold",
]

# Primary colors
PRIMARY_BLUE = "blue"
PRIMARY_CYAN = "cyan"
PRIMARY_GREEN = "green"
PRIMARY_MAGENTA = "magenta"
PRIMARY_YELLOW = "yellow"
PRIMARY_RED = "red"

# Accent colors
ACCENT_WHEAT = "wheat1"
ACCENT_BRIGHT_WHITE = "bright_white"
ACCENT_BRIGHT_YELLOW = "bright_yellow"
ACCENT_LIGHT_GREEN = "light_green"

# Semantic color mapping
COLORS: Dict[ColorKey, str] = {
    # Table headers and titles
    "header": PRIMARY_BLUE,
    "title": PRIMARY_BLUE,
    # Event data
    "date": PRIMARY_CYAN,
    "time": PRIMARY_GREEN,
    "artists": ACCENT_BRIGHT_WHITE,
    "venue": PRIMARY_MAGENTA,
    "cost": PRIMARY_YELLOW,
    # Status indicators
    "success": PRIMARY_GREEN,
    "error": PRIMARY_RED,
    "info": PRIMARY_BLUE,
    "warning": PRIMARY_YELLOW,
    # Special highlighting
    "weekend": PRIMARY_YELLOW,
    "pinned": ACCENT_LIGHT_GREEN,
    "pin_marker": ACCENT_BRIGHT_YELLOW,
    # Misc
    "dim": "dim",
    "bold": "bold",
}


def get_color(color_key: ColorKey) -> str:
    """Get a color value by key"""
    return COLORS.get(color_key, "")


def style(text: str, color_key: ColorKey, **kwargs) -> str:
    """Apply color styling to text"""
    color = get_color(color_key)
    if not color:
        return text

    # Handle additional styling
    styles = [color]
    if kwargs.get("bold"):
        styles.append("bold")

    style_str = " ".join(styles)
    return f"[{style_str}]{text}[/{style_str}]"


def link_style(
    text: str, url: str, color_key: Optional[ColorKey] = None, **kwargs
) -> str:
    """Apply color styling with link to text"""
    if color_key:
        color = get_color(color_key)
        if kwargs.get("bold"):
            style_str = f"{color} bold"
        else:
            style_str = color
        return f"[{style_str} link={url}]{text}[/{style_str} link]"
    else:
        return f"[link={url}]{text}[/link]"


# Color constants for direct usage (still centralized)
WEEKEND_COLOR = PRIMARY_YELLOW
PINNED_COLOR = ACCENT_LIGHT_GREEN
PIN_MARKER_COLOR = ACCENT_BRIGHT_YELLOW
DATE_COLOR = PRIMARY_CYAN
TIME_COLOR = PRIMARY_GREEN
ARTISTS_COLOR = ACCENT_BRIGHT_WHITE
VENUE_COLOR = PRIMARY_MAGENTA
COST_COLOR = PRIMARY_YELLOW
SUCCESS_COLOR = PRIMARY_GREEN
ERROR_COLOR = PRIMARY_RED
INFO_COLOR = PRIMARY_BLUE
WARNING_COLOR = PRIMARY_YELLOW
HEADER_COLOR = PRIMARY_BLUE
