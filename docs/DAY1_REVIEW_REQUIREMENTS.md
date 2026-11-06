# Day 1 — yêu cầu hoàn thiện sau review

Tài liệu này tổng hợp các việc cần làm trong PR tiếp theo cho phần **Core Setup & CRUD Task**. Căn cứ: feedback sau [PR #2](https://github.com/TONTHATVAN/TaskHub/pull/2), đối chiếu với code trên `origin/main` ngày 05/11/2026 và [yêu cầu thực tập](TASKHUB_CONG_VIEC.md). Code sửa đang ở working tree của `feat/day-1-core`, **chưa commit hoặc push**; checklist dùng để review trước PR.

## Phạm vi đã có, cần giữ đúng

- FastAPI app, router `/api/v1`, `GET /health`, lifespan, dependency injection và các lớp `api` → `application` → `domain` → `infrastructure`.
- CRUD Task theo project; `Task` nội bộ tách khỏi schema phản hồi; service dùng repository được inject qua `self._repository`.
- `PATCH` từ chối `null` cho `title`, `status`, `priority`; `description` được phép nhận `null`. Title chỉ chứa khoảng trắng bị từ chối.
- PostgreSQL, Alembic và API tests hiện có. Không mở rộng sang tính năng phân quyền, label hoặc filter chưa thuộc PR này.

## Các việc còn phải sửa

### 1. Phân trang: `Annotated` và một nguồn giá trị mặc định

- [ ] Trong `app/api/v1/tasks.py`, khai báo `page` và `limit` bằng `Annotated[int, Query(...)]`, tách giá trị mặc định ra khỏi `Query`: ví dụ `page: Annotated[int, Query(ge=...)] = DEFAULT_PAGE`.
- [ ] Đặt giá trị dùng chung ở `app/core/constants.py`: trang mặc định **1**, giới hạn mặc định **20**, trang tối thiểu **1**, giới hạn tối thiểu **1**, giới hạn tối đa **100**. Đặt tên hằng số rõ nghĩa.
- [ ] Dùng cùng hằng số ở router, `TaskService`, `TaskRepository` protocol, repository SQL/in-memory và `BaseRepository` nơi đang lặp `1`, `20`, `100`. Giữ hành vi API hiện có.
- [ ] Test giá trị mặc định, ranh giới hợp lệ và trường hợp `page=0`, `limit=0`, `limit=101` trả 422; kiểm tra phân trang vẫn đúng khi truyền `page`/`limit` cụ thể.

### 2. Thông báo validation cho `null`

- [ ] Chuyển chuỗi `"This field cannot be null"` ra `app/core/messages.py`; validator trong `TaskUpdate` dùng hằng số này.
- [ ] Giữ phân biệt **không gửi field** và **gửi `null` tường minh**: `exclude_unset=True` vẫn áp dụng cho PATCH, nhưng `title`, `status`, `priority` gửi `null` phải trả 422; `description: null` vẫn hợp lệ.
- [ ] Test PATCH bị từ chối không ghi đè dữ liệu; GET và list Task sau đó vẫn trả 200 với dữ liệu cũ.

### 3. Exception mang thông báo của chính nó

- [ ] Sửa `NotFoundError` trong `app/domain/exceptions.py` để exception có `message`; `TaskNotFoundError` và `ProjectNotFoundError` nhận đúng thông báo từ `app/core/messages.py`.
- [ ] Handler trong `app/main.py` chỉ trả `{"detail": exc.message}` với HTTP 404. Bỏ nhánh `isinstance` chọn Task/Project, để loại `NotFoundError` mới sau này không bị trả nhầm `"Task not found"`.
- [ ] Test GET/PATCH/DELETE Task không tồn tại và POST vào project không tồn tại: mã 404 và message đúng. Có test cho một loại `NotFoundError` mới hoặc giả lập để chứng minh handler không mặc định thành lỗi Task.

### 4. Đồng bộ giới hạn title giữa schema và database

- [ ] Chuyển `TASK_TITLE_MIN_LENGTH = 1` và `TASK_TITLE_MAX_LENGTH = 200` từ `app/api/v1/task_constants.py` lên `app/core/constants.py`.
- [ ] `TaskCreate` và `TaskUpdate` tiếp tục dùng cùng kiểu/constraint title; `TaskModel.title` trong `app/infrastructure/models.py` dùng `String(TASK_TITLE_MAX_LENGTH)` thay cho `String(200)`.
- [ ] Kiểm tra ranh giới title sau trim: rỗng → 422, 200 ký tự → hợp lệ, 201 ký tự → 422. Giữ `ConfigDict(str_strip_whitespace=True)` cho request schema.
- [ ] Vì giới hạn vẫn là 200, không sửa migration `0001_initial` đã áp dụng và không tạo migration mới chỉ để thay literal trong model. Nếu thay đổi kích thước cột thật, tạo migration mới.

### 5. Tách message khỏi constant số

- [ ] Chuyển `TASK_NOT_FOUND_MESSAGE` và `PROJECT_NOT_FOUND_MESSAGE` từ `app/api/v1/task_constants.py` sang `app/core/messages.py`, cùng message validation ở mục 2.
- [ ] `app/core/constants.py` chỉ chứa các giá trị quy tắc như độ dài title và phân trang; không đặt message phản hồi trong file này. Xóa file `task_constants.py` khi không còn nơi sử dụng.

### 6. Khai báo 404 trong OpenAPI

- [ ] Thêm `responses={404: ...}` cho GET, PATCH, DELETE `/api/v1/tasks/{task_id}`; nên khai báo cả POST `/api/v1/projects/{project_id}/tasks` vì project không tồn tại cũng trả 404.
- [ ] Mô tả response 404 thống nhất với dữ liệu thực tế `{"detail": "..."}`; tránh lặp cấu hình bằng một schema hoặc response definition dùng chung nếu phù hợp.
- [ ] Test `app.openapi()` có response 404 cho từng endpoint trên và test runtime vẫn trả đúng body.

## Điều kiện hoàn thành PR

- [ ] Diff chỉ chứa phần sửa feedback Day 1 và điểm liên quan trực tiếp ở model/repository; không sửa lại lịch sử commit hoặc migration cũ khi schema database không đổi.
- [ ] `ruff format --check app tests migrations`, `ruff check app tests migrations`, `mypy app tests migrations` đều đạt.
- [ ] `pytest -q` đạt; khi PostgreSQL trong Docker sẵn sàng, chạy migration rồi kiểm thử với `TASKHUB_RUN_DB_TESTS=1` để bao gồm bài test database.
- [ ] Đẩy nhánh sửa Day 1 lên GitHub, mở PR vào `main`, tự xem lại diff và chỉ đồng bộ `main` local sau khi PR được merge.

## Ghi nhận ngoài phạm vi Day 1

- API Task hiện chưa có xác thực và phân quyền theo project/workspace. Đây là rủi ro cần xử lý ở phần authorization/RBAC của các buổi tiếp theo, không tự thêm vào PR sửa feedback Day 1.
- Repo chưa có CI bắt buộc Ruff, mypy và pytest trên PR. Cần bổ sung workflow CI riêng để kiểm tra tự động trên GitHub.
- Test suite hiện còn cảnh báo deprecation từ `starlette.testclient`/`httpx`; theo dõi khi cập nhật dependencies. Tránh đổi dependency chỉ để xóa cảnh báo trong PR Day 1.
