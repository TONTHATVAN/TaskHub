from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.api.dependencies import (
    get_current_user,
    get_task_authorization_service,
    get_task_cache_service,
    get_task_repository,
)
from app.domain.authorization import ProjectAccess
from app.domain.project import Project, ProjectStatus
from app.domain.task import Task, TaskPriority, TaskStatus
from app.domain.user import User, UserRole
from app.infrastructure.in_memory_task_repository import InMemoryTaskRepository
from app.infrastructure.task_cache import (
    InMemoryTaskCacheService,
    RedisTaskCacheService,
    build_task_cache_key,
    deserialize_task,
    serialize_task,
)
from app.main import create_app


def create_sample_task(
    project_id: UUID | None = None,
    title: str = "Test Task",
    assignee_id: UUID | None = None,
    due_date: datetime | None = None,
) -> Task:
    return Task(
        id=uuid4(),
        project_id=project_id or uuid4(),
        title=title,
        description="Sample description",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        created_at=datetime.now(UTC),
        assignee_id=assignee_id,
        due_date=due_date,
        created_by=uuid4(),
    )


def test_build_task_cache_key() -> None:
    project_id = uuid4()
    assignee_id = uuid4()

    key_defaults = build_task_cache_key(project_id, page=1, limit=20)
    assert key_defaults == f"taskhub:tasks:{project_id}:p=1:l=20:s=all:pr=all:a=all"

    key_filtered = build_task_cache_key(
        project_id,
        page=2,
        limit=10,
        status=TaskStatus.IN_PROGRESS,
        priority=TaskPriority.URGENT,
        assignee_id=assignee_id,
    )
    assert key_filtered == (
        f"taskhub:tasks:{project_id}:p=2:l=10:s=IN_PROGRESS:pr=URGENT:a={assignee_id}"
    )


def test_task_serialization_and_deserialization() -> None:
    assignee_id = uuid4()
    due_date = datetime.now(UTC)
    task = create_sample_task(assignee_id=assignee_id, due_date=due_date)

    data = serialize_task(task)
    assert data["id"] == str(task.id)
    assert data["project_id"] == str(task.project_id)
    assert data["title"] == task.title
    assert data["status"] == "TODO"
    assert data["priority"] == "HIGH"
    assert data["assignee_id"] == str(assignee_id)
    assert data["due_date"] == due_date.isoformat()

    restored = deserialize_task(data)
    assert restored == task
    assert restored.due_date is not None
    assert restored.due_date.utcoffset() == due_date.utcoffset()


@pytest.mark.asyncio
async def test_in_memory_task_cache_service_crud() -> None:
    cache = InMemoryTaskCacheService()
    project_id = uuid4()
    other_project_id = uuid4()
    task1 = create_sample_task(project_id)
    task2 = create_sample_task(project_id)
    other_task = create_sample_task(other_project_id)

    # Cache miss
    miss = await cache.get_tasks(project_id, page=1, limit=20)
    assert miss is None
    assert cache.get_calls == 1

    # Set and cache hit
    await cache.set_tasks(project_id, page=1, limit=20, tasks=[task1, task2])
    await cache.set_tasks(other_project_id, page=1, limit=20, tasks=[other_task])
    assert cache.set_calls == 2

    hit = await cache.get_tasks(project_id, page=1, limit=20)
    assert hit == [task1, task2]
    assert cache.get_calls == 2

    other_hit = await cache.get_tasks(other_project_id, page=1, limit=20)
    assert other_hit == [other_task]

    # Invalidate project
    await cache.invalidate_project(project_id)
    assert cache.invalidate_calls == 1
    assert await cache.get_tasks(project_id, page=1, limit=20) is None
    # Other project's cache should remain intact
    assert await cache.get_tasks(other_project_id, page=1, limit=20) == [other_task]

    # Invalidate all
    await cache.invalidate_all()
    assert await cache.get_tasks(other_project_id, page=1, limit=20) is None


