from setu.web import pictures


def test_a_photo_is_used_when_the_file_exists_and_the_drawing_otherwise(tmp_path, monkeypatch):
    label = lambda key: "हिंदी"
    monkeypatch.setattr(pictures, "PHOTO_DIR", tmp_path)
    assert "<svg" in str(pictures.picture("పుస్తకం", label))
    (tmp_path / "book.webp").write_bytes(b"x")
    html = str(pictures.picture("పుస్తకం", label))
    assert 'src="/static/img/words/book.webp"' in html and 'alt="हिंदी"' in html


def test_numbers_stay_dots_even_if_a_photo_exists(tmp_path, monkeypatch):
    (tmp_path / "one.webp").write_bytes(b"x")
    monkeypatch.setattr(pictures, "PHOTO_DIR", tmp_path)
    assert "<svg" in str(pictures.picture("ఒకటి", lambda k: "x"))


def test_every_shipped_picture_belongs_to_a_word_and_is_credited():
    from setu.web.english import ENGLISH
    credits = (pictures.PHOTO_DIR / "PHOTO_CREDITS.md").read_text(encoding="utf-8")
    shipped = [p.name for p in pictures.PHOTO_DIR.iterdir() if p.suffix in (".webp", ".jpg", ".jpeg", ".png")]
    assert shipped
    words = {pictures.photo_file(te) for te in ENGLISH}
    for name in shipped:
        assert name in words and f"`{name}`" in credits
