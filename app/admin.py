from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/ping")
def admin_ping():
    """Simple test route for admin area."""
    return {"message": "Admin router working!"}