@pytest.mark.asyncio
async def test_redis_task_cache_service_operations() -> None:
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    service = RedisTaskCacheService(mock_redis, ttl_seconds=60)
    project_id = uuid4()

    # Miss
    result = await service.get_tasks(project_id, page=1, limit=20)
    assert result is None
    mock_redis.get.assert_awaited_once()

    # Set
    task = create_sample_task(project_id)
    await service.set_tasks(project_id, page=1, limit=20, tasks=[task])
    mock_redis.set.assert_awaited_once()
    call_args = mock_redis.set.call_args
    assert call_args[1]["ex"] == 60

    # Invalidate
    async def mock_scan_iter(match: str, count: int):  # type: ignore[no-untyped-def]
        yield "key1"
        yield "key2"

    mock_redis.scan_iter = mock_scan_iter
    await service.invalidate_project(project_id)
    mock_redis.delete.assert_awaited_once_with("key1", "key2")


@pytest.mark.asyncio
async def test_redis_task_cache_service_graceful_fallback() -> None:
    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(side_effect=RedisConnectionError("Connection lost"))
    mock_redis.set = AsyncMock(side_effect=RedisConnectionError("Connection lost"))
    mock_redis.delete = AsyncMock(side_effect=RedisConnectionError("Connection lost"))

    service = RedisTaskCacheService(mock_redis, ttl_seconds=60)
    project_id = uuid4()

    # Should not raise exception on Redis failure
    result = await service.get_tasks(project_id, page=1, limit=20)
    assert result is None

    # Set should handle error gracefully without raising
    await service.set_tasks(project_id, page=1, limit=20, tasks=[])

    # Invalidate should handle error gracefully without raising
    async def mock_scan_iter(match: str, count: int):  # type: ignore[no-untyped-def]
        raise RedisConnectionError("Connection lost")
        yield "key"

    mock_redis.scan_iter = mock_scan_iter
    await service.invalidate_project(project_id)


def test_api_tasks_caching_and_invalidation_flow() -> None:
    class CountingRepository(InMemoryTaskRepository):
        def __init__(self) -> None:
            super().__init__()
            self.list_calls = 0

        async def list_by_project(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.list_calls += 1
            return await super().list_by_project(*args, **kwargs)

    repository = CountingRepository()
    cache = InMemoryTaskCacheService()
    project_id = uuid4()
    user_id = uuid4()

    class TestProjectAccess:
        def __init__(self, repo: InMemoryTaskRepository) -> None:
            self.repo = repo

        async def require_project(
            self, user: User, proj_id: UUID, *, write: bool
        ) -> ProjectAccess:
            return ProjectAccess(
                owner_id=user.id,
                member_role=None,
                project=Project(
                    proj_id,
                    uuid4(),
                    "Test Project",
                    None,
                    ProjectStatus.ACTIVE,
                    datetime.now(UTC),
                ),
            )

        async def require_task(self, user: User, task_id: UUID, *, write: bool) -> Task:
            task = await self.repo.get(task_id)
            assert task is not None
            return task

    app = create_app()
    app.dependency_overrides[get_task_repository] = lambda: repository
    app.dependency_overrides[get_task_cache_service] = lambda: cache
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id,
        email="user@example.com",
        full_name="User",
        hashed_password="disabled",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_task_authorization_service] = lambda: (
        TestProjectAccess(repository)
    )

    with TestClient(app) as client:
        endpoint = f"/api/v1/projects/{project_id}/tasks"

        # 1. First GET: cache miss, queries repository
        res1 = client.get(endpoint)
        assert res1.status_code == 200
        assert res1.json() == []
        assert repository.list_calls == 1
        assert cache.get_calls == 1
        assert cache.set_calls == 1

        # 2. Second GET: cache hit! Repository is NOT queried
        res2 = client.get(endpoint)
        assert res2.status_code == 200
        assert res2.json() == []
        assert repository.list_calls == 1  # Unchanged!
        assert cache.get_calls == 2

        # 3. Create a task -> Invalidation triggered!
        created = client.post(endpoint, json={"title": "New Task"})
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert cache.invalidate_calls == 1

        # 4. Third GET: cache miss (due to invalidation), queries repository again
        res3 = client.get(endpoint)
        assert res3.status_code == 200
        assert len(res3.json()) == 1
        assert res3.json()[0]["id"] == task_id
        assert repository.list_calls == 2  # Queried DB again!
        assert cache.get_calls == 3
        assert cache.set_calls == 2

        # 5. Fourth GET: cache hit!
        res4 = client.get(endpoint)
        assert res4.status_code == 200
        assert repository.list_calls == 2  # Still 2!
        assert cache.get_calls == 4

        # 6. Update task -> Invalidation triggered!
        updated = client.patch(f"/api/v1/tasks/{task_id}", json={"title": "Updated"})
        assert updated.status_code == 200
        assert cache.invalidate_calls == 2

        # 7. Fifth GET: cache miss, returns updated title
        res5 = client.get(endpoint)
        assert res5.status_code == 200
        assert res5.json()[0]["title"] == "Updated"
        assert repository.list_calls == 3

        # 8. Delete task -> Invalidation triggered!
        deleted = client.delete(f"/api/v1/tasks/{task_id}")
        assert deleted.status_code == 204
        assert cache.invalidate_calls == 3

        # 9. Sixth GET: cache miss, returns empty list
        res6 = client.get(endpoint)
        assert res6.status_code == 200
        assert res6.json() == []
        assert repository.list_calls == 4


