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

## Buổi 6 — Comment

`POST /api/v1/tasks/{task_id}/comments` thêm Comment; `GET /api/v1/tasks/{task_id}/comments` xem danh sách có phân trang; `DELETE /api/v1/tasks/{task_id}/comments/{comment_id}` xóa Comment. Thành viên có quyền ghi mới được thêm Comment; tác giả, chủ Workspace hoặc `ADMIN` được xóa. `VIEWER` chỉ được xem. Thao tác ghi vào Project đã archive trả 409.

## Buổi 7 — Redis Caching cho Task

Danh sách Task tại `GET /api/v1/projects/{project_id}/tasks` được cache bằng Redis theo `project_id`, các tham số lọc (`status`, `priority`, `assignee_id`) và phân trang (`page`, `limit`) với thời gian sống mặc định 300 giây (`TASK_CACHE_TTL_SECONDS`).

Khi có bất kỳ thay đổi nào tác động đến dữ liệu Task trong Project (`POST` tạo Task, `PATCH` cập nhật Task, `DELETE` xóa Task, hoặc gỡ người giao việc khi xóa thành viên khỏi Workspace), toàn bộ cache liên quan của Project đó sẽ tự động được xóa để đảm bảo tính nhất quán dữ liệu. Trong trường hợp Redis tạm thời gặp sự cố mất kết nối, hệ thống tự động fallback về truy vấn trực tiếp cơ sở dữ liệu mà không làm gián đoạn API của người dùng.

## Buổi 7 — Background Task thông báo email khi giao Task

Khi tạo Task có người thực hiện (`assignee_id`) hoặc khi cập nhật thay đổi người thực hiện sang thành viên khác, hệ thống kích hoạt một tác vụ chạy nền (`fastapi.BackgroundTasks`) để gửi email thông báo cho thành viên được giao việc qua SMTP (`aiosmtplib`). Thao tác gửi email chạy ngầm sau khi phản hồi HTTP đã được gửi về client, giúp API phản hồi tức thì mà không bị trễ bởi kết nối mạng tới máy chủ mail.

## Buổi 8 — Docker Compose, Refactor & Hoàn thiện dự án

Buổi cuối cùng hoàn thiện toàn bộ hệ thống và đóng gói triển khai:
- **Dockerfile multi-stage build**: Tách biệt rõ 2 giai đoạn: `builder` biên dịch các thư viện Python trong virtual environment và `runner` tối giản chạy trên nền `python:3.12-slim`, chạy dưới tài khoản non-root (`taskhub`) để đảm bảo an toàn bảo mật.
- **Tự động áp dụng Migration khi khởi động**: Container app tự động chạy `alembic upgrade head` trước khi khởi động Uvicorn server, đảm bảo database luôn ở phiên bản schema mới nhất.
- **Docker Compose hoàn chỉnh (`compose.yaml`)**: Quản lý đồng bộ 4 service:
  1. `db`: PostgreSQL 16 có volume lưu trữ và healthcheck `pg_isready`.
  2. `redis`: Redis 7 có volume lưu trữ và healthcheck `redis-cli ping`.
  3. `mailpit`: Máy chủ SMTP giả lập nội bộ (cổng 1025) kèm giao diện web trực quan (cổng 8025) để xem email gửi nền.
  4. `app`: FastAPI backend, phụ thuộc vào `db` và `redis` ở trạng thái healthy, kết nối nội bộ qua mạng docker và tự kiểm tra sức khỏe tại endpoint `/health`.
- **Rà soát chất lượng mã nguồn toàn diện**: Ruff format và lint pass 100%, Mypy 0 error trên toàn bộ 90+ files mã nguồn, loại bỏ mã trùng lặp, tối ưu hóa các luồng xử lý và đảm bảo nguyên tắc DRY.

---

## Hướng dẫn triển khai với Docker Compose

Chỉ cần một lệnh duy nhất để khởi động toàn bộ stack hệ thống (FastAPI App, PostgreSQL, Redis và Mailpit):

