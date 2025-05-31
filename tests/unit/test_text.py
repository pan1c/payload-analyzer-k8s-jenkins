from app.services.text import text_summary

def test_text_summary_basic():
    text = "Hello world! This is a test."
    result = text_summary(text)
    assert result["word_count"] == 6
    assert result["char_count"] == len(text)

def test_text_summary_empty():
    result = text_summary("")
    assert result["word_count"] == 0
    assert result["char_count"] == 0