@pytest.mark.asyncio
async def test_workspace_remove_member_invalidates_only_workspace_projects() -> None:
    from app.application.workspace_service import WorkspaceService
    from app.domain.workspace import Workspace, WorkspaceRole

    workspace_id = uuid4()
    owner_id = uuid4()
    member_id = uuid4()

    workspace = Workspace(workspace_id, "Target Workspace", owner_id, datetime.now(UTC))

    class StubWorkspaceRepo:
        def __init__(self) -> None:
            self.committed = False

        async def add(self, name: str, owner_id: UUID) -> Workspace:
            return workspace

        async def get(self, ws_id: UUID) -> Workspace | None:
            return workspace

        async def rename(self, ws_id: UUID, name: str) -> Workspace | None:
            return None

        async def delete(self, ws_id: UUID) -> bool:
            return False

        async def get_member_role(
            self, ws_id: UUID, user_id: UUID, *, for_update: bool = False
        ) -> WorkspaceRole | None:
            return None

        async def list_members(self, ws_id: UUID, *, page: int = 1, limit: int = 20):
            return [], 0

        async def add_member(
            self, ws_id: UUID, user_id: UUID, role: WorkspaceRole
        ) -> bool:
            return True

        async def remove_member(self, ws_id: UUID, user_id: UUID) -> bool:
            return True

        async def commit(self) -> None:
            self.committed = True

    project_1 = Project(
        uuid4(), workspace_id, "P1", None, ProjectStatus.ACTIVE, datetime.now(UTC)
    )
    project_2 = Project(
        uuid4(), workspace_id, "P2", None, ProjectStatus.ACTIVE, datetime.now(UTC)
    )

    class StubProjectRepo:
        async def list_by_workspace(
            self, ws_id: UUID, *, page: int = 1, limit: int = 20
        ) -> tuple[list[Project], int]:
            if ws_id == workspace_id:
                return [project_1, project_2], 2
            return [], 0

    class TrackingCache(InMemoryTaskCacheService):
        def __init__(self) -> None:
            super().__init__()
            self.invalidated_projects: list[UUID] = []
            self.all_invalidated = False

        async def invalidate_project(self, project_id: UUID) -> None:
            self.invalidated_projects.append(project_id)
            await super().invalidate_project(project_id)

        async def invalidate_all(self) -> None:
            self.all_invalidated = True
            await super().invalidate_all()

    class StubUserRepo:
        async def get_by_id(self, user_id: UUID) -> User | None:
            return None

    repo = StubWorkspaceRepo()
    proj_repo = StubProjectRepo()
    cache = TrackingCache()
    service = WorkspaceService(
        repository=repo,  # type: ignore[arg-type]
        users=StubUserRepo(),  # type: ignore[arg-type]
        cache=cache,
        projects=proj_repo,  # type: ignore[arg-type]
    )

    await service.remove_member(workspace, member_id)

    assert repo.committed is True
    assert cache.all_invalidated is False
    assert set(cache.invalidated_projects) == {project_1.id, project_2.id}


def test_redis_settings_and_client_have_timeout() -> None:
    from app.infrastructure.redis import get_redis_client
    from app.infrastructure.settings import settings

    assert settings.redis_socket_timeout > 0
    assert settings.redis_connect_timeout > 0

    client = get_redis_client()
    connection_kwargs = client.connection_pool.connection_kwargs
    assert connection_kwargs.get("socket_timeout") == settings.redis_socket_timeout
    assert (
        connection_kwargs.get("socket_connect_timeout")
        == settings.redis_connect_timeout
    )
