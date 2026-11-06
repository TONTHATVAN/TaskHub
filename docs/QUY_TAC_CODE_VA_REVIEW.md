# Quy tắc viết code và tự review — TaskHub

Tài liệu này rút ra từ các lỗi đã gặp khi triển khai và nhận review buổi 1–3. Áp dụng cho thay đổi mới ở mọi nhánh. Đối chiếu với [yêu cầu dự án](TASKHUB_CONG_VIEC.md) và quy trình Git trong `docs/GIT_WORKFLOW.md` trên `main`; một nhánh cũ có thể chưa chứa các bản sửa đã merge sau đó.

## 1. Một nguồn cho thông báo và giá trị dùng chung

| Loại | Nơi đặt | Ví dụ |
|---|---|---|
| Thông báo lỗi, validation, response | `app/core/messages.py` | `INVALID_REFRESH_TOKEN_MESSAGE`, `TASK_NOT_FOUND_MESSAGE` |
| Giới hạn, mặc định và thông số cố định của ứng dụng | `app/core/constants.py` | `PASSWORD_MAX_BYTES`, `LIMIT_DEFAULT`, `JWT_ALGORITHM` |
| Giá trị có tập hợp hữu hạn | `Enum`/`StrEnum` ở lớp phù hợp | `TokenType.ACCESS`, `TokenType.REFRESH` |
| Bí mật hoặc giá trị thay đổi theo môi trường | `app/infrastructure/settings.py` và biến môi trường | `JWT_SECRET_KEY`, `DATABASE_URL` |

- Trước khi viết một chuỗi lỗi hoặc con số, tìm nơi nó đã được dùng bằng `rg`. Nếu là cùng một quy tắc nghiệp vụ, dùng lại cùng tên. Không tạo nhiều bản sao của `72`, `200`, `1/20/100`, `"HS256"`, `"taskhub"` hoặc `"Invalid refresh token"` ở các lớp khác nhau.
- Tách `messages.py` và `constants.py` theo mục đích; không gom mọi chuỗi vào một file khổng lồ. Giá trị chỉ xuất hiện một lần và tự giải thích, như `status.HTTP_204_NO_CONTENT`, không cần biến thành hằng số.
- Schema request, service, model và repository phải dùng cùng giới hạn khi cùng bảo vệ một dữ liệu. Nếu thực sự thay đổi kích thước cột DB, tạo migration mới; không sửa migration đã áp dụng chỉ để đổi một literal trong code.
- Test kiểm tra giá trị phản hồi cụ thể được phép ghi literal làm kỳ vọng độc lập. Cấu hình dùng để tạo token thử nghiệm nên lấy cùng hằng số JWT khi mục đích test là kiểm tra hành vi token.

## 2. Exception và hợp đồng HTTP

- Lỗi nghiệp vụ/repository dùng exception có nghĩa (`NotFoundError`, `TaskNotFoundError`, `InvalidTokenError`...), không dùng `LookupError` hay `ValueError` chung để báo không tìm thấy bản ghi. `ValueError` vẫn phù hợp trong Pydantic validator để tạo phản hồi 422 cho dữ liệu đầu vào sai.
- Exception mang thông báo của chính nó. Handler chung lấy `exc.message` hoặc cấu hình của exception; không đoán thông báo bằng `isinstance` rồi mặc định mọi lỗi 404 thành “Task not found”.
- Với 401, dùng `UnauthorizedException` chung và giữ `WWW-Authenticate: Bearer`; refresh/logout dùng cùng loại lỗi và thông báo chuẩn. Không lặp `raise HTTPException(..., detail="...")` ở nhiều endpoint.
- Dùng hằng `fastapi.status` cho mã HTTP trong code (`status.HTTP_401_UNAUTHORIZED`, `status.HTTP_204_NO_CONTENT`); giữ body lỗi và mã HTTP nhất quán giữa các endpoint cùng loại.
- Khai báo các response lỗi quan trọng trong OpenAPI, đặc biệt 404 của GET/PATCH/DELETE Task và POST Task khi Project không tồn tại. Test cả schema OpenAPI lẫn status/body/header thực tế.

## 3. PATCH và validation phải phân biệt từng trường hợp

