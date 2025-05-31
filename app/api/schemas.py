from typing import List
from pydantic import BaseModel, field_validator

# Input schema for /payload endpoint
class PayloadIn(BaseModel):
    numbers: List[float]  # List of numbers to analyze
    text: str  # Text to analyze

    @field_validator('numbers')
    def check_numbers_min_length(cls, v):
        # Ensure at least one number is provided
        if len(v) < 1:
            raise ValueError('numbers must have at least 1 item')
        return v

    model_config = {"extra": "forbid"}  # Forbid extra fields in input

# Output schema for numeric analysis
class NumericSummary(BaseModel):
    min: float      # Minimum value
    max: float      # Maximum value
    mean: float     # Mean value
    median: float   # Median value
    stddev: float   # Standard deviation

# Output schema for text analysis
class TextSummary(BaseModel):
    word_count: int  # Number of words in text
    char_count: int  # Number of characters in text

# Output schema for /payload endpoint
class PayloadOut(BaseModel):
    numeric: NumericSummary  # Numeric analysis results
    text: TextSummary       # Text analysis results
