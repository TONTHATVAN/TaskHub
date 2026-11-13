# Quy tắc phạm vi Pull Request và cập nhật nhánh

Áp dụng khi tạo nhánh, mở PR và xử lý góp ý review trong TaskHub. Bài học từ PR Buổi 5: nhánh chứa cả sửa xác thực, Workspace và Project khiến diff lớn, khó review; merge `main` vào nhánh còn tạo thêm merge commit.

## 1. Chia PR theo thay đổi có thể review độc lập

- Trước khi code, xác định một mục tiêu cho mỗi PR. Ví dụ: sửa auth và xử lý lỗi; Workspace và thành viên; Project và archive là ba phạm vi khác nhau. Nếu phần sau cần phần trước, đặt base của PR sau vào nhánh trước; đổi base về `main` khi PR trước đã merge.
- Code, test, migration và tài liệu trực tiếp phục vụ cùng một mục tiêu được giữ cùng PR. Sửa lỗi không liên quan hoặc chỉ định dạng hàng loạt phải tách riêng.
- Ưu tiên PR khoảng dưới 20 file theo góp ý review. Đây là tín hiệu để kiểm tra lại phạm vi, không phải lý do tách một thay đổi cần tính nguyên tử thành nhiều PR thiếu test.
- Trước khi mở PR, kiểm tra diff thực tế so với base: `git diff --stat <base>...HEAD`, `git diff --name-only <base>...HEAD` và `git log --oneline <base>..HEAD`. Mô tả PR nêu thay đổi, cách kiểm tra và phần phụ thuộc.

## 2. Cập nhật nhánh từ base

- Với nhánh **chưa push**, lưu hoặc commit công việc dở, fetch base mới rồi rebase để lịch sử tuyến tính:

```powershell
git status --short
git fetch origin
git rebase origin/main
```

- Nếu PR phụ thuộc nhánh khác chưa merge, rebase lên nhánh đó thay cho `main`. Kiểm tra lại base và diff sau rebase; giải quyết conflict theo hành vi mong muốn, rồi chạy test.
- Không dùng `git pull` mặc định hoặc `git merge main` lặp lại chỉ để đồng bộ nhánh tính năng, vì sẽ đưa merge commit và thay đổi từ nhánh khác vào lịch sử PR.

## 3. Nhánh đã push hoặc đã có PR

- Rebase hoặc `reset` sẽ đổi lịch sử nhánh đã công bố; cherry-pick sang nhánh khác tạo commit mới với SHA khác. Nếu nhánh đã có PR hoặc được nhánh khác dùng làm base, trước tiên xác định các PR/nhánh phụ thuộc và thống nhất cách cập nhật với reviewer/người cùng làm.
- Khi chỉ sửa lỗi review trong cùng phạm vi, ưu tiên commit bổ sung trên nhánh hiện tại. Không viết lại lịch sử chỉ để xóa merge commit cũ hoặc sửa tên commit.
- Nếu cần tách PR đã mở: giữ nguyên nhánh cũ để đối chiếu; lập các nhánh mới từ đúng base, chuyển từng nhóm thay đổi bằng commit chọn lọc hoặc stage từng hunk; kiểm tra từng diff và test trước khi tạo PR thay thế. Chỉ đóng PR cũ sau khi PR thay thế đã đầy đủ và reviewer đã có đường dẫn mới.
- Chỉ khi việc viết lại lịch sử đã được thống nhất, tạo nhánh dự phòng và dùng `git push --force-with-lease` cho đúng nhánh. Không dùng `--force` và không force push `main`. Cập nhật lại các nhánh/PR phụ thuộc sau đó.

## 4. Tự kiểm tra trước khi gửi review

1. `git status --short`: không lẫn file nháp, tài liệu review nội bộ hoặc thay đổi của việc khác.
2. `git diff --stat <base>...HEAD` và `git diff --name-only <base>...HEAD`: phạm vi và số file hợp lý.
3. `git log --oneline <base>..HEAD`: không có merge commit hoặc commit không liên quan mới phát sinh.
4. Chạy format, lint, type check và test phù hợp; sau khi rebase hoặc giải quyết conflict phải chạy lại.
5. Kiểm tra base/head trên GitHub và mô tả PR trước khi yêu cầu review.
