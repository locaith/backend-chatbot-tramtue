# Hướng dẫn Push Code lên GitHub

## Vấn đề hiện tại
- Git đã được cấu hình với tài khoản `nozomisasaki6892@gmail.com`
- Code đã được commit local (36 files)
- Repository đã tạo: https://github.com/nozomisasaki6892/backend-chatbot-tramtue.git
- Nhưng gặp lỗi 403 khi push

## Giải pháp 1: Sử dụng GitHub Desktop
1. Mở GitHub Desktop
2. File > Add Local Repository
3. Chọn thư mục: `G:\TramTue-ChatbotAI-BackendV2`
4. Publish repository hoặc Push origin

## Giải pháp 2: Tạo lại Personal Access Token
1. Vào GitHub Settings > Developer settings > Personal access tokens
2. Xóa token cũ
3. Tạo token mới với quyền:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
4. Copy token mới

## Giải pháp 3: Sử dụng SSH Key
1. Tạo SSH key:
   ```bash
   ssh-keygen -t ed25519 -C "nozomisasaki6892@gmail.com"
   ```
2. Thêm SSH key vào GitHub Settings > SSH and GPG keys
3. Đổi remote URL:
   ```bash
   git remote set-url origin git@github.com:nozomisasaki6892/backend-chatbot-tramtue.git
   ```

## Giải pháp 4: Upload thủ công
1. Tạo file ZIP từ thư mục project
2. Vào GitHub repository
3. Upload files manually

## Files quan trọng cần push:
- `app/` - Source code chính
- `requirements.txt` - Dependencies
- `render.yaml` - Cấu hình deployment
- `deploy_to_supabase.sql` - Database schema
- `.env.example` - Template environment variables
- `README_DEPLOYMENT.md` - Hướng dẫn deployment

## Sau khi push thành công:
1. Deploy database schema lên Supabase
2. Cấu hình deployment trên Render.com