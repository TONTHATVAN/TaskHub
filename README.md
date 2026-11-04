# TaskHub
TaskHub — Hệ thống quản lý công việc (Task Management API)

## Môi trường phát triển

- Python 3.12; các thư viện Python được ghi trong [`requirements.txt`](requirements.txt).
- PostgreSQL 16 và Redis 7 chạy bằng [`compose.yaml`](compose.yaml). Bản Compose hiện chuẩn bị DB và Redis; ứng dụng chạy trực tiếp trên máy phát triển.
- Cấu hình mẫu nằm trong [`.env.example`](.env.example). File `.env` cục bộ chứa mật khẩu DB và không được đưa lên Git.

Trong PowerShell, tại thư mục project:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db redis
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Nếu tạo `.env` từ file mẫu, hãy thay `POSTGRES_PASSWORD` và mật khẩu tương ứng trong `DATABASE_URL` trước khi khởi động DB.

PostgreSQL dùng cổng `localhost:5433` vì cổng `5432` trên máy đang được sử dụng. Redis dùng `localhost:6379`. Kiểm tra bằng `docker compose ps`; dừng dịch vụ bằng `docker compose down`.

Yêu cầu thực tập được tổng hợp trong [`docs/TASKHUB_CONG_VIEC.md`](docs/TASKHUB_CONG_VIEC.md).

Quy trình nhánh, Pull Request và định dạng mã nguồn: [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md).

## Buổi 1 — Core Setup & Architecture

Mã ứng dụng nằm trong `app/`:

```text
app/
├── api/              Router, request/response schemas, dependencies
├── application/      TaskService và các thao tác nghiệp vụ
├── domain/           Task, enum và giao diện repository
├── infrastructure/   SQLAlchemy models, session và repositories
└── main.py           App factory
migrations/           Alembic migration
tests/                Kiểm tra API và cấu trúc database
```

Khởi động API từ thư mục project:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Mở `http://127.0.0.1:8000/docs` để thử API. Endpoint kiểm tra ứng dụng là `GET /health`. CRUD mẫu gồm:

| Phương thức | Đường dẫn | Mục đích |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/tasks` | Tạo task |
| GET | `/api/v1/projects/{project_id}/tasks` | Liệt kê task trong project |
| GET | `/api/v1/tasks/{task_id}` | Xem task |
| PATCH | `/api/v1/tasks/{task_id}` | Cập nhật task |
| DELETE | `/api/v1/tasks/{task_id}` | Xóa task |

`project_id` và `task_id` là UUID.

## Buổi 2 — Database và migration

Ứng dụng dùng SQLAlchemy 2.x async với PostgreSQL. Migration đầu tiên tạo các bảng `users`, `workspaces`, `workspace_members`, `projects`, `tasks`, `labels`, `task_labels` và `comments`, cùng khóa ngoại và chỉ mục. Chạy migration sau khi PostgreSQL sẵn sàng:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Task được lưu trong database và tồn tại qua các lần khởi động ứng dụng. `POST /api/v1/projects/{project_id}/tasks` chỉ chấp nhận project đã tồn tại và trả về 404 nếu không tìm thấy. `GET /api/v1/projects/{project_id}/tasks` hỗ trợ `page` từ 1 và `limit` từ 1 đến 100, mặc định là 20. Các API tạo user, workspace và project sẽ được triển khai cùng xác thực và phân quyền ở các buổi tiếp theo; hiện tại cần tạo các bản ghi này trong database để thử API Task. Redis chưa được tích hợp vào ứng dụng.

`BaseRepository[T]` cung cấp thêm, lấy, liệt kê có phân trang, cập nhật và xóa model. `SqlTaskRepository` chuyển giữa model SQLAlchemy và entity Task trong domain. Mỗi request sử dụng một `AsyncSession`; giao dịch được commit khi xử lý thành công và rollback nếu có lỗi.

Kiểm tra migration ở chế độ không cần kết nối database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

Kiểm tra mã:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\mypy.exe app
```

Khi PostgreSQL đã chạy và migration đã được áp dụng, chạy bài kiểm tra tích hợp:

```powershell
$env:TASKHUB_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_database_integration.py
Remove-Item Env:TASKHUB_RUN_DB_TESTS
```

Bài kiểm tra tạo dữ liệu riêng và dọn dữ liệu đó khi kết thúc.

## Buổi 3 — Phần đầu: đăng ký tài khoản

`POST /api/v1/auth/register` nhận `email`, `full_name` và `password`. Email được chuẩn hóa về chữ thường; mật khẩu được băm bằng bcrypt trước khi lưu và không xuất hiện trong response. Endpoint trả 409 khi email đã tồn tại, 422 khi dữ liệu không hợp lệ. Mật khẩu cần ít nhất 8 ký tự và tối đa 72 byte UTF-8.

Phần đăng nhập, JWT access/refresh token và đăng xuất sẽ được triển khai ở các phần tiếp theo của Buổi 3.