```powershell
# 1. Chuẩn bị file .env nếu chưa có
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 2. Khởi chạy toàn bộ hệ thống trong nền
docker compose up --build -d
# hoặc trên máy dùng docker-compose v1/v2:
docker-compose up --build -d

# 3. Theo dõi log khởi động và migration của app
docker compose logs -f app

# 4. Kiểm tra trạng thái các container
docker compose ps
```

Sau khi các container ở trạng thái `healthy` hoặc `running`:
- **API Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Hộp thư Mailpit (xem email thông báo)**: [http://localhost:8025](http://localhost:8025)

Dừng hệ thống:
```powershell
docker compose down
```

Dừng và xóa toàn bộ dữ liệu volumes:
```powershell
docker compose down -v
```

---

## Bảng cấu hình biến môi trường (`.env`)

| Tên biến | Kiểu / Giá trị mặc định | Mô tả |
|---|---|---|
| `POSTGRES_USER` | `taskhub` | Tên người dùng cơ sở dữ liệu PostgreSQL |
| `POSTGRES_PASSWORD` | *(Bắt buộc thay đổi)* | Mật khẩu cơ sở dữ liệu PostgreSQL |
| `POSTGRES_DB` | `taskhub` | Tên database TaskHub |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Connection string async SQLAlchemy cho PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | URL kết nối Redis cache |
| `TASK_CACHE_TTL_SECONDS` | `300` | Thời gian sống (TTL) của cache danh sách Task (giây) |
| `REDIS_SOCKET_TIMEOUT` | `1.0` | Timeout đọc/ghi socket Redis (giây) |
| `REDIS_CONNECT_TIMEOUT` | `1.0` | Timeout kết nối ban đầu tới Redis (giây) |
| `JWT_SECRET_KEY` | *(Tối thiểu 32 ký tự)* | Khóa bí mật dùng để ký và giải mã JWT token |
| `JWT_ACCESS_MINUTES` | `15` | Thời gian hiệu lực của Access Token (phút) |
| `JWT_REFRESH_DAYS` | `7` | Thời gian hiệu lực của Refresh Token (ngày) |
| `SMTP_HOST` | `localhost` / `mailpit` | Địa chỉ máy chủ SMTP gửi mail |
| `SMTP_PORT` | `1025` | Cổng dịch vụ SMTP |
| `SMTP_FROM` | `noreply@taskhub.com` | Địa chỉ email người gửi |
| `EMAIL_NOTIFICATIONS_ENABLED`| `true` | Bật/tắt tính năng gửi email chạy nền |

---

## Tổng hợp danh mục API Endpoints

### 1. Xác thực & Tài khoản (`/api/v1/auth`)
- `POST /api/v1/auth/register`: Đăng ký tài khoản mới (mật khẩu băm bcrypt).
- `POST /api/v1/auth/login`: Đăng nhập, nhận access token và refresh token.
- `POST /api/v1/auth/refresh`: Đổi refresh token còn hạn lấy cặp token mới.
- `POST /api/v1/auth/logout`: Thu hồi refresh token hiện tại.

### 2. Hồ sơ người dùng (`/api/v1/users`)
- `GET /api/v1/users/me`: Xem thông tin hồ sơ của tài khoản đang đăng nhập.
- `PATCH /api/v1/users/me`: Cập nhật email và họ tên.
- `POST /api/v1/users/me/change-password`: Đổi mật khẩu tài khoản.

### 3. Workspace (`/api/v1/workspaces`)
- `POST /api/v1/workspaces`: Tạo Workspace mới (người tạo tự động là OWNER).
- `GET /api/v1/workspaces/{workspace_id}`: Xem chi tiết Workspace.
- `PATCH /api/v1/workspaces/{workspace_id}`: Đổi tên Workspace (chỉ OWNER/ADMIN).
- `DELETE /api/v1/workspaces/{workspace_id}`: Xóa Workspace (cascade xóa toàn bộ dữ liệu con).
- `GET /api/v1/workspaces/{workspace_id}/members`: Liệt kê thành viên (có phân trang).
- `POST /api/v1/workspaces/{workspace_id}/members`: Mời/thêm thành viên với role EDITOR/VIEWER.
- `DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`: Xóa thành viên khỏi Workspace.

### 4. Project (`/api/v1/workspaces/{id}/projects` & `/api/v1/projects`)
- `POST /api/v1/workspaces/{workspace_id}/projects`: Tạo Project trong Workspace.
- `GET /api/v1/workspaces/{workspace_id}/projects`: Liệt kê Project (phân trang).
- `GET /api/v1/projects/{project_id}`: Xem chi tiết Project.
- `PATCH /api/v1/projects/{project_id}`: Cập nhật tên/mô tả Project.
- `DELETE /api/v1/projects/{project_id}`: Xóa Project.
- `POST /api/v1/projects/{project_id}/archive`: Lưu trữ Project (chặn ghi, cho phép đọc).
- `POST /api/v1/projects/{project_id}/unarchive`: Mở lại Project đã lưu trữ.

### 5. Task & Caching (`/api/v1/projects/{id}/tasks` & `/api/v1/tasks`)
- `GET /api/v1/projects/{project_id}/tasks`: Lấy danh sách Task (hỗ trợ lọc theo `status`, `priority`, `assignee_id`, phân trang `page`/`limit`, cache bằng Redis 300s).
- `POST /api/v1/projects/{project_id}/tasks`: Tạo Task mới trong Project (xóa cache liên quan, gửi email nếu có giao việc).
- `GET /api/v1/tasks/{task_id}`: Xem chi tiết Task.
- `PATCH /api/v1/tasks/{task_id}`: Cập nhật Task (status, priority, due date, assignee; xóa cache liên quan, gửi email nếu thay đổi người nhận).
- `DELETE /api/v1/tasks/{task_id}`: Xóa Task (xóa cache liên quan).

### 6. Nhãn dán — Label (`/api/v1/projects/{id}/labels` & `/api/v1/tasks/{id}/labels`)
- `POST /api/v1/projects/{project_id}/labels`: Tạo nhãn trong Project.
- `GET /api/v1/projects/{project_id}/labels`: Xem danh sách nhãn.
- `PATCH /api/v1/projects/{project_id}/labels/{label_id}`: Sửa tên/màu nhãn.
- `DELETE /api/v1/projects/{project_id}/labels/{label_id}`: Xóa nhãn.
- `GET /api/v1/tasks/{task_id}/labels`: Xem các nhãn gắn trên Task.
- `POST /api/v1/tasks/{task_id}/labels/{label_id}`: Gắn nhãn vào Task.
- `DELETE /api/v1/tasks/{task_id}/labels/{label_id}`: Gỡ nhãn khỏi Task.

### 7. Bình luận — Comment (`/api/v1/tasks/{id}/comments`)
- `POST /api/v1/tasks/{task_id}/comments`: Thêm bình luận vào Task.
- `GET /api/v1/tasks/{task_id}/comments`: Xem bình luận trên Task (có phân trang).
- `DELETE /api/v1/tasks/{task_id}/comments/{comment_id}`: Xóa bình luận.

### 8. Giám sát hệ thống
- `GET /health`: Kiểm tra trạng thái hoạt động (dùng cho Docker healthcheck và load balancer).

---

## Kiểm tra chất lượng mã nguồn

Chạy các lệnh sau tại thư mục gốc của project để kiểm tra toàn bộ tiêu chuẩn mã nguồn:

```powershell
# 1. Kiểm tra và định dạng code theo chuẩn Ruff
.\.venv\Scripts\ruff.exe format --check app tests migrations
.\.venv\Scripts\ruff.exe check app tests migrations

# 2. Kiểm tra kiểu tĩnh (Static Type Checking) với Mypy
.\.venv\Scripts\mypy.exe app tests migrations

# 3. Chạy toàn bộ bộ test suite
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -m pytest -v
```
