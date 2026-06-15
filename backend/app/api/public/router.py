from fastapi import APIRouter

router = APIRouter(tags=["public"])


@router.get("/status")
async def public_status() -> dict[str, str]:
    return {"status": "public-api-ready"}
