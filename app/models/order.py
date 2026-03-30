
from sqlalchemy import Enum, Integer, case, func, literal, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base import BaseModel
from app.models.payment import Payment
from app.models.enums import PaymentStatus, OrderPaymentStatus


class Order(BaseModel):
    """Модель заказов"""
    
    __tablename__ = "orders"
    __name__ = "Заказы"
    
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    payments: Mapped[list["Payment"]] = relationship( 
        "Payment", foreign_keys="Payment.order_id", lazy="selectin", back_populates="order"
    )
    
    @hybrid_property
    def payment_status(self) -> OrderPaymentStatus:
        """Возвращает статус оплаты"""
        # TODO: нужно сделать в репозитории запросом, чтобы не грузить все платежи в память
        paid_amount = sum(p.amount for p in self.payments if p.status == PaymentStatus.COMPLETED)
        refunded_amount = sum(p.amount for p in self.payments if p.status == PaymentStatus.REFUNDED)
        print(refunded_amount)
        net_paid = paid_amount - refunded_amount
        if net_paid <= 0:
            return OrderPaymentStatus.UNPAID
        elif net_paid < self.amount:
            return OrderPaymentStatus.PARTIALLY_PAID
        else:
            return OrderPaymentStatus.PAID