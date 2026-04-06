from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from database import connect_db, disconnect_db
from routes.chat import router as chat_router
from routes.students import router as students_router
from routes.staff import router as staff_router
from routes.fees import router as fees_router
from routes.attendance import router as attendance_router
from routes.tools import router as tools_router
from routes.settings import router as settings_router
from routes.academics import router as academics_router
from routes.operations import router as operations_router
from routes.search import router as search_router
from routes.notifications import router as notifications_router
from routes.exports import router as exports_router
from routes.upload import router as upload_router
from routes.auth import router as auth_router
from routes.sms import router as sms_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="EduFlow API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(students_router)
app.include_router(staff_router)
app.include_router(fees_router)
app.include_router(attendance_router)
app.include_router(tools_router)
app.include_router(settings_router)
app.include_router(academics_router)
app.include_router(operations_router)
app.include_router(search_router)
app.include_router(notifications_router)
app.include_router(exports_router)
app.include_router(upload_router)
app.include_router(sms_router)


@app.on_event("startup")
async def startup():
    await connect_db()
    logger.info("EduFlow API started — MongoDB connected")


@app.on_event("shutdown")
async def shutdown():
    await disconnect_db()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "EduFlow API"}
