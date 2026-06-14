from fastapi import APIRouter

router = APIRouter(tags=["Health"])

@router.get("/")
def root():
    return {"status": "NEXUS ATMS running"}

@router.get("/health")
@router.get("/api/health")
def health():
    return {"status": "ok"}

@router.get("/ping")
def ping():
    return {"status": "ok"}
