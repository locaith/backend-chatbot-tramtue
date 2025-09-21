Bạn là Senior Python Backend Engineer. Hãy đọc toàn bộ repo hiện tại và xây dựng – kiểm thử – đóng gói – deploy một backend AI Agent theo các yêu cầu chi tiết sau. Tuyệt đối sử dụng Python 3.11.x để còn deploy lên render.com, FastAPI, Pydantic v2, asyncio, httpx. Không viết ví dụ, chỉ build sản phẩm hoàn chỉnh để nhiều client dùng song song.

1) Kiến trúc & Công nghệ

FastAPI async, Pydantic v2 (BaseModel) cho mọi inbound/outbound schema.

HTTP client: httpx.AsyncClient (timeout, retries, connection pooling).

Queue nội bộ nhẹ cho timers/follow-up (async background task).

Logging: structlog hoặc logging + JSON formatter, mức INFO/ERROR, có correlation-id cho mỗi request.

CORS: Allow all origins (Access-Control-Allow-Origin: *, methods GET/POST/OPTIONS, headers Content-Type/Authorization). Sau deploy, origin list có thể thu hẹp bằng ENV.

Tối ưu đồng thời: cấu hình server uvicorn workers & keep-alive; mọi I/O gọi ngoài (Gemini/Serper/Supabase) đều async.

2) Cấu hình & Secrets

Đọc ENV (không dùng file .env trong runtime):

GEMINI_API_KEY, SERPER_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.

MODEL_FLASH=gemini-2.5-flash, MODEL_PRO=gemini-2.5-pro.

Đường dẫn cấu hình/prompt: POLICY_FILE, SYSTEM_PROMPT_FILE, DISCOVERY_PROMPT_FILE, CSKH_PROMPT_FILE, SALES_PROMPT_FILE, HANDOFF_PROMPT_FILE, FOLLOWUP_PROMPT_FILE, RAG_CONFIG_FILE.

Kiểm tra sự tồn tại các file prompt/policy ngay khi khởi động; cache nội dung vào bộ nhớ.

3) Policy & Prompts (nạp từ file)

Nạp policy YAML từ config/policy.tramtue.yml, dùng làm guardrails in/out, routing rule, follow-up/handoff matrix, RAG-first rule.

Nạp system prompt tổng từ prompts/system_tramtue.txt.

Nạp agent prompts:

Discovery: prompts/agents/discovery.txt.

CSKH: prompts/agents/cskh.txt.

Sales: prompts/agents/sales.txt.

Handoff: prompts/agents/handoff.txt.

Followup: prompts/agents/followup.txt.

Khi thay đổi file, hỗ trợ hot-reload soft (endpoint /admin/reload yêu cầu header token) để nạp lại policy/prompts mà không restart toàn bộ.

4) Database & Migrations (Supabase Postgres + pgvector)

Tạo migrations tạo các bảng: users, conversations, messages, memories, documents, doc_chunks, doc_embeddings(vector), timers, handoffs, policies, metrics.

Dao lớp hoá: mỗi bảng có repository async; transaction cho các thao tác nhiều bước (ghi message + timers).

Index: ivfflat trên doc_embeddings(embedding), index thời gian cho timers(run_at).

5) RAG Pipeline

Endpoint quản trị POST /rag/ingest: đọc config/rag.ingest.config.json, crawl/copy nguồn, clean HTML → text, chunk theo config (size/overlap), embed, upsert vào documents/doc_chunks/doc_embeddings. Xử lý idempotent (hash nội dung tránh nhân bản).

Endpoint POST /rag/search: nhận {q, topK?} trả top chunks + metadata, phục vụ debug.

RAG-first: khi xử lý chat, nếu policy yêu cầu trích dẫn (giá, chính sách, quy trình, thành phần) thì bắt buộc lấy RAG context; nếu RAG trống, fallback sang Serper (mục 7).

6) Memory Engine (Cá nhân hóa)

Short-term: nạp tối đa N tin gần nhất (config), tự tóm tắt hội thoại nếu vượt ngưỡng token.

Long-term: key-value theo contract đã thống nhất (purpose, scent_preference, budget_band, sensitivity, xưng hô, preferred_formality, response_length_pref, …).

Discovery Agent: nếu user mới/chưa có memory đủ, chuyển Discovery để hỏi 3–5 lượt và ghi memory; extraction JSON theo schema đã khai báo, có confidence và weight.

Chính sách update: nếu confidence < 0.6 lưu với weight thấp, gắn cờ cần xác nhận; xung đột chọn weight cao hơn hoặc latest-wins.

7) Serper.dev Fallback

Khi RAG không đủ cho intent factual bắt buộc (ví dụ hỏi chung nhưng ngoài tài liệu), gọi Serper search + quick summarize (tối đa 3 nguồn uy tín). Kết quả được đưa về Orchestrator để quyết định có chèn vào prompt làm Supplemental Context hay không. Tất cả đều async, timeout rõ ràng.

8) Orchestrator & Multi-Agent

Orchestrator đọc policy để định tuyến tác vụ:

NEW_USER hoặc intent mơ hồ → Discovery Agent (đọc discovery.txt) để thu thập purpose/scent/budget/sensitivity/xưng hô; sau mỗi lượt lưu signals vào memories.

