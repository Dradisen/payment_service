from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PaymentStatus, PaymentType


class AcquiringDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_id: int
    bank_payment_id: str | None
    bank_status: str | None
    bank_amount: int | None
    bank_paid_at: datetime | None
    synced_at: datetime | None


class PaymentCreate(BaseModel):
    payment_type: PaymentType
    amount: int


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    payment_type: PaymentType
    amount: int
    status: PaymentStatus
    created_at: datetime
    updated_at: datetime | None
    acquiring_detail: AcquiringDetailRead | None = None


class PaymentSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment: PaymentRead
    synced: bool
    message: str
