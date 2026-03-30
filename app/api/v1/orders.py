from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.order import OrderRepository
from app.schemas.order import OrderRead
from app.schemas.payment import PaymentCreate, PaymentRead
from app.services.payment_service import (
    InsufficientOrderBalanceError,
    OrderAlreadyPaidError,
    OrderNotFoundError,
    PaymentService,
)
from app.exceptions import BankError, PaymentServiceError
from app.api.depends import payment_service


router = APIRouter(prefix="/orders", tags=["Заказы"])


@router.get(
    "",
    description="Список заказов", 
    response_model=list[OrderRead]
)
async def list_orders(
    session: AsyncSession = Depends(get_db),
) -> list[OrderRead]:
    repo = OrderRepository(session)
    orders = await repo.list()
    return [OrderRead.model_validate(o) for o in orders]


@router.get(
    "/{order_id}",
    description='Детальная информация по заказу',
    response_model=OrderRead
)
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_db),
) -> OrderRead:
    repo = OrderRepository(session)
    order = await repo.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")
    return OrderRead.model_validate(order)


@router.post(
    "/{order_id}/payments",
    description="Создать новый платеж и запустить процесс оплаты",
    response_model=PaymentRead,
    tags=["Платежные операции"],
    status_code=status.HTTP_201_CREATED,
)
async def deposit(
    order_id: int,
    body: PaymentCreate,
    session: AsyncSession = Depends(get_db),
    service: PaymentService = Depends(payment_service),
) -> PaymentRead:
    try:
        async with session.begin():
            payment = await service.deposit(
                order_id=order_id,
                amount=body.amount,
                payment_type=body.payment_type,
                session=session,
            )
        await session.refresh(payment)
        return PaymentRead.model_validate(payment)
    except OrderNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except OrderAlreadyPaidError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except InsufficientOrderBalanceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except BankError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    except PaymentServiceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))

