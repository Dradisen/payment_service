

class BankError(Exception):
    
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

class BankPaymentNotFoundError(BankError): ...
class BankValidationError(BankError): ...