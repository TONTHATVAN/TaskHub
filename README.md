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

Nếu tạo `.env` từ file mẫu, hãy thay `POSTGRES_PASSWORD`, mật khẩu tương ứng trong `DATABASE_URL` và `JWT_SECRET_KEY` bằng một chuỗi ngẫu nhiên tối thiểu 32 ký tự trước khi khởi động ứng dụng.

PostgreSQL dùng cổng `localhost:5433` vì cổng `5432` trên máy đang được sử dụng. Redis dùng `localhost:6379`. Kiểm tra bằng `docker compose ps`; dừng dịch vụ bằng `docker compose down`.

Yêu cầu thực tập được tổng hợp trong [`docs/TASKHUB_CONG_VIEC.md`](docs/TASKHUB_CONG_VIEC.md).

Quy trình nhánh, Pull Request và định dạng mã nguồn: [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md).

## Buổi 1 — Core Setup & Architecture

Mã ứng dụng nằm trong `app/`:

```text
app/
├── api/              Router, request/response schemas, dependencies
├── application/      Nghiệp vụ Task và xác thực
├── domain/           Entity, enum và giao diện repository
├── infrastructure/   SQLAlchemy models, session và repositories
└── main.py           App factory và lifespan
migrations/           Alembic migration
tests/                Kiểm tra API, migration và database
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

Task được lưu trong database và tồn tại qua các lần khởi động ứng dụng. `POST /api/v1/projects/{project_id}/tasks` chỉ chấp nhận project đã tồn tại và trả về 404 nếu không tìm thấy. `GET /api/v1/projects/{project_id}/tasks` hỗ trợ `page` từ 1 và `limit` từ 1 đến 100, mặc định là 20. Có thể tạo Workspace và Project qua API để thử luồng Task. Redis chưa được tích hợp vào ứng dụng.

`BaseRepository[T]` cung cấp thêm, lấy, liệt kê có phân trang, cập nhật và xóa model. `SqlTaskRepository` chuyển giữa model SQLAlchemy và entity Task trong domain. Mỗi request sử dụng một `AsyncSession`; giao dịch được commit khi xử lý thành công và rollback nếu có lỗi.

Kiểm tra migration ở chế độ không cần kết nối database:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

Kiểm tra mã:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\mypy.exe app tests migrations
```

Khi PostgreSQL đã chạy và migration đã được áp dụng, chạy bài kiểm tra tích hợp:

```powershell
$env:TASKHUB_RUN_DB_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q tests/test_database_integration.py
Remove-Item Env:TASKHUB_RUN_DB_TESTS
```

Bài kiểm tra tạo dữ liệu riêng và dọn dữ liệu đó khi kết thúc.

## Buổi 3 — Xác thực

`POST /api/v1/auth/register` nhận `email`, `full_name` và `password`. Email được chuẩn hóa về chữ thường; mật khẩu được băm bằng bcrypt trước khi lưu và không xuất hiện trong response. Endpoint trả 409 khi email đã tồn tại, 422 khi dữ liệu không hợp lệ. Mật khẩu cần ít nhất 8 ký tự và tối đa 72 byte UTF-8.

Các endpoint còn lại:

| Phương thức | Đường dẫn | Mục đích |
|---|---|---|
| POST | `/api/v1/auth/login` | Nhận email và password, trả access token và refresh token |
| POST | `/api/v1/auth/refresh` | Đổi refresh token còn hiệu lực lấy cặp token mới |
| POST | `/api/v1/auth/logout` | Thu hồi refresh token |
| GET | `/api/v1/users/me` | Lấy hồ sơ bằng `Authorization: Bearer <access_token>` |

Access token có hiệu lực mặc định 15 phút; refresh token có hiệu lực 7 ngày. Mỗi refresh token chỉ dùng được một lần. Logout thu hồi refresh token, còn access token đã phát hành vẫn có hiệu lực đến khi hết hạn. Trạng thái thu hồi được lưu trong bảng `refresh_tokens`.

Sau khi cập nhật mã, chạy migration mới:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Buổi 4 — quản lý hồ sơ và phân quyền Task

Người dùng đã đăng nhập có thể cập nhật email và tên qua `PATCH /api/v1/users/me`, hoặc đổi mật khẩu qua `POST /api/v1/users/me/change-password` với `current_password` và `new_password`. Các endpoint này yêu cầu Bearer access token. Email được chuẩn hóa về chữ thường; email trùng trả 409, mật khẩu hiện tại sai trả 400. Mật khẩu mới phải có ít nhất 8 ký tự và tối đa 72 byte UTF-8. Đổi mật khẩu thành công trả 204; access token hiện có tiếp tục hiệu lực đến khi hết hạn.

