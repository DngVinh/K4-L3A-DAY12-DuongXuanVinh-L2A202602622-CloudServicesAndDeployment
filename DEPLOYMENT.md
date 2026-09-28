# Thông Tin Deploy — Checkpoint 5

> Điền file này sau khi deploy xong. `pytest tests/test_cp5.py` đọc file này
> để tìm địa chỉ service của bạn và gọi thử.
>
> **Chỉ ghi TÊN biến môi trường, tuyệt đối không dán giá trị API key vào đây.**
> Repo này công khai — dán khóa vào là mất khóa.

## Thông Tin Học Viên

| Mục | Nội dung |
|-----|----------|
| Họ và tên | Duong Xuan Vinh |
| Mã học viên | L2A202602622 |
| Repo | https://github.com/DngVinh/K4-L3A-DAY12-DuongXuanVinh-L2A202602622-CloudServicesAndDeployment |

## Service

| Mục | Nội dung |
|-----|----------|
| Public URL | https://agent-production-43eb.up.railway.app |
| Demo UI | https://agent-production-43eb.up.railway.app/ |
| Platform | Railway |
| Ngày deploy | 2026-09-28 |

## Biến Môi Trường Đã Set Trên Cloud

Ghi tên biến và **nguồn giá trị**, không ghi giá trị:

| Biến | Đã set | Ghi chú |
|------|--------|---------|
| `PORT` | ✅ | platform tự gán |
| `AGENT_API_KEY` | ✅ | đặt trong dashboard, không nằm trong repo |
| `LLM_PROVIDER` | ✅ | `deepseek` |
| `DEEPSEEK_API_KEY` | ✅ | secret trên Railway, không ghi vào repo |
| `DEEPSEEK_BASE_URL` | ✅ | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | ✅ | `deepseek-flash` |
| `REDIS_URL` | ✅ | Redis add-on managed của Railway, tham chiếu `${{Redis.REDIS_URL}}` |
| `RATE_LIMIT_PER_MINUTE` | ✅ | 10 |
| `MONTHLY_BUDGET_USD` | ✅ | 10.0 |
| `LOG_LEVEL` | ✅ | INFO |

API `/ask` hiện gọi DeepSeek trên server. Giao diện chỉ cần `AGENT_API_KEY`; không nhập
DeepSeek key vào trình duyệt.

## Lệnh Kiểm Tra

Các lệnh kiểm tra với Public URL hiện tại:

```bash
# 1. Liveness — mong đợi 200 {"status":"ok"}
curl -i https://agent-production-43eb.up.railway.app/health

# 2. Readiness — mong đợi 200 {"status":"ready"} (đã nối được Redis)
curl -i https://agent-production-43eb.up.railway.app/ready

# 3. Không có API key — mong đợi 401
curl -i -X POST https://agent-production-43eb.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'

# 4. Có API key — mong đợi 200 kèm câu trả lời
curl -i -X POST https://agent-production-43eb.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "X-User-Id: sv-test" \
  -d '{"question":"Deploy là gì?"}'

# 5. Rate limit — gọi 15 lần, những lần cuối phải trả 429
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code} " -X POST https://agent-production-43eb.up.railway.app/ask \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $AGENT_API_KEY" \
    -H "X-User-Id: sv-test" \
    -d '{"question":"test"}'
done; echo
```

## Kết Quả Chạy Thật

Dán output của các lệnh trên vào đây:

```
GET /health → 200 {"status":"ok","service":"day12-agent","version":"1.0.0"}
GET /ready → 200 {"status":"ready","redis":true}
POST /ask không có X-API-Key → 401
POST /ask có X-API-Key, X-User-Id: cp5-smoke → 200
POST /ask qua DeepSeek → 200
```

## CI/CD

Workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) chạy khi push
hoặc mở pull request vào `main`. Job `test` chạy các checkpoint offline, job
`build` build Docker image, rồi job `deploy` mới được chạy sau khi cả hai job
đều xanh và chỉ trên push vào `main`.

Để bật deploy tự động trên GitHub, tạo các giá trị sau trong **Settings →
Secrets and variables → Actions**:

- Variable `RAILWAY_DEPLOY_ENABLED`: `true` sau khi cấu hình đủ các mục dưới đây.
- Secret `RAILWAY_TOKEN`: Project token của đúng project/environment Railway.
- Variable `RAILWAY_PROJECT_ID`: Project ID của project Railway.
- Variable `RAILWAY_SERVICE_NAME`: tên service web cần deploy (không phải Redis).
- Variable `PUBLIC_URL`: `https://agent-production-43eb.up.railway.app`.

Workflow chỉ tham chiếu tên secret/variable; giá trị token không nằm trong
repo. Khi chưa bật `RAILWAY_DEPLOY_ENABLED`, job deploy được bỏ qua.
`railway up --ci` chỉ chạy sau khi test và build xanh. Bước cuối gọi
`${PUBLIC_URL}/health` với `curl --fail` để deploy lỗi cũng bị đánh dấu đỏ.

## Ảnh Chụp Màn Hình

Đặt ảnh trong thư mục `screenshots/`:

- [Ảnh dashboard Railway](screenshots/deploy.png) — service đang hoạt động và bản deploy gần nhất.
- [Ảnh `/health`](screenshots/health.png) — phản hồi JSON thực tế của public URL.

---

## Nếu Dùng Phương Án Dự Phòng

Không đăng ký được tài khoản cloud? Vẫn nộp được bài, nhưng CP5 tối đa 60% điểm:

1. Đặt `LOCAL_FALLBACK=true` trong `.env`
2. Chạy `docker compose up -d` rồi kiểm tra `docker compose ps`
3. Chụp màn hình vào `screenshots/`
4. Chạy `pytest tests/test_cp5.py -v` — bộ test sẽ tự chuyển sang kiểm tra
   `http://localhost:8000`
5. Ghi rõ lý do không deploy được vào phần dưới đây:

Deployment Railway đã hoạt động, nên không sử dụng phương án dự phòng LOCAL_FALLBACK.
