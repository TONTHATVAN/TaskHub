from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.task import TaskPriority, TaskStatus
from app.domain.user import UserRole


class Base(DeclarativeBase):
    pass


class WorkspaceRole(StrEnum):
    OWNER = "OWNER"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class ProjectStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole, native_enum=False, create_constraint=True, validate_strings=True
        ),
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owned_workspaces: Mapped[list["WorkspaceModel"]] = relationship(
        back_populates="owner"
    )
    memberships: Mapped[list["WorkspaceMemberModel"]] = relationship(
        back_populates="user"
    )
    assigned_tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="assignee", foreign_keys="TaskModel.assignee_id"
    )
    created_tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="creator", foreign_keys="TaskModel.created_by"
    )
    comments: Mapped[list["CommentModel"]] = relationship(back_populates="author")
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(
        back_populates="user", passive_deletes=True
    )


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[UserModel] = relationship(back_populates="refresh_tokens")


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped[UserModel] = relationship(back_populates="owned_workspaces")
    members: Mapped[list["WorkspaceMemberModel"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", passive_deletes=True
    )
    projects: Mapped[list["ProjectModel"]] = relationship(
        back_populates="workspace", passive_deletes=True
    )


class WorkspaceMemberModel(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(
            WorkspaceRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        )
    )

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="members")
    user: Mapped[UserModel] = relationship(back_populates="memberships")


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(
            ProjectStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=ProjectStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="projects")
    tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    labels: Mapped[list["LabelModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )


class TaskModel(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    assignee_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus, native_enum=False, create_constraint=True, validate_strings=True
        ),
        default=TaskStatus.TODO,
        index=True,
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        default=TaskPriority.MEDIUM,
        index=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped[ProjectModel] = relationship(back_populates="tasks")
    assignee: Mapped[UserModel | None] = relationship(
        back_populates="assigned_tasks", foreign_keys=[assignee_id]
    )
    creator: Mapped[UserModel | None] = relationship(
        back_populates="created_tasks", foreign_keys=[created_by]
    )
    labels: Mapped[list["LabelModel"]] = relationship(
        secondary="task_labels", back_populates="tasks", passive_deletes=True
    )
    comments: Mapped[list["CommentModel"]] = relationship(
        back_populates="task", passive_deletes=True
    )


class LabelModel(Base):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        UniqueConstraint("id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(7))

    project: Mapped[ProjectModel] = relationship(back_populates="labels")
    tasks: Mapped[list[TaskModel]] = relationship(
        secondary="task_labels", back_populates="labels", passive_deletes=True
    )


class TaskLabelModel(Base):
    __tablename__ = "task_labels"

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[UUID] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )


class CommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task: Mapped[TaskModel] = relationship(back_populates="comments")
    author: Mapped[UserModel] = relationship(back_populates="comments")
