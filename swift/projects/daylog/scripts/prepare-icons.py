#!/usr/bin/env python3
"""Package the approved icon into macOS asset sizes and the SwiftPM icns."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "design/brand/kebai-daylight-production.png"
RESOURCES = ROOT / "DayLog/Resources"
CATALOG = RESOURCES / "Assets.xcassets"
ICONS = CATALOG / "AppIcon.appiconset"


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    (CATALOG / "Contents.json").write_text(json.dumps({"info": {"version": 1, "author": "xcode"}}, indent=2) + "\n")
    images = []
    with tempfile.TemporaryDirectory(prefix="kebai-icon-") as temp:
        iconset = Path(temp) / "Kebai.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                pixels = points * scale
                filename = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"
                output = ICONS / filename
                subprocess.run(["sips", "-z", str(pixels), str(pixels), str(SOURCE), "--out", str(output)], check=True, stdout=subprocess.DEVNULL)
                (iconset / filename).write_bytes(output.read_bytes())
                images.append({"idiom": "mac", "size": f"{points}x{points}", "scale": f"{scale}x", "filename": filename})
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(RESOURCES / "Kebai.icns")], check=True)
    (ICONS / "Contents.json").write_text(json.dumps({"images": images, "info": {"version": 1, "author": "xcode"}}, indent=2) + "\n")
    print("Prepared AppIcon.appiconset and Kebai.icns")


if __name__ == "__main__":
    main()
