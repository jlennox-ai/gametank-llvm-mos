// Turns sheets of tiles into GameTank colour data, once per palette, as C source.
//
//   tile_palettes <output folder> <config.toml>...
//
// Each config (README.md, "Graphics", has an example) names the source image, the tiles in it
// (left to right, one row), the shade of each colour the image uses, and the palettes. Each
// palette gives every shade a hue (and can make the whole palette lighter or darker), so one
// drawing becomes as many colour versions as there are palettes.
//
// The config's file name is its name: tiles.toml makes tiles.h and tiles.c. The image is a file
// in the config's folder, so a build knows what to rebuild from: the config and the images
// beside it.
//
// It writes, into the output folder (only files whose contents changed, so a build doesn't see
// new timestamps):
//   <name>.h, <name>.c     the sheet as a C array of colour bytes: one row of tiles per
//                          palette, laid out as it would be in graphics RAM (0 is transparent)
//   <name>_preview.png     the sheet as the GameTank shows it, enlarged, to check the colours
use serde::Deserialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;

mod gametank_palette;

const HUE_COUNT: u8 = 8;
const SATURATION_COUNT: u8 = 4;
const LUMINANCE_COUNT: u8 = 8;
const TRANSPARENT_BYTE: u8 = 0;
const TRANSPARENT_KEYWORD: &str = "transparent";
// The header's own names, after its <NAME>_ prefix (the include guard, the sizes and the X/Y
// macros): a tile can't have one of these names, or start with "palette_".
const RESERVED_TILE_NAMES: [&str; 7] = ["h", "x", "y", "sheet_width", "sheet_height", "tile_width", "tile_height"];
const PREVIEW_SCALE: u32 = 8;
// The preview's transparent pixels: a magenta no GameTank colour shows as, to tell them apart.
const PREVIEW_TRANSPARENT: [u8; 3] = [255, 0, 255];

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    // The config's file name, without .toml.
    #[serde(skip)]
    name: String,
    image: String,
    tile_width: u32,
    tile_height: u32,
    tiles: Vec<String>,
    // The image's colours ("#rrggbb"), each a shade or "transparent".
    colors: BTreeMap<String, ColorConfig>,
    palettes: Vec<PaletteConfig>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum ColorConfig {
    Keyword(String),
    Shade(Shade),
}

#[derive(Deserialize, Clone, Copy)]
#[serde(deny_unknown_fields)]
struct Shade {
    saturation: u8,
    luminance: u8,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct PaletteConfig {
    name: String,
    hue: u8,
    // Added to every shade's luminance.
    #[serde(default)]
    luminance: i8,
}

// A source pixel: None is transparent.
type Pixel = Option<Shade>;

// The source image.
struct ShadeSheet {
    width: u32,
    height: u32,
    pixels: Vec<Pixel>,
}

// The output: colour bytes, TRANSPARENT_BYTE where transparent (no shade comes out as it).
struct ColorSheet {
    width: u32,
    height: u32,
    bytes: Vec<u8>,
}

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().collect();
    if arguments.len() < 3 {
        eprintln!("usage: tile_palettes <output folder> <config.toml>...");
        return ExitCode::FAILURE;
    }
    let output_folder = Path::new(&arguments[1]);
    // Each config's name names its output files, so two with the same name (in different
    // folders) would overwrite each other.
    let mut names_by_config: Vec<(String, String)> = Vec::new();
    for config_argument in &arguments[2..] {
        let result = run(Path::new(config_argument), output_folder).and_then(|name| {
            match names_by_config.iter().find(|(existing, _)| *existing == name) {
                Some((_, other)) => Err(format!("its name \"{}\" is also {}'s", name, other)),
                None => Ok(name),
            }
        });
        match result {
            Ok(name) => names_by_config.push((name, config_argument.clone())),
            Err(message) => {
                eprintln!("tile_palettes: {}: {}", config_argument, message);
                return ExitCode::FAILURE;
            }
        }
    }
    ExitCode::SUCCESS
}

