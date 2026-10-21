"""Загрузка документов клиентом (PDF/JPG/PNG до 10 МБ). Файлы лежат в docker volume (UPLOAD_DIR).

Когда загружены все запрошенные документы, заявка сама возвращается на проверку:
INFO_REQUESTED → CHECKING + задача воркеру. После повторной проверки она идёт к специалисту.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.config import settings
from app.deps import DB, AnalystUser, ClientUser, get_owned_application
from app.enums import AppStatus, DocStatus, JobStatus, JobType
from app.errors import Conflict, NotFound, ValidationFailed
from app.models import DocumentRequest, Job
from app.schemas import ApplicationOut
from app.services.state_machine import Actor, transition
from app.views import application_out

router = APIRouter(tags=["Документы"])

MAX_BYTES = 10 * 1024 * 1024
# Тип файла определяем по первым байтам, а не по расширению — его легко подделать.
SIGNATURES = {b"%PDF": "pdf", b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}
MEDIA_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "png": "image/png"}


def _detect(head: bytes) -> str | None:
    return next((ext for sig, ext in SIGNATURES.items() if head.startswith(sig)), None)


@router.post(
    "/applications/{application_id}/documents",
    response_model=ApplicationOut,
    summary="Загрузить документ по запросу банка",
)
def upload_document(
    application_id: int,
    db: DB,
    user: ClientUser,
    document_request_id: int = Form(description="Какой из запрошенных документов загружаем"),
    file: UploadFile = File(description="PDF, JPG или PNG до 10 МБ"),
) -> ApplicationOut:
    app = get_owned_application(db, application_id, user, for_update=True)
    if app.status != AppStatus.INFO_REQUESTED:
        raise Conflict("Сейчас документы по этой заявке не нужны")
    doc = db.get(DocumentRequest, document_request_id)
    if doc is None or doc.application_id != app.id:
        raise NotFound("Такой документ по заявке не запрашивали")

    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValidationFailed("Файл больше 10 МБ. Сожмите его или загрузите по частям")
    if not data:
        raise ValidationFailed("Файл пустой")
    ext = _detect(data[:8])
    if ext is None:
        raise ValidationFailed("Подходят только PDF, JPG или PNG")

    folder = Path(settings.upload_dir) / str(app.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}.{ext}"
    path.write_bytes(data)

    doc.status = DocStatus.UPLOADED
    doc.file_path = str(path)
    doc.file_name = (file.filename or f"document.{ext}")[:255]
    db.flush()

    # Всё, что просили, загружено → заявка снова идёт на проверку.
    waiting = db.scalar(
        select(DocumentRequest.id).where(
            DocumentRequest.application_id == app.id, DocumentRequest.status == DocStatus.REQUESTED
        )
    )
    if waiting is None:
        transition(db, app, AppStatus.CHECKING, Actor.of(user), comment="Клиент загрузил документы")
        db.add(Job(type=JobType.PROCESS_APPLICATION, application_id=app.id, status=JobStatus.PENDING))
    db.commit()
    return application_out(db, app)


@router.get("/analyst/documents/{document_id}", tags=["Кабинет специалиста"], summary="Скачать документ клиента")
def download_document(document_id: int, db: DB, _user: AnalystUser) -> FileResponse:
    doc = db.get(DocumentRequest, document_id)
    if doc is None or not doc.file_path or not Path(doc.file_path).exists():
        raise NotFound("Файл не найден")
    ext = Path(doc.file_path).suffix.lstrip(".")
    return FileResponse(doc.file_path, media_type=MEDIA_TYPES.get(ext), filename=doc.file_name, content_disposition_type="inline")
