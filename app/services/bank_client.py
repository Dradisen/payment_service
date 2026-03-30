import httpx

from app.conf.base import config
from app.exceptions.bank import BankError, BankValidationError
from app.schemas.bank import BankCheckResponse, BankStartResponse

from pydantic import ValidationError

class BankAPIClient:
    """
    HTTP-клиент для API банка-эквайера
    """

    def __init__(self, timeout: int=10) -> None:
        self._base_url = config.BANK_API_URL
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers={
                "Content-Type": "application/json"
            },
        )

    async def start_acquiring(self, order_id: int, amount: int) -> BankStartResponse:
        """Запускает процесс оплаты в банке, возвращая идентификатор платежа в банке."""
        payload = {"order_id": str(order_id), "amount": str(amount)}
        async with self._client() as client:
            try:
                response = await client.post("/acquiring_start", json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise BankError(
                    f"Ошибка ответа от банка: {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise BankError(f"Не удалось связаться с банком: {exc}") from exc

        data = response.json()
        if "error" in data:
            raise BankError(data["error"])

        try:
            return BankStartResponse(bank_payment_id=data["bank_payment_id"])
        except (KeyError, TypeError) as exc:
            raise BankError(f"Непредвиденный ответ от банка: {data}") from exc
        except ValidationError as exc:
            raise BankValidationError(f"Ошибка валидации: {data}") from exc

    async def check_acquiring(self, bank_payment_id: str) -> BankCheckResponse:
        """Проверяет статус оплаты в банке по идентификатору платежа."""

        payload = {"bank_payment_id": bank_payment_id}
        async with self._client() as client:
            try:
                response = await client.post("/acquiring_check", json=payload)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise BankError(
                    f"Ошибка HTTP {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except httpx.RequestError as exc:
                raise BankError(f"Не удалось связаться с банком: {exc}") from exc

        data = response.json()
        if "error" in data:
            raise BankError(data["error"])

        try:
            return BankCheckResponse(
                bank_payment_id=data.get("bank_payment_id"),
                amount=int(data.get("amount", 0)),
                status=data.get("status"),
                paid_at=data.get("paid_at"),
            )
        except (KeyError, TypeError) as exc:
            raise BankError(f"Неожиданный ответ от банка: {data}") from exc
        except ValidationError as exc:
            raise BankValidationError(f"Ошибка валидации: {data}") from exc


bank_client = BankAPIClient()