// Returns the config's name.
fn run(config_path: &Path, output_folder: &Path) -> Result<String, String> {
    let config_text = fs::read_to_string(config_path).map_err(|error| error.to_string())?;
    let mut config: Config = toml::from_str(&config_text).map_err(|error| error.to_string())?;
    config.name = config_path.file_stem().and_then(|stem| stem.to_str())
        .ok_or_else(|| "the config's file name isn't text".to_string())?.to_string();
    validate(&config)?;

    let image_path = config_path.parent().unwrap_or(Path::new(".")).join(&config.image);
    let source = read_image(&image_path, &config)?;
    let sheet = build_sheet(&source, &config)?;

    fs::create_dir_all(output_folder)
        .map_err(|error| format!("can't create {}: {}", output_folder.display(), error))?;
    let header_name = format!("{}.h", config.name);
    write_if_changed(&output_folder.join(&header_name), header_source(&config, &sheet).as_bytes())?;
    write_if_changed(&output_folder.join(format!("{}.c", config.name)),
        data_source(&config, &sheet, &header_name).as_bytes())?;
    write_if_changed(&output_folder.join(format!("{}_preview.png", config.name)), &preview_png(&sheet)?)?;
    Ok(config.name)
}

fn validate(config: &Config) -> Result<(), String> {
    validate_identifier("config file name", &config.name)?;
    let mut image_components = Path::new(&config.image).components();
    if !matches!((image_components.next(), image_components.next()), (Some(Component::Normal(_)), None)) {
        return Err(format!("image \"{}\" must be a file in the config's folder", config.image));
    }
    if config.tile_width == 0 || config.tile_height == 0 {
        return Err("tile_width and tile_height must be above 0".to_string());
    }
    if config.tiles.is_empty() {
        return Err("no tiles".to_string());
    }
    if config.palettes.is_empty() {
        return Err("no palettes".to_string());
    }
    for tile in &config.tiles {
        validate_identifier("tile", tile)?;
    }
    for palette in &config.palettes {
        validate_identifier("palette", &palette.name)?;
        if palette.hue >= HUE_COUNT {
            return Err(format!("palette {}: hue {} isn't 0-{}", palette.name, palette.hue, HUE_COUNT - 1));
        }
    }
    for tile in &config.tiles {
        if RESERVED_TILE_NAMES.contains(&tile.as_str()) || tile.starts_with("palette_") {
            return Err(format!("tile name \"{}\" would collide with a generated name ({}_{})", tile,
                config.name.to_uppercase(), tile.to_uppercase()));
        }
    }
    for palette in &config.palettes {
        if palette.name == "count" {
            return Err(format!("palette name \"count\" would collide with {}_PALETTE_COUNT", config.name.to_uppercase()));
        }
    }
    validate_unique("tile", &config.tiles)?;
    validate_unique("palette", &config.palettes.iter().map(|palette| palette.name.clone()).collect::<Vec<_>>())?;
    Ok(())
}

// Names become C identifiers.
fn validate_identifier(kind: &str, name: &str) -> Result<(), String> {
    let mut characters = name.chars();
    let starts_with_letter = characters.next().is_some_and(|first| first.is_ascii_lowercase());
    if !starts_with_letter || !characters.all(|character| character.is_ascii_lowercase()
        || character.is_ascii_digit() || character == '_') {
        return Err(format!("{} name \"{}\" must be lower case letters, digits and _, starting with a letter",
            kind, name));
    }
    Ok(())
}

fn validate_unique(kind: &str, names: &[String]) -> Result<(), String> {
    for (index, name) in names.iter().enumerate() {
        if names[..index].contains(name) {
            return Err(format!("{} \"{}\" is listed twice", kind, name));
        }
    }
    Ok(())
}

fn parse_colors(config: &Config) -> Result<BTreeMap<[u8; 3], Pixel>, String> {
    let mut colors = BTreeMap::new();
    for (key, color) in &config.colors {
        let rgb = parse_hex_color(key)?;
        let pixel = match color {
            ColorConfig::Keyword(keyword) if keyword == TRANSPARENT_KEYWORD => None,
            ColorConfig::Keyword(keyword) => {
                return Err(format!("colour {}: \"{}\" isn't \"{}\" or a shade", key, keyword, TRANSPARENT_KEYWORD));
            }
            ColorConfig::Shade(shade) => {
                if shade.saturation >= SATURATION_COUNT || shade.luminance >= LUMINANCE_COUNT {
                    return Err(format!("colour {}: saturation must be 0-{} and luminance 0-{}", key,
                        SATURATION_COUNT - 1, LUMINANCE_COUNT - 1));
                }
                Some(*shade)
            }
        };
        if colors.insert(rgb, pixel).is_some() {
            return Err(format!("colour {} is listed twice", key));
        }
    }
    Ok(colors)
}

