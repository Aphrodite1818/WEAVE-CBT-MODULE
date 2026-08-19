# ========================== #
# app.domains.node.router
# ========================== #

from fastapi import APIRouter, HTTPException, Response, status

from app.domains.node.exceptions import (
    InstallationAlreadyPairedError,
    NodeIdentityStorageError,
)
from app.domains.node.schemas import (
    InstallationStatus,
    PairInstallationRequest,
    PairInstallationResponse,
)
from app.domains.node.service import node_service
from app.integrations.weave.exceptions import (
    WeaveContractError,
    WeaveRequestRejectedError,
    WeaveUnavailableError,
)


router = APIRouter(
    prefix="/installation",
    tags=["Installation"],
)


@router.get(
    "/status",
    response_model=InstallationStatus,
)
def get_installation_status() -> InstallationStatus:
    return node_service.get_installation_status()


@router.post(
    "/pair",
    response_model=PairInstallationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def pair_installation(
    request: PairInstallationRequest,
    response: Response,
) -> PairInstallationResponse:
    """
    Pair this local CBT runtime with a Weave tenant.
    """

    try:
        return await node_service.pair_installation(request)

    except InstallationAlreadyPairedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except WeaveRequestRejectedError as exc:
        # Rate limiting needs one extra piece of information:
        # Retry-After.
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            if exc.retry_after is not None:
                response.headers["Retry-After"] = str(exc.retry_after)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=exc.detail,
                headers=(
                    {"Retry-After": str(exc.retry_after)}
                    if exc.retry_after is not None
                    else None
                ),
            ) from exc

        # Preserve normal client-side pairing rejection codes.
        if 400 <= exc.status_code < 500:
            raise HTTPException(
                status_code=exc.status_code,
                detail=exc.detail,
            ) from exc

        # A remote Weave 5xx is not an internal failure of the
        # local CBT API. From CBT's perspective its upstream failed.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weave Cloud could not complete the pairing request.",
        ) from exc

    except WeaveUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Weave Cloud is currently unreachable.",
        ) from exc

    except WeaveContractError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=("Weave Cloud returned an unexpected pairing response."),
        ) from exc

    except NodeIdentityStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "The CBT installation could not securely persist its local identity."
            ),
        ) from exc
