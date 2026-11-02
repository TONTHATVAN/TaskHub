# Tổng hợp công việc thực tập — TaskHub (FastAPI)

TaskHub là **Task Management API** được xây dựng xuyên suốt module FastAPI. Sau mỗi chủ đề, học viên thực hành và tích hợp vào cùng một sample app. Nội dung dưới đây được tổng hợp từ **4 ảnh yêu cầu** bạn cung cấp.

| Nhóm | Mục | Công việc / thông số cần thực hiện | Kết quả hoặc ghi chú |
|---|---|---|---|
| Lộ trình | Buổi 1 — Core Setup & Architecture (8 giờ) | Tổ chức project theo Layered Architecture; tạo FastAPI app instance, `APIRouter`, lifespan events; xây dựng routing và request handling; áp dụng Dependency Injection; định nghĩa Pydantic v2 schemas. | Skeleton app chạy được, có CRUD endpoints cơ bản cho một resource. |
| Lộ trình | Buổi 2 — Database: SQLAlchemy 2.x & Alembic (8 giờ) | Sử dụng SQLAlchemy 2.x async; định nghĩa models và relationships; xây dựng Repository Pattern với `BaseRepository[T]`, async CRUD và pagination; tạo Alembic migrations; tích hợp DB vào FastAPI. | Models, migrations và repository CRUD hoàn chỉnh trong sample app. |
| Lộ trình | Buổi 3–7 — Business Logic & Core Features (40 giờ) | Authentication và security: password hashing (`passlib`/`bcrypt`), JWT; authorization và RBAC: `get_current_user`, kiểm soát theo role và quyền sở hữu resource; middleware và exception handling; Redis caching; API documentation; configuration với `pydantic-settings`, `BaseSettings`, fail-fast env validation và multi-environment; logging. | Hoàn chỉnh core features của sample app. Tài liệu không chia các hạng mục này thành từng ngày riêng. |
| Lộ trình | Buổi 3–7 — nội dung tùy chọn | Dockerfile multi-stage build, `docker-compose` (app + DB + Redis); Background Tasks & Queue. | Được ghi là **Optional** trong phần lộ trình. Xem yêu cầu tính năng 10 và 13 bên dưới. |
| Lộ trình | Buổi 8 — Review, Refactor & Optimization (8 giờ) | Code review toàn bộ sample app (architecture, naming, code quality); Ruff lint pass 100%, mypy không có error; loại bỏ mã trùng lặp, áp dụng DRY; performance review; hoàn thiện README (setup, env vars, `docker compose up`). | Hệ thống chạy đầy đủ và ổn định các chức năng theo luồng. |
| Tổng quan | Tên và phạm vi | **TaskHub — hệ thống quản lý công việc (Task Management API).** Domain: User, Workspace, Project, Task, Label, Comment, Notification. | Xây dựng một sample app duy nhất trong suốt module. |
| Tổng quan | Tech stack | FastAPI 0.111+; SQLAlchemy 2.x async; Alembic; Pydantic v2; Redis 7; MySQL 8 **hoặc** PostgreSQL 16; Docker. | Chọn một trong hai hệ quản trị DB được nêu. |
| DB schema | `users` | `id`, `email`, `full_name`, `hashed_password`, `role` (`ADMIN`/`MEMBER`), `is_active`, `created_at`. | Entity chính số 1. |
| DB schema | `workspaces` | `id`, `name`, `owner_id`, `created_at`. | Entity chính số 2. |
| DB schema | `workspace_members` | `workspace_id`, `user_id`, `role` (`OWNER`/`EDITOR`/`VIEWER`). | Entity chính số 3. |
| DB schema | `projects` | `id`, `workspace_id`, `name`, `description`, `status` (`ACTIVE`/`ARCHIVED`), `created_at`. | Entity chính số 4. |
| DB schema | `tasks` | `id`, `project_id`, `assignee_id`, `title`, `description`, `status` (`TODO`/`IN_PROGRESS`/`IN_REVIEW`/`DONE`), `priority` (`LOW`/`MEDIUM`/`HIGH`/`URGENT`), `due_date`, `created_by`, `created_at`. | Entity chính số 5. |
| DB schema | `labels` | `id`, `project_id`, `name`, `color`. | Entity chính số 6. |
| DB schema | `task_labels` | `task_id`, `label_id`. | Entity chính số 7; quan hệ task–label. |
| DB schema | `comments` | `id`, `task_id`, `author_id`, `content`, `created_at`. | Entity chính số 8. |
| Tính năng bắt buộc | 1. Auth | Register; Login với JWT access và refresh token; Logout bằng cách revoke refresh token. | Luồng xác thực đầy đủ. |
| Tính năng bắt buộc | 2. User | Get profile; Update profile (`PATCH`); Change password. | Quản lý hồ sơ người dùng. |
| Tính năng bắt buộc | 3. Workspace | CRUD workspace (owner only); invite member; remove member; phân quyền theo role. | Quản lý workspace và thành viên. |
| Tính năng bắt buộc | 4. Project | CRUD project trong workspace; archive project. | Quản lý project theo workspace. |
| Tính năng bắt buộc | 5. Task | CRUD task trong project; assign task cho member; chuyển status; đặt priority và due date. | Quản lý vòng đời task. |
| Tính năng bắt buộc | 6. Label | CRUD label theo project; gắn và bỏ label khỏi task. | Phân loại task bằng label. |
| Tính năng bắt buộc | 7. Comment | Thêm và xóa comment trên task. | Trao đổi trên task. |
| Tính năng bắt buộc | 8. Filtering & Pagination | Lọc task theo `status`, `priority`, `assignee`; phân trang bằng `page` và `limit`. | Danh sách task có bộ lọc và phân trang. |
| Tính năng bắt buộc | 9. Caching | Cache `GET /projects/{id}/tasks` bằng Redis; invalidate khi dữ liệu thay đổi. | Không trả dữ liệu cache cũ sau thay đổi liên quan. |
| Tính năng bắt buộc | 10. Background Task | Gửi email notification khi được assign task. | Email được xử lý ở nền. |
| Tính năng bắt buộc | 11. RBAC | Phân quyền `ADMIN`/`OWNER`/`EDITOR`/`VIEWER` theo từng resource. | Kiểm soát quyền truy cập đúng vai trò và phạm vi. |
| Tính năng bắt buộc | 12. Swagger/ReDoc | Tài liệu API đầy đủ, Bearer auth scheme và error responses. | Có thể xem và thử API qua Swagger UI/ReDoc. |
| Tính năng bắt buộc | 13. Docker Compose | Chạy toàn bộ stack app + DB + Redis. | `docker compose up` chạy được. |
| Tính năng bắt buộc | 14. Chất lượng mã | Kiểm tra Ruff và mypy. | Ruff lint pass 100%; mypy không có error. |
| API tham khảo | Auth | `POST /api/v1/auth/register`<br>`POST /api/v1/auth/login`<br>`POST /api/v1/auth/refresh`<br>`POST /api/v1/auth/logout` | 4 endpoints. |
| API tham khảo | User | `GET /api/v1/users/me`<br>`PATCH /api/v1/users/me` | 2 endpoints. |
| API tham khảo | Workspace & Project | `POST /api/v1/workspaces`<br>`GET /api/v1/workspaces/{id}`<br>`POST /api/v1/workspaces/{id}/members`<br>`DELETE /api/v1/workspaces/{id}/members/{user_id}`<br>`POST /api/v1/workspaces/{id}/projects` | 5 endpoints. |
| API tham khảo | Task, Label & Comment | `GET /api/v1/projects/{id}/tasks` (filter + pagination + cache)<br>`POST /api/v1/projects/{id}/tasks`<br>`PATCH /api/v1/tasks/{id}`<br>`DELETE /api/v1/tasks/{id}`<br>`POST /api/v1/tasks/{id}/labels/{label_id}`<br>`POST /api/v1/tasks/{id}/comments` | 6 endpoints. |
| Đánh giá | Mức hoàn thành | Hoàn thành ít nhất **85%** features bắt buộc; tối thiểu features **1–8 và 11–12**. | Đối chiếu với 14 tính năng trên. |
| Đánh giá | Vận hành API | API chạy ổn định qua Swagger UI và ReDoc. | Thử được các luồng API chính. |
| Đánh giá | Quyết định thiết kế | Nắm được các quyết định về DB schema, phân quyền và cache strategy. | Giải thích được lựa chọn và cách triển khai. |

**Lưu ý về tài liệu gốc:** Phần mở đầu ghi **8 ngày × 8 giờ = 64 giờ** và các buổi trong bảng cũng cộng thành **64 giờ**, nhưng dòng “Tổng cộng” ở ảnh thứ hai ghi **68 giờ**. Cần xác nhận lại con số này với người giao bài. Ngoài ra, Docker Compose và Background Tasks & Queue được ghi **Optional** trong lộ trình, trong khi các tính năng 10 và 13 ở phụ lục lại nằm trong danh sách **bắt buộc**; bảng trên giữ nguyên cả hai cách ghi để tiện đối chiếu.
