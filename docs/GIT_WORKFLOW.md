# Quy trình Git, GitHub và chuẩn mã nguồn

Áp dụng cho mọi thay đổi trong TaskHub. `main` là nhánh tích hợp; không phát triển trực tiếp hoặc push trực tiếp lên `main`.

## 1. Tạo nhánh làm việc

Trước khi bắt đầu, đồng bộ `main` rồi tạo nhánh riêng từ `main` mới nhất:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/task-reminders
```

Tên nhánh dùng **tiếng Anh**, chữ thường và dấu gạch ngang, theo mẫu `<type>/<short-description>`. Dùng `feat/` cho tính năng, `fix/` cho sửa lỗi, `docs/` cho tài liệu, `refactor/` cho tái cấu trúc, `test/` cho kiểm thử và `chore/` cho công việc bảo trì. Ví dụ: `feat/workspace-permissions`, `fix/token-expiry`, `docs/git-workflow`.

Nếu `main` local có commit chưa được tích hợp lên GitHub, xử lý các commit đó qua nhánh và Pull Request riêng trước khi đồng bộ `main`. Không dùng `git reset --hard` hoặc force push để bỏ qua commit chưa tích hợp.

## 2. Triển khai và định dạng

- Đặt mã ứng dụng trong `app/` theo lớp `api/`, `application/`, `domain/`, `infrastructure/`; migration trong `migrations/`; bài kiểm thử trong `tests/`.
- Đặt tài liệu trong `docs/`. `README.md` ở thư mục gốc dùng để giới thiệu và hướng dẫn chạy nhanh. Không đặt `.docx`, `.txt` hoặc tài liệu ghi chú vào các thư mục mã nguồn; chuyển tài liệu cần lưu vào `docs/` với tên mô tả rõ nội dung.
- Dùng **4 dấu cách** cho mỗi mức thụt lề Python, không dùng tab. `.editorconfig` quy định thụt lề và xuống dòng; Ruff là công cụ định dạng Python thống nhất cho cả nhóm.
- Nếu dùng VS Code, cài extension **Ruff** (`charliermarsh.ruff`). Cấu hình trong `.vscode/settings.json` đặt Ruff làm formatter cho Python và tự định dạng khi lưu. Trước khi commit, chạy các lệnh sau tại thư mục project:

```powershell
.\.venv\Scripts\ruff.exe format app tests migrations
.\.venv\Scripts\ruff.exe format --check app tests migrations
.\.venv\Scripts\ruff.exe check app tests migrations
.\.venv\Scripts\python.exe -m pytest -q
```

Chỉ commit các file liên quan đến công việc của nhánh. Nếu định dạng lại nhiều file cũ, tách thay đổi đó khỏi commit triển khai tính năng để Pull Request dễ xem.

## 3. Commit và đẩy nhánh

Mỗi commit có dạng `<type>: <mô tả ngắn>`. Mô tả nêu kết quả đã thực hiện, dùng động từ cụ thể và bao quát nội dung commit; tránh các tên chung như `update` hoặc `fix code`. Ví dụ:

```text
feat: thêm phân quyền thành viên workspace
fix: xử lý refresh token hết hạn
docs: ghi quy trình Git và chuẩn định dạng
test: bổ sung kiểm thử đăng nhập
```

Kiểm tra `git status` và `git diff` trước khi commit. Sau đó đẩy **nhánh làm việc** lên GitHub:

```powershell
git add <các-file-liên-quan>
git commit -m "docs: ghi quy trình Git và chuẩn định dạng"
git push -u origin docs/git-workflow
```

Thay tên nhánh và nội dung commit cho đúng công việc thực tế. Không commit `.env`, mật khẩu, file sinh tự động hoặc tài liệu nháp.

## 4. Pull Request và cập nhật local

1. Trên GitHub, tạo Pull Request từ nhánh làm việc vào `main`.
2. Trong Pull Request, mô tả thay đổi, cách kiểm tra và lưu ý liên quan; xem lại diff, chờ kiểm tra và review theo quy định của nhóm.
3. Sau khi Pull Request được duyệt, merge trên GitHub vào `main`. Xóa nhánh remote sau merge nếu không còn dùng.
4. Chỉ sau khi merge xong mới cập nhật `main` local:

```powershell
git switch main
git pull --ff-only origin main
git branch -d docs/git-workflow
```

Nếu `git pull --ff-only` báo không thể fast forward, dừng lại và kiểm tra commit local chưa tích hợp; không ép đồng bộ hoặc ghi đè lịch sử.
