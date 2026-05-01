"""
Image Watermark Tool
--------------------
Desktop GUI application built with Tkinter that lets the user overlay a
transparent watermark on a chosen image and save the result.

Main flow:
  1. The user loads an image via the "Browse..." button.
  2. Selects the watermark position from the dropdown menu.
  3. Clicks "Download Watermarked Image" to save the output.
"""

from tkinter import *
from tkinter import ttk, filedialog
import os
from pathlib import Path
from PIL import Image

# Base directory of this script — used to build absolute paths to resources
# (e.g. the watermark image file).
BASE_DIR = Path(__file__).parent

# Warm background color used for the UI frames
YELLOW = "#f7f5dd"

# Font used for all labels in the interface
FONT_NAME = "Comic Sans MS"

# Available options in the position dropdown
POSITIONS = ["Bottom Right", "Bottom Left", "Top Right", "Top Left", "Center"]

# Absolute path to the watermark image file, built from the base directory and relative path
WATERMARK_IMAGE_PATH = BASE_DIR / "assets" / "watermark.png"


def watermark_with_transparency(input_image_path, output_image_path, watermark_image_path, position):
    """
    Overlays a transparent watermark onto the base image and saves the result.

    Parameters:
        input_image_path     -- path to the image the watermark will be applied to
        output_image_path    -- path where the final image will be saved
        watermark_image_path -- path to the watermark image (PNG with alpha channel recommended)
        position             -- (x, y) tuple with pixel coordinates for placing the watermark
    """
    print(f"Applying watermark from '{watermark_image_path}' to '{input_image_path}' at position {position}...")
    # Open the base image and the watermark
    base_image = Image.open(input_image_path)
    watermark = Image.open(watermark_image_path)

    # Dimensions of the base image, used to create the transparent canvas
    width, height = base_image.size
    #print(f"Base image size: {width} x {height}")
    # get the position coordinates where to place the watermark based on the user's selection
    if position == "Bottom Right":
        position = (width - watermark.width - 10, height - watermark.height - 10)
    elif position == "Bottom Left":
        position = (10, height - watermark.height - 10)
    elif position == "Top Right":
        position = (width - watermark.width - 10, 10)
    elif position == "Top Left":
        position = (10, 10)
    elif position == "Center":
        position = ((width - watermark.width) // 2, (height - watermark.height) // 2)
    #print(f"Calculated watermark position: {position}")
    # Create a fully transparent RGBA layer the same size as the base image.
    # This canvas receives the original image first, then the watermark on top.
    transparent = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    #print(f"Created transparent canvas of size {transparent.size}.")
    transparent.paste(base_image, (0, 0))

    # Paste the watermark using its own alpha channel as a mask so that
    # transparent areas of the watermark do not cover the image beneath.
    transparent.paste(watermark, position, mask=watermark)

    # Preview the result in the system image viewer
    transparent.show()

    # Write the final image to disk
    transparent.save(output_image_path)


def upload_file():
    """
    Opens a file dialog to select an image from the filesystem.

    Updates 'input_path_var' with the chosen path, enables the download
    button, and updates the status bar.
    Supported formats: PNG, JPG, JPEG, BMP, GIF, TIFF.
    """
    path = filedialog.askopenfilename(
        title="Select Image",
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
    )
    if path:
        # Store the selected path in the shared GUI state variable
        input_path_var.set(path)

        # Enable the download button only after an image has been selected
        btn_download.config(state=NORMAL)

        # Show just the filename (not the full path) in the status bar
        set_status(f"Loaded: {os.path.basename(path)}")


def download_watermarked():
    """
    Opens a "Save As" dialog to choose where to save the watermarked image.

    Updates the status bar with the saved filename.
    Default format: PNG; JPEG is also supported.

    Note: currently this function only handles the save path selection;
    the actual call to watermark_with_transparency() still needs to be wired in.
    """
    save_path = filedialog.asksaveasfilename(
        title="Save Watermarked Image",
        defaultextension=".png",
        filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
    )
    if save_path:
        watermark_with_transparency(input_path_var.get(), save_path, WATERMARK_IMAGE_PATH, position_var.get())
        set_status("Saved: " + os.path.basename(save_path))


def clear_all():
    """
    Resets the UI to its initial state:
      - Clears the loaded image path
      - Restores the watermark position to the default ("Bottom Right")
      - Disables the download button
      - Sets the status bar back to "Ready"
    """
    input_path_var.set("")
    position_var.set("Bottom Right")
    btn_download.config(state=DISABLED)
    set_status("Ready")


def set_status(msg):
    """
    Updates the text shown in the status bar at the bottom of the window.

    Parameters:
        msg -- string to display in the status label
    """
    lbl_status.config(text=msg)


# ─── Main Window ─────────────────────────────────────────────────────────────
# Create the Tkinter root window and configure its appearance and minimum size
window = Tk()
window.title("Image Watermark Tool")
window.config(bg="#d9d9d9", padx=15, pady=15)
window.minsize(width=600, height=350)

# Column 0 expands horizontally to fill the window width
window.columnconfigure(0, weight=1)

# ─── Frame: image upload ──────────────────────────────────────────────────────
# LabelFrame with a grooved border grouping the image-loading controls
frame_upload = LabelFrame(window, bg=YELLOW, padx=15, pady=12, bd=1, relief=GROOVE)
frame_upload.grid(row=0, column=0, sticky="ew", pady=(0, 12))
frame_upload.columnconfigure(0, weight=1)

Label(frame_upload, text="Upload Image:", font=(FONT_NAME, 11, "bold"), bg=YELLOW).grid(
    row=0, column=0, sticky="w"
)

# Tkinter variable that holds the path of the currently selected image file
input_path_var = StringVar()

# Button that opens the file-selection dialog
btn_browse = Button(frame_upload, text="Browse...", command=upload_file, width=12)
btn_browse.grid(row=1, column=0, sticky="w", pady=(8, 0))

# ─── Frame: watermark position ────────────────────────────────────────────────
# LabelFrame containing the dropdown for choosing where to place the watermark
frame_position = LabelFrame(window, bg=YELLOW, padx=15, pady=12, bd=1, relief=GROOVE)
frame_position.grid(row=1, column=0, sticky="ew", pady=(0, 12))
frame_position.columnconfigure(0, weight=1)

Label(frame_position, text="Position:", font=(FONT_NAME, 11, "bold"), bg=YELLOW).grid(
    row=0, column=0, sticky="w"
)

# Tkinter variable bound to the Combobox; tracks the currently selected position
position_var = StringVar(value="Bottom Right")

# Read-only Combobox: the user can only pick from the values defined in POSITIONS
combo_position = ttk.Combobox(
    frame_position, textvariable=position_var, values=POSITIONS, state="readonly"
)
combo_position.grid(row=1, column=0, sticky="ew", pady=(8, 0))

# ─── Frame: action buttons ────────────────────────────────────────────────────
# Borderless frame that lays the two main buttons side by side
frame_buttons = Frame(window, bg="#d9d9d9")
frame_buttons.grid(row=2, column=0, sticky="ew", pady=(0, 12))
frame_buttons.columnconfigure(0, weight=1)

# Download button: disabled until an image is loaded (enabled inside upload_file)
btn_download = Button(
    frame_buttons, text="Download Watermarked Image", command=download_watermarked, state=DISABLED
)
btn_download.grid(row=0, column=0, sticky="ew", padx=(0, 8))

# Button to reset all fields and start over
btn_clear = Button(frame_buttons, text="Clear", command=clear_all, width=10)
btn_clear.grid(row=0, column=1, sticky="ew")

# ─── Status Bar ───────────────────────────────────────────────────────────────
# Sunken label used as a status bar to give feedback to the user
lbl_status = Label(window, text="Ready", relief=SUNKEN, anchor="w", bg="white", width=20)
lbl_status.grid(row=3, column=0, sticky="w")

# Start the Tkinter event loop — keeps the window open and responsive to input
window.mainloop()
