from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.payment import PaymentRead, PaymentSyncRead
from app.services.payment_service import (
    InvalidPaymentStatusError,
    NotAcquiringPaymentError,
    PaymentNotFoundError,
    PaymentService,
)
from app.api.depends import payment_service

router = APIRouter(prefix="/payments", tags=["Платежные операции"])


@router.post(
    "/{payment_id}/refund", 
    description="Возврат платежа",
    response_model=PaymentRead
)
async def refund(
    payment_id: int,
    session: AsyncSession = Depends(get_db),
    service: PaymentService = Depends(payment_service),
) -> PaymentRead:
    try:
        async with session.begin():
            payment = await service.refund(payment_id=payment_id, session=session)
            return PaymentRead.model_validate(payment)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidPaymentStatusError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))



@router.post(
    "/{payment_id}/sync", 
    description="Ручной вызов синхронизации статуса платежа с банком",
    response_model=PaymentSyncRead,
)
async def sync_acquiring(
    payment_id: int,
    session: AsyncSession = Depends(get_db),
    service: PaymentService = Depends(payment_service),
) -> PaymentSyncRead:
    try:
        async with session.begin():
            payment, synced, message = await service.sync_acquiring(
                payment_id=payment_id, session=session
            )
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NotAcquiringPaymentError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))

    return PaymentSyncRead(
        payment=PaymentRead.model_validate(payment),
        synced=synced,
        message=message,
    )
