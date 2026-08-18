# =========================================#
# backend.app.integrations.weave.exceptions
# =========================================#


"""
Custom exceptions for integration boundary
"""


class WeaveIntegrationError(Exception):
    """Base exception for communication with Weave Cloud"""


class WeaveUnavailableError(WeaveIntegrationError):
    """
    Raised when Weave cannot be reacherd because of a network,
    timeout, DNS or similar connectivity failure
    """


class WeaveRequestRejectedError(WeaveIntegrationError):
    """
    Raised when Weave successfully receives the request but rejects it
    """

    def __init__(
        self, *, status_code: int, detail: str, retry_after: int | None = None
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.retry_after = retry_after

        super().__init__(detail)


class WeaveContractError(WeaveIntegrationError):
    """
    Raised when Weave responds successfully but the response does not
    match the contract expected by this CBT version
    """
