# TramTue Chatbot AI Backend - Deployment Guide

## Hướng dẫn Deploy lên Render.com

### 1. Chuẩn bị GitHub Repository
- Repository đã được khởi tạo và commit code
- Cần push code lên GitHub repository: `https://github.com/nozomisasaki6892/backend-chatbot-tramtue.git`
- Nếu gặp lỗi 403, cần cấu hình GitHub authentication

### 2. Cấu hình Supabase Database
1. Truy cập Supabase Dashboard
2. Mở SQL Editor
3. Copy nội dung từ file `deploy_to_supabase.sql` và chạy
4. Verify các bảng đã được tạo thành công

### 3. Deploy lên Render.com
1. Truy cập https://render.com
2. Tạo new Web Service
3. Connect GitHub repository: `backend-chatbot-tramtue`
4. Cấu hình:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Environment: Python 3.11

### 4. Environment Variables trên Render
Cần thêm các environment variables sau:
```
GEMINI_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
CORS_ORIGINS=*
DEFAULT_MODEL=gemini-1.5-flash
RAG_ENABLED=true
SYSTEM_PROMPT_PATH=prompts/system_tramtue.txt
POLICY_PATH=config/policy.tramtue.yml
```

### 5. Kiểm tra Deployment
- Health check: `https://your-app.onrender.com/health`
- API docs: `https://your-app.onrender.com/docs`

## Files quan trọng
- `render.yaml`: Cấu hình deployment cho Render
- `requirements.txt`: Dependencies Python
- `deploy_to_supabase.sql`: Database schema
- `.env.example`: Template cho environment variables