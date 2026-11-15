from setu.web import pictures


def test_a_photo_is_used_when_the_file_exists_and_the_drawing_otherwise(tmp_path, monkeypatch):
    label = lambda key: "हिंदी"
    assert "<svg" in str(pictures.picture("పుస్తకం", label))
    (tmp_path / "book.webp").write_bytes(b"x")
    monkeypatch.setattr(pictures, "PHOTO_DIR", tmp_path)
    html = str(pictures.picture("పుస్తకం", label))
    assert 'src="/static/img/words/book.webp"' in html and 'alt="हिंदी"' in html


def test_numbers_stay_dots_even_if_a_photo_exists(tmp_path, monkeypatch):
    (tmp_path / "one.webp").write_bytes(b"x")
    monkeypatch.setattr(pictures, "PHOTO_DIR", tmp_path)
    assert "<svg" in str(pictures.picture("ఒకటి", lambda k: "x"))
