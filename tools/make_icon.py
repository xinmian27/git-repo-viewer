"""生成应用图标 assets/icon.ico（一次性工具，需要 pillow 库）。"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([12, 12, 244, 244], radius=52, fill=(37, 99, 235, 255))

white = (255, 255, 255, 255)
# 画一个"三个节点互相连接"的图形，象征仓库之间的版本关系
nodes = [(128, 66), (78, 186), (178, 186)]
d.line([nodes[0], nodes[1]], fill=white, width=13)
d.line([nodes[0], nodes[2]], fill=white, width=13)
d.line([nodes[1], nodes[2]], fill=white, width=13)
for (x, y) in nodes:
    d.ellipse([x - 19, y - 19, x + 19, y + 19], fill=white)

out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
os.makedirs(out_dir, exist_ok=True)
img.save(os.path.join(out_dir, "icon.ico"),
         sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
img.resize((64, 64), Image.LANCZOS).save(os.path.join(out_dir, "icon.png"))
print("图标已生成 ->", out_dir)
