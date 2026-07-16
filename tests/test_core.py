from pathlib import Path

from PIL import Image

from imageination.core import (
    apply_color_map,
    apply_color_map_batch,
    build_color_map,
    build_cell_color_map,
    extract_hex_values,
    image_data,
    parse_manual_map,
)


def save_rgba(path: Path, pixels, size=(2, 2)):
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    image.save(path)


def test_extract_hex_values_returns_sorted_unique_rgb_hex(tmp_path):
    image_path = tmp_path / "source.png"
    save_rgba(
        image_path,
        [
            (255, 0, 0, 255),
            (0, 255, 0, 255),
            (255, 0, 0, 255),
            (1, 2, 3, 0),
        ],
    )

    assert extract_hex_values(image_path) == ["#00FF00", "#FF0000"]


def test_build_color_map_counts_aligned_pixel_transforms(tmp_path):
    source_path = tmp_path / "source.png"
    target_path = tmp_path / "target.png"
    save_rgba(source_path, [(255, 0, 0, 255), (0, 0, 255, 255), (255, 0, 0, 255), (9, 9, 9, 0)])
    save_rgba(target_path, [(0, 255, 0, 255), (8, 8, 8, 255), (0, 255, 0, 255), (1, 1, 1, 255)])

    assert build_color_map(source_path, target_path) == {
        "#0000FF": {"target": "#080808", "count": 1},
        "#FF0000": {"target": "#00FF00", "count": 2},
    }


def test_build_cell_color_map_compares_dominant_cell_colors(tmp_path):
    source_path = tmp_path / "source.png"
    target_path = tmp_path / "target.png"
    save_rgba(
        source_path,
        [
            (255, 0, 0, 255), (255, 0, 0, 255), (0, 0, 255, 255), (0, 0, 255, 255),
            (255, 0, 0, 255), (1, 1, 1, 255), (0, 0, 255, 255), (2, 2, 2, 255),
        ],
        size=(4, 2),
    )
    save_rgba(
        target_path,
        [
            (0, 255, 0, 255), (0, 255, 0, 255), (9, 9, 9, 255), (9, 9, 9, 255),
            (0, 255, 0, 255), (3, 3, 3, 255), (9, 9, 9, 255), (4, 4, 4, 255),
        ],
        size=(4, 2),
    )

    assert build_cell_color_map(source_path, target_path, frame_width=2, frame_height=2) == {
        "#0000FF": {"target": "#090909", "count": 1},
        "#FF0000": {"target": "#00FF00", "count": 1},
    }


def test_parse_manual_map_accepts_arrows_commas_and_plain_pairs():
    text = """
    #ff0000 -> #00ff00
    0000ff, 111111
    abcdef 123456
    """

    assert parse_manual_map(text) == {
        "#FF0000": "#00FF00",
        "#0000FF": "#111111",
        "#ABCDEF": "#123456",
    }


def test_apply_color_map_recolors_matching_opaque_pixels(tmp_path):
    source_path = tmp_path / "source.png"
    out_path = tmp_path / "out.png"
    save_rgba(source_path, [(255, 0, 0, 255), (0, 0, 255, 255), (255, 0, 0, 0), (1, 2, 3, 255)])

    apply_color_map(source_path, out_path, {"#FF0000": "#00FF00", "#010203": "#040506"})

    with Image.open(out_path).convert("RGBA") as image:
        assert list(image_data(image)) == [
            (0, 255, 0, 255),
            (0, 0, 255, 255),
            (255, 0, 0, 0),
            (4, 5, 6, 255),
        ]


def test_apply_color_map_batch_recolors_supported_images_only(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    save_rgba(input_dir / "a.png", [(255, 0, 0, 255)], size=(1, 1))
    save_rgba(input_dir / "b.bmp", [(1, 2, 3, 255)], size=(1, 1))
    (input_dir / "notes.txt").write_text("#FF0000", encoding="utf-8")

    outputs = apply_color_map_batch(input_dir, output_dir, {"#FF0000": "#00FF00", "#010203": "#040506"})

    assert [path.name for path in outputs] == ["a.png", "b.bmp"]
    with Image.open(output_dir / "a.png").convert("RGBA") as image:
        assert list(image_data(image)) == [(0, 255, 0, 255)]
    with Image.open(output_dir / "b.bmp").convert("RGBA") as image:
        r, g, b, a = list(image_data(image))[0]
        assert (r, g, b, a) == (4, 5, 6, 255)
    assert not (output_dir / "notes.txt").exists()
