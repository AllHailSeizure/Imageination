from pathlib import Path

from PIL import Image

from imageination.recipe import Recipe
from imageination.session import RecipeSession


def save_rgba(path: Path, pixels, size=(1, 1)):
    image = Image.new("RGBA", size)
    image.putdata(pixels)
    image.save(path)


def test_session_add_folder_uses_only_top_level_pngs(tmp_path):
    (tmp_path / "nested").mkdir()
    save_rgba(tmp_path / "a.png", [(1, 2, 3, 255)])
    save_rgba(tmp_path / "nested" / "b.png", [(1, 2, 3, 255)])
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    session = RecipeSession()

    session.add_folder(tmp_path)

    assert session.inputs == [tmp_path / "a.png"]
    assert session.selected_index == 0


def test_session_preview_is_none_without_selected_input():
    assert RecipeSession(recipe=Recipe()).preview() is None
