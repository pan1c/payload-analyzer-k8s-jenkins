#import time
from fastapi import APIRouter, HTTPException

from app.services.numeric import numeric_summary
from app.services.text import text_summary
from app.api.schemas import PayloadIn, PayloadOut, NumericSummary, TextSummary

router = APIRouter()

@router.post("/payload", response_model=PayloadOut)
async def analyze(body: PayloadIn):
    """
    Accepts a JSON payload with 'numbers' and 'text'.
    Returns numeric and text analysis.
    Responds with 400 Bad Request for malformed input.
    Custom 400 error handling is implemented to allign with the assignment requirements.
    """
    # Artificial delay for demonstration/testing (remove in production)
    # await asyncio.sleep(5)
    # for i in range(30):
    #   print("Sleeping", i)
    #   time.sleep(1)
    try:
        return PayloadOut(
            numeric=NumericSummary(**numeric_summary(body.numbers)),
            text=TextSummary(**text_summary(body.text)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
