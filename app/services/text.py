# app/services/text.py
import re

WORD_RE = re.compile(r"\w+")

def text_summary(text: str) -> dict[str, int]:
    """
    Compute word count and character count for the given text.
    """
    words = WORD_RE.findall(text)
    return {
        "word_count": len(words),
        "char_count": len(text),
    }
