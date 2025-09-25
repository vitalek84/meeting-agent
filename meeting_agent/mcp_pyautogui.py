"""
Very experimental and raw version
"""

from typing import List, Tuple

import pyautogui
from mcp.server.fastmcp import FastMCP

# --- Server Setup ---

# Create an MCP server instance
mcp = FastMCP("Mouse Control Server")

# Get the screen resolution
try:
    SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
except Exception as e:
    print(f"Error getting screen resolution: {e}")
    # Set a default resolution if pyautogui fails
    SCREEN_WIDTH, SCREEN_HEIGHT = 1920, 1080


# Add the screen resolution as a read-only resource to the server
@mcp.resource("resource://screen_resolution")
def get_screen_resolution() -> dict:
    """Provides the screen resolution of the primary monitor."""
    return {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}


# --- Helper Functions ---


def _find_bounding_box_center(bounding_box: List[int]) -> Tuple[int, int]:
    """
    Calculates the relative center coordinates from a bounding box.
    Note: The input format is [y_min, x_min, y_max, x_max].
    The output format is (x_center, y_center).
    """
    y_min, x_min, y_max, x_max = bounding_box
    x_center_relative = (x_min + x_max) // 2
    y_center_relative = (y_min + y_max) // 2
    return x_center_relative, y_center_relative


def _convert_relative_to_absolute(x_relative: int, y_relative: int) -> Tuple[int, int]:
    """
    Converts relative coordinates (0-1000) to absolute screen coordinates.
    """
    x_absolute = int((x_relative / 1000) * SCREEN_WIDTH)
    y_absolute = int((y_relative / 1000) * SCREEN_HEIGHT)
    return x_absolute, y_absolute


# --- Mouse Control Tools ---


@mcp.tool()
def move_mouse(bounding_box: List[int]) -> str:
    """
    Moves the mouse to the center of a specified bounding box. The model should provide a list of 4 integers representing the bounding box of the GUI element
    in the format [y_min, x_min, y_max, x_max], using relative coordinates (0-1000).

    Args:
        bounding_box: A list of 4 integers [y_min, x_min, y_max, x_max].

    Returns:
        A confirmation message detailing the operation.
    """
    try:
        if not isinstance(bounding_box, list) or len(bounding_box) != 4:
            return "Error: bounding_box must be a list of 4 integers [y_min, x_min, y_max, x_max]."

        x_rel, y_rel = _find_bounding_box_center(bounding_box)
        x_abs, y_abs = _convert_relative_to_absolute(x_rel, y_rel)

        pyautogui.moveTo(x_abs, y_abs)

        return (
            f"Mouse moved to center of bounding box {bounding_box}. "
            f"Relative center: ({x_rel}, {y_rel}). "
            f"Absolute coordinates: ({x_abs}, {y_abs})."
        )
    except Exception as e:
        return f"Error moving mouse: {e}"


@mcp.tool()
def click_mouse(bounding_box: List[int], button: str = "left") -> str:
    """
    Clicks the center of a specified bounding box. The model should provide a list of 4 integers representing the bounding box of the GUI element in the format [y_min, x_min, y_max, x_max], using relative coordinates (0-1000).

    Args:
        bounding_box: A list of 4 integers [y_min, x_min, y_max, x_max].
        button: The mouse button to click ('left', 'middle', 'right').

    Returns:
        A confirmation message detailing the operation.
    """
    try:
        if not isinstance(bounding_box, list) or len(bounding_box) != 4:
            return "Error: bounding_box must be a list of 4 integers [y_min, x_min, y_max, x_max]."
        if button not in ["left", "middle", "right"]:
            return "Error: Invalid button specified. Use 'left', 'middle', or 'right'."

        x_rel, y_rel = _find_bounding_box_center(bounding_box)
        x_abs, y_abs = _convert_relative_to_absolute(x_rel, y_rel)

        pyautogui.click(x_abs, y_abs, button=button)

        return (
            f"{button.capitalize()} click at center of bounding box {bounding_box}. "
            f"Relative center: ({x_rel}, {y_rel}). "
            f"Absolute coordinates: ({x_abs}, {y_abs})."
        )
    except Exception as e:
        return f"Error clicking mouse: {e}"


@mcp.tool()
def click_admit():
    """Click Admit button on Google Meet Call Page"""
    try:
        print("Function click_admit called!")
        pyautogui.click("./gm_control_elems/admit.png")
        return "Admitted OK"
    except Exception as ex:
        print(f"Exception in ScreenActions: {ex}")
        return "Admitted NOT OK"


if __name__ == "__main__":
    # To run this server, save it as a Python file (e.g., server.py) and run:
    # python server.py
    #
    # Or, using the mcp CLI for more options:
    # mcp serve-stdio --module_name server:mcp
    print("Starting Mouse Control Server...")
    mcp.run(transport="stdio")
