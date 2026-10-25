from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.audit import log_action
from app.core.permissions import can_edit_project, can_view_project
from app.models.audit_log import EntityType
from app.models.document import Document, DocumentStatus
from app.models.document_version import DocumentVersion
from app.models.project import Project
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.schemas.document_version import DocumentVersionReadWithCreator


class DocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, doc_id: int) -> Optional[Document]:
        return await self.session.get(Document, doc_id)

    async def _check_project_exists(self, project_id: int) -> Project:
        project = await self.session.get(Project, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    async def _check_document_exists(self, doc_id: int) -> Document:
        document = await self.get_by_id(doc_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        return document

    async def _check_edit_permission(self, user: User, project_id: int) -> None:
        if not await can_edit_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Editor access required"
            )

    async def _check_view_permission(self, user: User, project_id: int) -> None:
        if not await can_view_project(self.session, user, project_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this project",
            )

    async def _get_max_version(self, doc_id: int) -> int:
        # SELECT MAX(version) FROM document_versions WHERE document_id = :doc_id
        statement = select(func.max(DocumentVersion.version)).where(
            DocumentVersion.document_id == doc_id
        )
        return (await self.session.exec(statement)).first() or 0

    async def _get_version_or_404(self, doc_id: int, version: int) -> DocumentVersion:
        statement = select(DocumentVersion).where(
            DocumentVersion.document_id == doc_id,
            DocumentVersion.version == version,
        )
        ver = (await self.session.exec(statement)).first()
        if not ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
            )
        return ver

    async def create_document(
        self, project_id: int, doc_data: DocumentCreate, user: User
    ) -> Document:
        await self._check_project_exists(project_id)
        await self._check_edit_permission(user, project_id)

        document = Document(
            project_id=project_id,
            title=doc_data.title,
            content=doc_data.content or "",
            status=DocumentStatus.draft,
            created_by=user.id,
            updated_by=user.id,
        )
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)

        self.session.add(
            DocumentVersion(
                document_id=document.id,
                version=1,
                content_snapshot=document.content,
                created_by=user.id,
            )
        )
        await self.session.commit()

        await log_action(
            session=self.session,
            user_id=user.id,
            action="create_document",
            entity_type=EntityType.document,
            entity_id=document.id,
            meta={"title": document.title, "project_id": project_id},
        )
        return document

    async def list_documents(
        self, project_id: int, user: User, skip: int = 0, limit: int = 20
    ) -> list[Document]:
        await self._check_project_exists(project_id)
        await self._check_view_permission(user, project_id)

        statement = (
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.id)
            .offset(skip)
            .limit(limit)
        )
        return list((await self.session.exec(statement)).all())

    async def get_document(self, doc_id: int, user: User) -> Document:
        document = await self._check_document_exists(doc_id)
        await self._check_view_permission(user, document.project_id)
        return document

    async def update_document(
        self, doc_id: int, doc_data: DocumentUpdate, user: User
    ) -> Document:
        document = await self._check_document_exists(doc_id)
        await self._check_edit_permission(user, document.project_id)

        update_data = doc_data.model_dump(exclude_unset=True)
        content_changed = (
            "content" in update_data and update_data["content"] != document.content
        )

        for key, value in update_data.items():
            setattr(document, key, value)

        document.updated_by = user.id
        document.updated_at = datetime.now(timezone.utc)

        self.session.add(document)
        await self.session.commit()

        if content_changed:
            max_version = await self._get_max_version(doc_id)
            self.session.add(
                DocumentVersion(
                    document_id=doc_id,
                    version=max_version + 1,
                    content_snapshot=document.content or "",
                    created_by=user.id,
                )
            )
            await self.session.commit()

        await self.session.refresh(document)

        await log_action(
            session=self.session,
            user_id=user.id,
            action="update_document",
            entity_type=EntityType.document,
            entity_id=doc_id,
            meta={
                "updated_fields": list(update_data.keys()),
                "content_changed": content_changed,
            },
        )
        return document

    async def change_status(
        self, doc_id: int, new_status: DocumentStatus, user: User
    ) -> Document:
        document = await self._check_document_exists(doc_id)
        await self._check_edit_permission(user, document.project_id)

        old_status = document.status
        document.status = new_status
        document.updated_by = user.id
        document.updated_at = datetime.now(timezone.utc)

        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)

        await log_action(
            session=self.session,
            user_id=user.id,
            action=f"{new_status.value}_document",
            entity_type=EntityType.document,
            entity_id=doc_id,
            meta={"old_status": old_status.value, "new_status": new_status.value},
        )
        return document

    async def list_versions(
        self, doc_id: int, user: User
    ) -> list[DocumentVersionReadWithCreator]:
        document = await self._check_document_exists(doc_id)
        await self._check_view_permission(user, document.project_id)

        statement = (
            select(DocumentVersion, User.email)
            .join(User, User.id == DocumentVersion.created_by, isouter=True)
            .where(DocumentVersion.document_id == doc_id)
            .order_by(DocumentVersion.version.desc())
        )
        rows = (await self.session.exec(statement)).all()

        return [
            DocumentVersionReadWithCreator(**ver.model_dump(), creator_email=email)
            for ver, email in rows
        ]

    async def get_version(self, doc_id: int, version: int, user: User) -> DocumentVersion:
        document = await self._check_document_exists(doc_id)
        await self._check_view_permission(user, document.project_id)
        return await self._get_version_or_404(doc_id, version)

    async def restore_version(self, doc_id: int, version: int, user: User) -> Document:
        document = await self._check_document_exists(doc_id)
        await self._check_edit_permission(user, document.project_id)
        ver = await self._get_version_or_404(doc_id, version)

        document.content = ver.content_snapshot
        document.updated_by = user.id
        document.updated_at = datetime.now(timezone.utc)

        self.session.add(document)
        await self.session.commit()

        max_version = await self._get_max_version(doc_id)
        self.session.add(
            DocumentVersion(
                document_id=doc_id,
                version=max_version + 1,
                content_snapshot=document.content,
                created_by=user.id,
            )
        )
        await self.session.commit()
        await self.session.refresh(document)

        await log_action(
            session=self.session,
            user_id=user.id,
            action="restore_version",
            entity_type=EntityType.document,
            entity_id=doc_id,
            meta={"restored_version": version, "new_version": max_version + 1},
        )
        return document
