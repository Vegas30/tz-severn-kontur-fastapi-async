from fastapi import APIRouter, Depends, Query, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.document import DocumentStatus
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.schemas.document_version import DocumentVersionRead, DocumentVersionReadWithCreator
from app.services.document_service import DocumentService

router = APIRouter(tags=["Documents"])


@router.post(
    "/projects/{project_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    project_id: int,
    doc_data: DocumentCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).create_document(project_id, doc_data, current_user)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    project_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).list_documents(project_id, current_user, skip, limit)


@router.get("/documents/{doc_id}", response_model=DocumentRead)
async def get_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).get_document(doc_id, current_user)


@router.patch("/documents/{doc_id}", response_model=DocumentRead)
async def update_document(
    doc_id: int,
    doc_data: DocumentUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).update_document(doc_id, doc_data, current_user)


@router.post("/documents/{doc_id}/publish", response_model=DocumentRead)
async def publish_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).change_status(
        doc_id, DocumentStatus.published, current_user
    )


@router.post("/documents/{doc_id}/archive", response_model=DocumentRead)
async def archive_document(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).change_status(
        doc_id, DocumentStatus.archived, current_user
    )


@router.get("/documents/{doc_id}/versions", response_model=list[DocumentVersionReadWithCreator])
async def list_document_versions(
    doc_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).list_versions(doc_id, current_user)


@router.get("/documents/{doc_id}/versions/{version}", response_model=DocumentVersionRead)
async def get_document_version(
    doc_id: int,
    version: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).get_version(doc_id, version, current_user)


@router.post("/documents/{doc_id}/versions/{version}/restore", response_model=DocumentRead)
async def restore_document_version(
    doc_id: int,
    version: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return await DocumentService(session).restore_version(doc_id, version, current_user)