fn parse_hex_color(text: &str) -> Result<[u8; 3], String> {
    let invalid = || format!("colour \"{}\" isn't #rrggbb", text);
    let digits = text.strip_prefix('#').ok_or_else(invalid)?;
    if digits.len() != 6 || !digits.chars().all(|character| character.is_ascii_hexdigit()) {
        return Err(invalid());
    }
    let channel = |index: usize| u8::from_str_radix(&digits[index * 2..index * 2 + 2], 16).map_err(|_| invalid());
    Ok([channel(0)?, channel(1)?, channel(2)?])
}

// The source image as shades: every pixel's colour must be in the config, or fully transparent.
fn read_image(path: &Path, config: &Config) -> Result<ShadeSheet, String> {
    let colors = parse_colors(config)?;
    let image_error = |error: String| format!("{}: {}", path.display(), error);
    let file = fs::File::open(path).map_err(|error| image_error(error.to_string()))?;
    let mut decoder = png::Decoder::new(std::io::BufReader::new(file));
    decoder.set_transformations(png::Transformations::normalize_to_color8());
    let mut reader = decoder.read_info().map_err(|error| image_error(error.to_string()))?;
    let mut buffer = vec![0; reader.output_buffer_size()];
    let frame = reader.next_frame(&mut buffer).map_err(|error| image_error(error.to_string()))?;
    let channels = match frame.color_type {
        png::ColorType::Grayscale => 1,
        png::ColorType::GrayscaleAlpha => 2,
        png::ColorType::Rgb => 3,
        png::ColorType::Rgba => 4,
        png::ColorType::Indexed => return Err(image_error("still indexed after expanding".to_string())),
    };

    let expected_width = config.tile_width * config.tiles.len() as u32;
    if frame.width != expected_width || frame.height != config.tile_height {
        return Err(image_error(format!("is {}x{}, but {} tiles of {}x{} in a row make {}x{}", frame.width,
            frame.height, config.tiles.len(), config.tile_width, config.tile_height, expected_width,
            config.tile_height)));
    }

    let mut pixels = Vec::with_capacity((frame.width * frame.height) as usize);
    for y in 0..frame.height {
        let row = &buffer[y as usize * frame.line_size..];
        for x in 0..frame.width {
            let samples = &row[x as usize * channels..(x as usize + 1) * channels];
            let (rgb, alpha) = match channels {
                1 => ([samples[0]; 3], 255),
                2 => ([samples[0]; 3], samples[1]),
                3 => ([samples[0], samples[1], samples[2]], 255),
                _ => ([samples[0], samples[1], samples[2]], samples[3]),
            };
            let pixel = match alpha {
                0 => None,
                255 => *colors.get(&rgb).ok_or_else(|| image_error(format!(
                    "pixel {},{} is #{:02x}{:02x}{:02x}, which isn't in [colors]", x, y, rgb[0], rgb[1], rgb[2])))?,
                _ => return Err(image_error(format!("pixel {},{} is partly transparent", x, y))),
            };
            pixels.push(pixel);
        }
    }
    Ok(ShadeSheet { width: frame.width, height: frame.height, pixels })
}

// The output sheet: one row of tiles per palette, in colour bytes.
fn build_sheet(source: &ShadeSheet, config: &Config) -> Result<ColorSheet, String> {
    let mut bytes = Vec::with_capacity(source.pixels.len() * config.palettes.len());
    for palette in &config.palettes {
        for pixel in &source.pixels {
            bytes.push(match pixel {
                None => TRANSPARENT_BYTE,
                Some(shade) => color_byte(*shade, palette)?,
            });
        }
    }
    Ok(ColorSheet { width: source.width, height: source.height * config.palettes.len() as u32, bytes })
}

fn color_byte(shade: Shade, palette: &PaletteConfig) -> Result<u8, String> {
    let luminance = shade.luminance as i16 + palette.luminance as i16;
    if luminance < 0 || luminance >= LUMINANCE_COUNT as i16 {
        return Err(format!("palette {}: luminance {} plus {} is outside 0-{}", palette.name, shade.luminance,
            palette.luminance, LUMINANCE_COUNT - 1));
    }
    let byte = (palette.hue << 5) | (shade.saturation << 3) | luminance as u8;
    if byte == TRANSPARENT_BYTE {
        return Err(format!("palette {}: a colour comes out as byte 0, which the blitter draws as transparent",
            palette.name));
    }
    Ok(byte)
}

