from fastapi import APIRouter

from ..profiles import IMPLEMENTED_PROFILES


router = APIRouter(tags=["Description"])


@router.get("/description", operation_id="GetSelfDescription")
async def get_self_description() -> dict:
    return {"profiles": IMPLEMENTED_PROFILES}
