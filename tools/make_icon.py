"""Draws the app icon: a lens over lines of text on a green tile.

Writes assets/icon.ico (for the .exe) and lesson_lens/ui/icon.png (for the window).
Run from the repo root:  python tools/make_icon.py
"""
import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

GREEN = QColor("#1f7a4d")
LIGHT = QColor(255, 255, 255, 60)
WHITE = QColor("white")


def draw(size=256):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 256, size / 256)

    p.setPen(Qt.NoPen)
    p.setBrush(GREEN)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 56, 56)

    # Lines of "feedback text"
    p.setBrush(WHITE)
    for y, width in ((62, 150), (94, 110), (126, 70)):
        p.drawRoundedRect(QRectF(44, y, width, 16), 8, 8)

    # The lens
    p.setBrush(LIGHT)
    p.setPen(QPen(WHITE, 18))
    p.drawEllipse(QPointF(146, 146), 50, 50)
    p.setPen(QPen(WHITE, 26, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(184, 184), QPointF(214, 214))
    p.end()
    return img


def png_bytes(img):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.WriteOnly)
    img.save(buffer, "PNG")
    return bytes(data)


def write_ico(path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    """A multi-size .ico with PNG-compressed images (supported since Windows Vista)."""
    pngs = [(s, png_bytes(draw(s))) for s in sizes]
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, png in pngs:
        side = 0 if size >= 256 else size  # 0 means 256 in the ICO format
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    path.write_bytes(struct.pack("<HHH", 0, 1, len(pngs)) + entries + blobs)


if __name__ == "__main__":
    app = QGuiApplication([])
    root = Path(__file__).resolve().parent.parent
    (root / "assets").mkdir(exist_ok=True)
    write_ico(root / "assets" / "icon.ico")
    draw(256).save(str(root / "lesson_lens" / "ui" / "icon.png"))
    print("Wrote assets/icon.ico and lesson_lens/ui/icon.png")
