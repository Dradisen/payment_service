from pydantic import BaseModel

from datetime import datetime

class BankStartResponse(BaseModel):
    bank_payment_id: str


class BankCheckResponse(BaseModel):
    bank_payment_id: str
    amount: int
    status: str
    paid_at: datetime | None = None