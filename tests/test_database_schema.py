from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    Base,
    LabelModel,
    ProjectModel,
    TaskModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
    WorkspaceRole,
)


def test_schema_creates_all_tables_and_foreign_keys() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {
        "users",
        "workspaces",
        "workspace_members",
        "projects",
        "tasks",
        "labels",
        "task_labels",
        "comments",
        "refresh_tokens",
    }
    assert {key["referred_table"] for key in inspector.get_foreign_keys("tasks")} == {
        "projects",
        "users",
    }
    assert {
        key["referred_table"] for key in inspector.get_foreign_keys("task_labels")
    } == {
        "tasks",
        "labels",
    }
    assert {
        key["referred_table"] for key in inspector.get_foreign_keys("refresh_tokens")
    } == {"users"}
    engine.dispose()


def test_model_relationships() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = UserModel(
            email="owner@example.com", full_name="Owner", hashed_password="test"
        )
        workspace = WorkspaceModel(name="Workspace", owner=user)
        workspace.members.append(
            WorkspaceMemberModel(user=user, role=WorkspaceRole.OWNER)
        )
        project = ProjectModel(name="Project", workspace=workspace)
        task = TaskModel(title="Task", project=project)
        label = LabelModel(name="Backend", color="#123456", project=project)
        task.labels.append(label)
        session.add(user)
        session.commit()

        assert workspace.owner is user
        assert project in workspace.projects
        assert task in project.tasks
        assert label in task.labels
        assert task in label.tasks

    engine.dispose()