fn header_source(config: &Config, sheet: &ColorSheet) -> String {
    let prefix = config.name.to_uppercase();
    let mut text = String::new();
    text += &format!("// Generated by tools/tile_palettes from {}: don't edit.\n", config.image);
    text += &format!("#ifndef {}_H\n#define {}_H\n\n", prefix, prefix);
    text += "// The sheet: GameTank colour bytes, a row at a time, 0 transparent. Each palette is a row of\n";
    text += "// tiles, in the order below.\n";
    text += &format!("#define {}_SHEET_WIDTH {}\n", prefix, sheet.width);
    text += &format!("#define {}_SHEET_HEIGHT {}\n", prefix, sheet.height);
    text += &format!("#define {}_TILE_WIDTH {}\n", prefix, config.tile_width);
    text += &format!("#define {}_TILE_HEIGHT {}\n\n", prefix, config.tile_height);
    text += "enum {\n";
    for (index, tile) in config.tiles.iter().enumerate() {
        text += &format!("    {}_{} = {},\n", prefix, tile.to_uppercase(), index);
    }
    text += "};\n\nenum {\n";
    for (index, palette) in config.palettes.iter().enumerate() {
        text += &format!("    {}_PALETTE_{} = {},\n", prefix, palette.name.to_uppercase(), index);
    }
    text += &format!("    {}_PALETTE_COUNT = {},\n}};\n\n", prefix, config.palettes.len());
    text += "// Where a tile's top left corner is in the sheet.\n";
    text += &format!("#define {}_X(tile) ((tile) * {}_TILE_WIDTH)\n", prefix, prefix);
    text += &format!("#define {}_Y(palette) ((palette) * {}_TILE_HEIGHT)\n\n", prefix, prefix);
    text += &format!("extern const unsigned char {}_sheet[{}_SHEET_WIDTH * {}_SHEET_HEIGHT];\n\n", config.name,
        prefix, prefix);
    text += "#endif\n";
    text
}

fn data_source(config: &Config, sheet: &ColorSheet, header_name: &str) -> String {
    let prefix = config.name.to_uppercase();
    let mut text = String::new();
    text += &format!("// Generated by tools/tile_palettes from {}: don't edit.\n", config.image);
    text += &format!("#include \"{}\"\n\n", header_name);
    text += &format!("const unsigned char {}_sheet[{}_SHEET_WIDTH * {}_SHEET_HEIGHT] = {{\n", config.name, prefix,
        prefix);
    for (row_index, row) in sheet.bytes.chunks(sheet.width as usize).enumerate() {
        if row_index as u32 % config.tile_height == 0 {
            let palette = &config.palettes[(row_index as u32 / config.tile_height) as usize];
            text += &format!("    // {}\n", palette.name);
        }
        let bytes: Vec<String> = row.iter().map(|byte| format!("0x{:02x}", byte)).collect();
        text += &format!("    {},\n", bytes.join(", "));
    }
    text += "};\n";
    text
}

fn preview_png(sheet: &ColorSheet) -> Result<Vec<u8>, String> {
    let width = sheet.width * PREVIEW_SCALE;
    let height = sheet.height * PREVIEW_SCALE;
    let mut rgb = Vec::with_capacity((width * height * 3) as usize);
    for y in 0..height {
        for x in 0..width {
            let byte = sheet.bytes[((y / PREVIEW_SCALE) * sheet.width + x / PREVIEW_SCALE) as usize];
            rgb.extend_from_slice(&match byte {
                TRANSPARENT_BYTE => PREVIEW_TRANSPARENT,
                _ => gametank_palette::CAPTURE[byte as usize],
            });
        }
    }
    let mut png_bytes = Vec::new();
    let mut encoder = png::Encoder::new(&mut png_bytes, width, height);
    encoder.set_color(png::ColorType::Rgb);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header().map_err(|error| error.to_string())?;
    writer.write_image_data(&rgb).map_err(|error| error.to_string())?;
    writer.finish().map_err(|error| error.to_string())?;
    Ok(png_bytes)
}

fn write_if_changed(path: &PathBuf, contents: &[u8]) -> Result<(), String> {
    if fs::read(path).is_ok_and(|existing| existing == contents) {
        return Ok(());
    }
    fs::write(path, contents).map_err(|error| format!("can't write {}: {}", path.display(), error))
}
