#!/usr/bin/env python3
"""icon_1024.png -> packaging/icon.ico (Windows). Needs Pillow."""
import os
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = Image.open(os.path.join(ROOT, "icon_1024.png"))
out = os.path.join(ROOT, "packaging", "icon.ico")
src.save(out, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
print("wrote", out)
