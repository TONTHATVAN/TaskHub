# TaskHub
TaskHub — Hệ thống quản lý công việc (Task Management API)

## Môi trường phát triển

- Python 3.12; các thư viện Python được ghi trong [`requirements.txt`](requirements.txt).
- PostgreSQL 16 và Redis 7 chạy bằng [`compose.yaml`](compose.yaml). Bản Compose hiện chuẩn bị **DB và Redis**; dịch vụ app sẽ được thêm khi có mã ứng dụng.
- Cấu hình mẫu nằm trong [`.env.example`](.env.example). File `.env` cục bộ chứa mật khẩu DB và không được đưa lên Git.

Trong PowerShell, tại thư mục project:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d db redis
```

Nếu tạo `.env` từ file mẫu, hãy thay `POSTGRES_PASSWORD` và mật khẩu tương ứng trong `DATABASE_URL` trước khi khởi động DB.

PostgreSQL dùng cổng `localhost:5433` vì cổng `5432` trên máy đang được sử dụng. Redis dùng `localhost:6379`. Kiểm tra bằng `docker compose ps`; dừng dịch vụ bằng `docker compose down`.

Yêu cầu thực tập được tổng hợp trong [`TASKHUB_CONG_VIEC.md`](TASKHUB_CONG_VIEC.md).

## Buổi 1 — Core Setup & Architecture

Mã ứng dụng nằm trong `app/`:

```text
app/
├── api/              Router, request/response schemas, dependencies
├── application/      TaskService và các thao tác nghiệp vụ
├── domain/           Task, enum và giao diện repository
├── infrastructure/   Repository lưu trong bộ nhớ
└── main.py           App factory và lifespan
tests/                Kiểm tra API Task
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

`project_id` và `task_id` là UUID. Ở buổi 1, task chỉ lưu trong bộ nhớ và bị xóa khi ứng dụng khởi động lại. Chưa có bảng project nên API chưa kiểm tra project có tồn tại hay không. PostgreSQL và Redis đã được chuẩn bị nhưng ứng dụng buổi 1 chưa sử dụng; phần tích hợp DB thuộc buổi 2.

Kiểm tra mã:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests
.\.venv\Scripts\mypy.exe app
```
