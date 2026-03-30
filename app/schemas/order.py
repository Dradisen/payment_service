from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import OrderPaymentStatus
from app.schemas.payment import PaymentRead


class OrderRead(BaseModel):

    id: int
    amount: int
    payment_status: OrderPaymentStatus
    created_at: datetime
    updated_at: datetime
    payments: list[PaymentRead] = []

    model_config = ConfigDict(from_attributes=True)