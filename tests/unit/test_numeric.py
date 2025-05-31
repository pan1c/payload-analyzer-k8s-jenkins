import pytest
from app.services.numeric import numeric_summary

def test_numeric_summary_basic():
    data = [1, 2, 3, 4, 5]
    result = numeric_summary(data)
    assert result["min"] == 1
    assert result["max"] == 5
    assert result["mean"] == 3
    assert result["median"] == 3
    assert round(result["stddev"], 3) == 1.581

def test_numeric_summary_empty():
    with pytest.raises(ValueError):
        numeric_summary([])
