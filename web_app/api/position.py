"""
This module handles position-related API endpoints.
"""

from fastapi import APIRouter, HTTPException

from web_app.api.serializers.transaction import (
    LoopLiquidityData,
    RepayTransactionDataResponse,
)
from web_app.api.serializers.position import PositionFormData
from web_app.contract_tools.constants import (
    TokenParams,
    TokenMultipliers,
)
from web_app.api.serializers.position import TokenMultiplierResponse
from web_app.contract_tools.mixins.deposit import DepositMixin
from web_app.contract_tools.mixins.dashboard import DashboardMixin
from web_app.db.crud import PositionDBConnector

router = APIRouter()  # Initialize the router
position_db_connector = PositionDBConnector()  # Initialize the PositionDBConnector


@router.get(
    "/api/get-multipliers",
    tags=["Position Operations"],
    response_model=TokenMultiplierResponse,
    summary="Get token multipliers",
    response_description="Returns token multipliers",
)
async def get_multipliers() -> TokenMultiplierResponse:
    """
    This Endpoint retrieves the multipliers for tokens like ETH, STRK, and USDC.
    """
    multipliers = {
        "ETH": TokenMultipliers.ETH,
        "STRK": TokenMultipliers.STRK,
        "USDC": TokenMultipliers.USDC,
    }
    return TokenMultiplierResponse(multipliers=multipliers)


@router.post(
    "/api/create-position",
    tags=["Position Operations"],
    response_model=LoopLiquidityData,
    summary="Create a new position",
    response_description="Returns the new position and transaction data.",
)
async def create_position_with_transaction_data(
    form_data: PositionFormData,
) -> LoopLiquidityData:
    """
    This endpoint creates a new user position.

    ### Parameters:
    - **wallet_id**: The wallet ID of the user.
    - **token_symbol**: The symbol of the token used for the position.
    - **amount**: The amount of the token being deposited.
    - **multiplier**: The multiplier applied to the user's position.

    ### Returns:
    The created position's details and transaction data.
    """
    # Create a new position in the database
    position = position_db_connector.create_position(
        form_data.wallet_id,
        form_data.token_symbol,
        form_data.amount,
        form_data.multiplier,
    )
    borrowing_token = TokenParams.USDC.address
    if form_data.token_symbol == TokenParams.USDC.name:
        borrowing_token = TokenParams.ETH.address

    # Get the transaction data for the deposit
    deposit_data = await DepositMixin.get_transaction_data(
        form_data.token_symbol,
        form_data.amount,
        form_data.multiplier,
        form_data.wallet_id,
        borrowing_token,
    )
    deposit_data["contract_address"] = (
        position_db_connector.get_contract_address_by_wallet_id(form_data.wallet_id)
    )
    deposit_data["position_id"] = str(position.id)
    
    return LoopLiquidityData(**deposit_data)


@router.get(
    "/api/get-repay-data",
    tags=["Position Operations"],
    response_model=RepayTransactionDataResponse,
    summary="Get repay data",
    response_description="Returns the repay transaction data.",
)
async def get_repay_data(
    wallet_id: str
) -> RepayTransactionDataResponse:
    """
    Obtain data for position closing.
    :param wallet_id: Wallet ID
    :return: Dict containing the repay transaction data
    :raises: HTTPException :return: Dict containing status code and detail
    """
    # TODO rework it too many requests to DB
    if not wallet_id:
        raise HTTPException(status_code=404, detail="Wallet not found")

    contract_address = position_db_connector.get_contract_address_by_wallet_id(
        wallet_id
    )
    position_id = position_db_connector.get_position_id_by_wallet_id(wallet_id)
    position = position_db_connector.get_position_by_id(position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    repay_data = await DepositMixin.get_repay_data(position.token_symbol)
    repay_data["contract_address"] = contract_address
    repay_data["position_id"] = str(position_id)
    return repay_data


@router.get(
    "/api/close-position",
    tags=["Position Operations"],
    response_model=str,
    summary="Close a position",
    response_description="Returns the position status",
)
async def close_position(position_id: str) -> str:
    """
    Close a position.
    :param position_id: contract address
    :return: str
    :raises: HTTPException :return: Dict containing status code and detail
    """
    if position_id is None or position_id == "undefined":
        raise HTTPException(status_code=404, detail="Position not Found")

    position_status = position_db_connector.close_position(position_id)
    return position_status


@router.get(
    "/api/open-position",
    tags=["Position Operations"],
    response_model=str,
    summary="Open a position",
    response_description="Returns the positions status",
)
async def open_position(position_id: str) -> str:
    """
    Open a position.
    :param position_id: contract address
    :return: str
    :raises: HTTPException :return: Dict containing status code and detail
    """

    if not position_id:
        raise HTTPException(status_code=404, detail="Position not found")

    current_prices = await DashboardMixin.get_current_prices()
    position_status = position_db_connector.open_position(position_id, current_prices)
    return position_status
