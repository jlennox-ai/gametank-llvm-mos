### Graphics

`tools/tile_palettes` turns a PNG of tiles into GameTank color data, once per palette, so one
drawing becomes as many color versions as you have palettes. Add the configs to your game:

```cmake
gametank_add_tiles(mygame assets/tiles.toml)
```

A config is named by its file: `tiles.toml` makes `tiles.h` (which you `#include`) and `tiles.c`
in `build/assets/`, and `tiles_preview.png` there to check the colors. Its image is a file in the
same folder. For example, `assets/tiles.toml`:

```toml
image = "tiles.png"
tile_width = 12
tile_height = 12
tiles = ["solid", "single"]    # left to right in the image

# Every color in the image, as a shade: saturation 0-3 and luminance 0-7 (the palette gives the
# hue). Fully transparent pixels need no entry.
[colors]
"#ffffff" = "transparent"
"#1c9440" = { saturation = 3, luminance = 4 }
"#22b14c" = { saturation = 3, luminance = 5 }

# A row of tiles per palette: a hue 0-7, and optionally a luminance added to every shade.
[[palettes]]
name = "green"
hue = 7

[[palettes]]
name = "red"
hue = 2
luminance = -2
```

Then, in C:

```c
#include "tiles.h"

gt_sprite_sheet_load(tiles_sheet, TILES_SHEET_WIDTH, TILES_SHEET_HEIGHT, 0, 0);  // once, at startup
gt_sprite_draw(x, y, TILES_X(TILES_SOLID), TILES_Y(TILES_PALETTE_RED), TILES_TILE_WIDTH, TILES_TILE_HEIGHT);
```

A color the config doesn't list, or a shade pushed out of range by a palette, is an error that
names the pixel. A tile can't be called `h`, `x`, `y`, `sheet_width`, `sheet_height`,
`tile_width` or `tile_height`, or start with `palette_`: those names are taken in the header.