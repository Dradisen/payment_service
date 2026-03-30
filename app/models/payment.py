from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.enums import PaymentStatus, PaymentType


class Payment(BaseModel):
    __tablename__ = "payments"
    __name__ = "Платежи"

    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    order:            Mapped["Order"] = relationship("Order", back_populates="payments")
    acquiring_detail: Mapped["AcquiringDetail"] = relationship(
        "AcquiringDetail", back_populates="payment", lazy='selectin', uselist=False, cascade="all, delete-orphan"
    )


class AcquiringDetail(BaseModel):
    __tablename__ = "acquiring_details"
    __name__ = "Детали эквайринга"

    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    bank_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    bank_status:     Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_amount:     Mapped[int | None] = mapped_column(Integer, nullable=True)
    bank_paid_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at:       Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment:         Mapped["Payment"] = relationship("Payment", back_populates="acquiring_detail")
