
import os
import re
import barcode
from barcode.writer import ImageWriter


BARCODE_DIR = "barcodes"


def create_barcode_image(barcode_value):
    """Generate a PNG barcode image for a file ID."""
    os.makedirs(BARCODE_DIR, exist_ok=True)

    value = str(barcode_value).strip().upper()

    if not value:
        raise ValueError("Barcode value cannot be empty.")

    # Keep the filename safe for the filesystem.
    safe_name = re.sub(r"[^A-Z0-9_-]", "-", value)
    filename = os.path.join(BARCODE_DIR, safe_name)

    code = barcode.get(
        "code128",
        value,
        writer=ImageWriter()
    )

    saved_path = code.save(
        filename,
        options={
            "write_text": True,
            "module_width": 0.3,
            "module_height": 15,
            "quiet_zone": 3,
        }
    )

    return saved_path