- Dùng `model_dump(exclude_unset=True)` để phân biệt trường không gửi với trường gửi `null`. `title`, `status`, `priority` không nhận `null`; `description` có thể nhận `null` để xóa nội dung. Test rằng PATCH bị từ chối không làm đổi dữ liệu cũ.
- Chuẩn hóa chuỗi trước khi kiểm tra độ dài. Title chỉ có khoảng trắng phải trả 422; kiểm tra ranh giới 200 và 201 ký tự sau trim. Email phải được chuẩn hóa nhất quán ở đăng ký, đăng nhập và cập nhật hồ sơ.
- Bcrypt giới hạn **72 byte UTF-8**, không phải 72 ký tự. Kiểm tra giới hạn ở register, login và đổi mật khẩu; test cả chuỗi ASCII và Unicode vượt giới hạn.
- Dùng `Annotated[int, Query(...)]` cho ràng buộc `page`/`limit`, còn mặc định lấy từ `app/core/constants.py`. Test mặc định, biên hợp lệ và đầu vào ngoài phạm vi.

## 4. Database: cập nhật và xóa an toàn khi có request đồng thời

- Không làm `get()` rồi `delete()` chỉ để xác định có bản ghi: hai bước có thể bị chen bởi request khác, còn `session.get()` có thể trả dữ liệu từ identity map. Dùng `DELETE ... WHERE ... RETURNING` và dựa vào số dòng trả về.
- Không làm `get()` rồi `merge()` để kiểm tra sự tồn tại trước khi save. Dùng `UPDATE ... WHERE khóa_chính ... RETURNING`; nếu không có dòng nào, báo lỗi không tìm thấy theo domain. Với khóa chính ghép, kiểm tra đủ các thành phần.
- PATCH Task chỉ `UPDATE` các field có trong `changes`. Không lấy bản Task cũ rồi ghi lại cả `title`, `description`, `status`, `priority`: hai PATCH song song sửa hai field khác nhau sẽ làm mất một thay đổi.
- Test trường hợp một bản ghi bị xóa sau khi đọc nhưng trước khi save, và trường hợp save từ bản Task cũ khi Task vẫn tồn tại. Kiểm tra cả dữ liệu cuối trong PostgreSQL, không chỉ mã HTTP.
- Import ở đầu module; không đặt `import asyncio` trong nhánh `else` của `migrations/env.py`.

## 5. Giảm lặp và giữ ranh giới các lớp

- Logic decode và consume refresh token của refresh/logout nằm trong một helper ở service. Router chỉ chuyển request/response và ánh xạ lỗi; không lặp nghiệp vụ ở endpoint.
- API schema không phải domain entity. Repository giao tiếp với entity/model theo interface đã định; service không truy cập trực tiếp SQLAlchemy session.
- Khi một giá trị hữu hạn như loại token xuất hiện ở nhiều file, dùng enum thay cho các chuỗi `"access"`/`"refresh"`. Khi thêm một trường hay enum mới, tìm mọi nơi tạo, đọc, validate và test nó.
- Chỉ tách helper khi các đoạn thật sự có cùng ý nghĩa; tránh tạo hàm chỉ bọc một dòng mà không giảm lặp hoặc làm rõ hành vi.

## 6. Kiểm tra trước khi gửi review

1. Đọc lại diff theo từng lớp: request schema → router → service → repository → DB; kiểm tra tên, thông báo lỗi, default và giới hạn có thống nhất không.
2. Viết test cho luồng thành công, đầu vào sai, không tìm thấy, token hết hạn/đã dùng và các ranh giới. Test phân trang theo hợp đồng sắp xếp; không giả định đồng hồ luôn tăng giữa các lần tạo bản ghi.
3. Chạy Ruff format, Ruff check, mypy và pytest. Khi PostgreSQL sẵn sàng, chạy migration và test với `TASKHUB_RUN_DB_TESTS=1`; ghi rõ test nào bị skip nếu không có DB.
4. Kiểm tra `git status`, `git diff --check` và chỉ stage file thuộc phạm vi. Không sửa commit/migration đã công bố để che lỗi mới; dùng commit sửa tiếp theo khi phù hợp.
5. Kiểm tra `git branch -vv` sau khi đổi tên nhánh trên GitHub. Đổi tên remote không tự cập nhật upstream local; cần `git fetch --prune origin` và đặt lại upstream. Kiểm tra format ngay trước khi push theo `docs/GIT_WORKFLOW.md`.
6. Đặt tên nhánh theo chức năng (`feat/user-profile`, `feat/database-repositories`) thay vì theo số buổi. Commit theo mẫu `<type>: <mô tả kết quả bằng tiếng Việt>`. Với nhánh đã có PR/commit trên GitHub, tránh viết lại lịch sử chỉ để đổi thông điệp; dùng commit tiếp theo cho bản sửa mới.

Lệnh kiểm tra nhanh tại thư mục dự án:

```powershell
.\.venv\Scripts\ruff.exe format --check app tests migrations
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\mypy.exe app tests migrations
.\.venv\Scripts\python.exe -m pytest -q
git diff --check
```
