# Rà soát TaskHub sau khi đồng bộ `main` vào Buổi 5

Ngày rà soát: 11/11/2026. Nhánh: `feat/workspace-crud`. Đã merge `main` tại `562656c` vào nhánh bằng merge commit `b5781c7`, sau đó khôi phục phần Buổi 5 đang làm từ stash. Các thay đổi sau merge trong tài liệu này vẫn ở working tree, chưa commit hoặc push.

## Phạm vi kiểm tra

- Đối chiếu [yêu cầu dự án](TASKHUB_CONG_VIEC.md), [quy tắc code và review](QUY_TAC_CODE_VA_REVIEW.md), các góp ý Buổi 1–4 và luồng Workspace/Project của Buổi 5.
- Đi theo đường đi của request: schema → dependency/kiểm quyền → service → repository → PostgreSQL → phản hồi HTTP/OpenAPI.
- Kiểm tra đăng ký, đăng nhập, refresh/logout, hồ sơ và đổi mật khẩu; quyền theo từng Workspace/Project/Task; CRUD thành viên, Project, Task; validation, phân trang và lỗi đồng thời.

## Kết quả và sửa đổi

| Nhóm | Vấn đề đã kiểm tra và cách xử lý |
|---|---|
| Đồng bộ nhánh | Giải quyết xung đột auth, dependency, Task và test khi merge `main` và áp lại stash. Giữ cả bản sửa PR #9 và chức năng Buổi 5. Không còn dấu conflict. |
| Phân quyền | Task tiếp tục dùng `Readable/WritableProject` và `Readable/WritableTask` dependency từ `main`; dependency trả Task đã tải để handler không query lại. Project và hai endpoint tạo/liệt kê Project trong Workspace cũng chuyển kiểm quyền khỏi thân handler sang dependency. Service Workspace vẫn tự kiểm quyền cho các thao tác quản lý Workspace/thành viên. |
| Project archive | Ghi Task/Project vào Project đã archive trả 409 với thông báo `Project is archived`; đọc và xóa/archive Project theo quyền hiện có. Truy vấn quyền lấy khóa hàng Project cho thao tác ghi để tránh archive chạy song song với ghi Task. |
| Phiên đăng nhập | Đổi mật khẩu dùng cập nhật có điều kiện theo hash cũ, tránh hai request cùng xác thực bằng mật khẩu cũ rồi ghi đè nhau; hash mới và thu hồi mọi refresh token nằm trong cùng transaction. Login và refresh khóa hàng User để tuần tự với đổi mật khẩu, nên login bằng mật khẩu cũ không thể tạo phiên sau khi đổi. Refresh token đã dùng lại trả 401 và thu hồi các refresh token còn hiệu lực; nhánh lỗi này trả response để transaction thu hồi được commit. Access/refresh được phân biệt bằng `TokenType`, claim JWT được xác thực, và 401 giữ header `WWW-Authenticate: Bearer`. |
| Repository và cạnh tranh | Task/Project/member INSERT bắt lỗi khóa ngoại sau savepoint; PATCH chỉ cập nhật các trường được gửi; DELETE/UPDATE dùng điều kiện và `RETURNING`. `BaseRepository.get/delete` kiểm tra đủ thành phần khóa chính ghép, tránh DELETE bằng một UUID vô tình xóa nhiều membership. Xóa thành viên sau khi Workspace biến mất trả lỗi Workspace không tồn tại thay vì báo nhầm thành viên không tồn tại. |
| Validation | Email/tên/mật khẩu dùng giới hạn chung; bcrypt được giới hạn theo **72 byte UTF-8** ở register, login và đổi mật khẩu. `null` ở trường bắt buộc trả 422. Task và Profile từ chối field không hỗ trợ thay vì âm thầm bỏ qua; ví dụ `role` trong PATCH Profile hoặc `assignee_id` trong Task hiện trả 422. |
| Thông báo và tài liệu API | Mã lỗi dùng `AppException` và một handler; thông báo nằm trong `app/core/messages.py`, giới hạn/giá trị chung trong `app/core/constants.py`, trạng thái hữu hạn dùng Enum. Bổ sung response 400/401/409 của Auth/Profile vào OpenAPI; mô tả dùng chung với phản hồi thực tế, gồm header của 401. |

## Bằng chứng kiểm tra

- `TASKHUB_RUN_DB_TESTS=1`, PostgreSQL 16 trong Docker: **41 test đạt**, gồm kiểm thử đăng nhập song song với đổi mật khẩu. Có một cảnh báo deprecation từ Starlette/TestClient, không làm test thất bại.
- `ruff format --check .`: **75 file đã đúng định dạng**.
- `ruff check .`: **đạt**.
- `mypy app`: **57 file, không có lỗi**.
- `alembic check`: **No new upgrade operations detected**.
- `git diff --check`: **đạt**.

## Giới hạn và việc theo dõi

- Access token đã phát vẫn có hiệu lực đến lúc hết hạn sau đổi mật khẩu hoặc khi phát hiện refresh token bị dùng lại. Cơ chế hiện tại thu hồi refresh token; muốn vô hiệu hóa access token ngay cần thêm version/denylist và kiểm tra trong `get_current_user`.
- Quyền thành viên được kiểm tra trước khi ghi Project/Task; nếu quyền bị thu hồi đúng lúc request ghi đang chạy, hai thao tác chưa được khóa theo cùng bản ghi membership. Cần khóa bản ghi quyền hoặc thiết kế kiểm quyền và ghi trong một câu lệnh nếu yêu cầu thu hồi quyền có hiệu lực tức thì với request đồng thời.
- Nhánh này chưa triển khai thao tác assign Task, due date, Label, Comment và cache Redis. Request chứa field Task chưa hỗ trợ hiện nhận 422 để không tạo cảm giác cập nhật thành công.
- Trước khi commit Buổi 5, chỉ stage code, test và tài liệu liên quan; tránh đưa lại phần của các PR đã merge vào mô tả PR như thay đổi mới.