Toàn bộ endpoint Task yêu cầu Bearer access token. Quyền được xác định theo Workspace chứa Project:

| Vai trò | Đọc Task | Tạo, sửa, xóa Task |
|---|---|---|
| `ADMIN` | Có | Có |
| Chủ sở hữu Workspace | Có | Có |
| Thành viên `OWNER` hoặc `EDITOR` | Có | Có |
| Thành viên `VIEWER` | Có | Không |
| Người không thuộc Workspace | Không | Không |

Thiếu hoặc sai access token trả 401; thành viên có quyền đọc nhưng không được ghi nhận 403; resource không tồn tại hoặc người ngoài Workspace truy cập nhận 404 để không lộ sự tồn tại của resource. Quyền được đọc từ database ở mỗi request, nên request bắt đầu sau khi thay đổi thành viên đã được lưu sẽ áp dụng quyền mới. Cần có Workspace, Project và thành viên trong database để thử API Task. Tài liệu yêu cầu gốc gom buổi 3–7 chung một nhóm, nên phạm vi buổi 4 ở đây được chia theo nhóm chức năng để triển khai từng phần có thể kiểm chứng.

## Buổi 5 — Workspace và Project

Người dùng đã đăng nhập tạo Workspace qua `POST /api/v1/workspaces`; họ trở thành chủ sở hữu và được thêm vào `workspace_members` với vai trò `OWNER` trong cùng giao dịch. Chủ sở hữu hoặc `ADMIN` có thể đổi tên, xóa Workspace. Thành viên `EDITOR` và `VIEWER` có thể xem Workspace; người ngoài nhận 404. `GET /api/v1/workspaces/{workspace_id}/members` phân trang và trả `items`, `total`, `page`, `limit`. Chủ sở hữu hoặc `ADMIN` thêm thành viên bằng `POST /api/v1/workspaces/{workspace_id}/members` (vai trò `EDITOR`/`VIEWER`) và xóa bằng `DELETE /api/v1/workspaces/{workspace_id}/members/{member_id}`. Không thể thêm trùng hoặc xóa chủ sở hữu.

Trong Workspace, `OWNER`/`EDITOR` và `ADMIN` được tạo Project qua `POST /api/v1/workspaces/{workspace_id}/projects`; các thành viên được xem danh sách qua `GET` (có `page`/`limit`, trả `items` và `total`). `GET`, `PATCH`, `DELETE /api/v1/projects/{project_id}` và `POST /api/v1/projects/{project_id}/archive` dùng cùng quyền theo Workspace. Có thể khôi phục Project đã archive bằng `POST /api/v1/projects/{project_id}/unarchive`; trong trạng thái archive, Project và Task vẫn đọc được nhưng thao tác ghi trả 409. Project vẫn có thể xóa. Tên Workspace và Project được trim, giới hạn 200 ký tự. API trả 401 khi thiếu token, 403 khi thành viên không đủ quyền ghi và 404 khi resource không tồn tại hoặc người ngoài Workspace truy cập. Xóa Workspace hoặc Project sẽ xóa dữ liệu con qua khóa ngoại cascade.

## Buổi 6 — Giao Task, hạn hoàn thành và lọc danh sách

Khi tạo hoặc cập nhật Task, người có quyền ghi Project có thể đặt `assignee_id` cho một thành viên còn hoạt động trong Workspace và đặt `due_date` có múi giờ. `PATCH` gửi `null` cho hai trường này sẽ xóa người được giao hoặc hạn hoàn thành. `created_by` lấy từ access token và không nhận từ request. Người được giao không hợp lệ trả 409; khi xóa một thành viên khỏi Workspace, các Task trong Workspace đang giao cho người đó được gỡ giao trong cùng giao dịch. Các thao tác ghi giữ khóa bản ghi quyền thành viên đến khi giao dịch kết thúc để tuần tự với việc thu hồi quyền. `GET /api/v1/projects/{project_id}/tasks` nhận bộ lọc `status`, `priority`, `assignee_id` trước khi phân trang bằng `page` và `limit`.

## Buổi 6 — Label

`POST/GET /api/v1/projects/{project_id}/labels` và `GET/PATCH/DELETE /api/v1/projects/{project_id}/labels/{label_id}` quản lý Label trong Project. `POST/DELETE /api/v1/tasks/{task_id}/labels/{label_id}` gắn hoặc bỏ Label khỏi Task; Label phải thuộc cùng Project. `GET /api/v1/tasks/{task_id}/labels` xem các Label đã gắn. `VIEWER` chỉ được đọc; thao tác ghi vào Project đã archive trả 409. Tên Label dài 1–100 ký tự sau trim, màu có dạng `#RRGGBB`; tên trùng trong một Project trả 409.