KNOWN_USER:

Intent “chính sách/FAQ” → CSKH Agent (đọc cskh.txt) + RAG-first + trích nguồn.

Intent “mua hàng/đề xuất” → Sales Agent (đọc sales.txt) + mapping theo memory (purpose, scent, budget).

RỦI RO/HỖ TRỢ NGAY: Handoff Agent (đọc handoff.txt) tạo record handoffs và trả lời mượt mà cho người dùng trong lúc đợi người thật.

FOLLOW-UP: Followup Agent (đọc followup.txt) khi timers đến hạn; tôn trọng followup_optin.

Routing model:

Gemini 2.5-Pro cho input dài, cần suy luận, cần trích dẫn; Gemini 2.5-Flash cho FAQ ngắn, định dạng, phản hồi tốc độ.

Cho phép forceModel từ request; mặc định heuristic theo policy.

Compose prompt: System tổng + Agent prompt tương ứng + [USER MEMORY] + [RAG CONTEXT] + format 4 phần + checklist (theo system tổng).

Safety: áp guardrails input (regex/PII) trước khi gọi model và guardrails output (length, disclaimer, PII-redact, handoff matrix) sau khi gọi model, dựa trên policy YAML.

9) Tính “như người thật” (Human-like Timing & Split)

Tính thời gian gõ ước lượng theo độ dài reply: 300 ký tự/phút; nếu >600 ký tự, chia 2–3 phần theo cấu trúc: (1) Đồng cảm + Ý 1, (2) Ý 2 + Ý 3, (3) 2 CTA + handoff/disclaimer nếu có.

Trả về mảng parts {text, delay_ms}; nếu người dùng gõ tiếp khi đang gửi phần 2/3, hủy các phần còn lại và rút gọn câu trả lời tiếp theo.

Giữ nhịp chat tự nhiên; tránh spam nhiều tin quá nhanh.

10) Endpoints (async, typed, rate-limited)

GET /health → 200 JSON {status:"ok"}

POST /chat → nhận body theo schema request; triển khai đầy đủ pipeline: guardrails(in) → memory → RAG → routing → compose → Gemini → guardrails(out) → split parts → persist → timers → trả về schema response (parts + meta).

POST /rag/ingest → chạy ingest theo config; log số chunk mới/cập nhật; idempotent.

POST /rag/search → công cụ debug; trả list chunks + score + metadata.

POST /timers/run → worker chạy scheduled follow-up; gọi Followup Agent để tạo nội dung rồi gửi qua cùng /chat pipeline (flag internal).

POST /admin/reload → reload policy/prompts từ file (yêu cầu header token).

Tất cả endpoints async, có rate-limit cơ bản (per IP/per user) để bảo vệ tài nguyên.

11) Handoff & CSKH người thật

Khi handoff trigger khớp policy, tạo record handoffs với reason, đặt conversations.state=handoff, trả lời người dùng bằng Handoff Agent.

Chuẩn bị webhook nội bộ (stub) để hệ CSKH nhận thông báo; để trống secret, chỉ mô tả interface.

12) Telemetry & Eval

Log: thời gian, model, token dùng (nếu API trả), usedRAG, usedSerper, route agent, violations.

/eval/run (chế độ nội bộ): chạy bộ eval_set_tramtue.jsonl, đo passrate theo eval/kpi.targets.json; in báo cáo gọn.

13) Bảo mật & Tuân thủ

Không ghi PII thô vào log.

Không bao giờ echo secrets.

Cảnh báo nếu ENV thiếu hoặc file prompt/policy không tải được → từ chối khởi động (fail-fast).

14) Đóng gói & Deploy

Sinh Dockerfile, chạy uvicorn, health path /health.

Tạo render.yaml tương thích (đọc ENV từ Render), CORS mở.

README: hướng dẫn thiết lập ENV, migrate Supabase, chạy cục bộ, ingest RAG, test /chat.

15) Mặc định nội dung thương hiệu

Trả lời theo giọng Trầm Tuệ (trang trọng, ấm áp), format 4 phần, 2 CTA, ưu tiên RAG-first khi có dữ liệu sản phẩm/chính sách, và tự nhiên như chủ thương hiệu nắm policy “thuộc máu”.

Chỉ cần mở rộng ingest sản phẩm (tên, mô tả, mùi, giá, chính sách, ảnh) → RAG sẽ “học” thêm và trả lời phù hợp.

Checklist hoàn thành bắt buộc

Async FastAPI + Pydantic v2, CORS mở, concurrency tốt.

Tất cả endpoints hoạt động đúng hợp đồng I/O; /health 200 OK.

Đọc được tất cả file prompts/policy nêu trên; routing agents chạy đúng.

Guardrails in/out theo YAML, handoff/follow-up đúng ma trận.

RAG ingest/search ok; Serper fallback chạy khi RAG thiếu.

Memory cá nhân hóa lưu/đọc chuẩn; Discovery Agent kích hoạt đúng state.

Human-like timing: split và delay hợp lý, hủy phần còn lại khi user gửi thêm.

Docker + render.yaml sẵn sàng; log sạch; README đầy đủ.