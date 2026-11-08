"""Build Nimbus's original, lightly segmented mission digits (requires fonttools)."""
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

# Beveled segments with small gaps, drawn on a 108 x 180 design grid.
SEGMENTS = {
    "a": [(14,2),(86,2),(94,10),(86,18),(14,18),(6,10)],
    "b": [(96,14),(104,22),(104,78),(96,86),(88,78),(88,22)],
    "c": [(96,94),(104,102),(104,158),(96,166),(88,158),(88,102)],
    "d": [(14,162),(86,162),(94,170),(86,178),(14,178),(6,170)],
    "e": [(4,94),(12,102),(12,158),(4,166),(-4,158),(-4,102)],
    "f": [(4,14),(12,22),(12,78),(4,86),(-4,78),(-4,22)],
    "g": [(14,82),(86,82),(94,90),(86,98),(14,98),(6,90)],
}
DIGITS = ["abcdef", "bc", "abdeg", "abcdg", "bcfg", "acdfg", "acdefg", "abc", "abcdefg", "abcdfg"]


def build():
    names = [".notdef"] + [f"digit{i}" for i in range(10)]
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        if name != ".notdef":
            for segment in DIGITS[int(name[-1])]:
                points = [((x + 14) * 5, (180 - y) * 5 + 50) for x, y in SEGMENTS[segment]]
                pen.moveTo(points[0])
                for point in points[1:]:
                    pen.lineTo(point)
                pen.closePath()
        glyphs[name] = pen.glyph()
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({ord(str(i)): f"digit{i}" for i in range(10)})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (660, 50) for name in names})
    builder.setupHorizontalHeader(ascent=1000, descent=0)
    builder.setupNameTable({"familyName": "Nimbus Segments", "styleName": "Regular",
                           "uniqueFontIdentifier": "NimbusSegments-Regular-1",
                           "fullName": "Nimbus Segments Regular", "psName": "NimbusSegments-Regular"})
    builder.setupOS2(sTypoAscender=1000, sTypoDescender=0, usWinAscent=1000,
                    usWinDescent=0, sxHeight=900, sCapHeight=900)
    builder.setupPost()
    builder.setupMaxp()
    builder.font.flavor = "woff"
    destination = Path(__file__).resolve().parents[1] / "web/fonts/nimbus-segments.woff"
    destination.parent.mkdir(exist_ok=True)
    builder.save(destination)
    print(destination)


if __name__ == "__main__":
    build()
