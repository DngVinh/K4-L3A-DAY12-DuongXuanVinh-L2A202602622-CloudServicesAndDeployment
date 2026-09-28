# Phiếu Phản Ánh — K4 Level 3A, Ngày 12

> **Bài làm cá nhân.** Trả lời bằng lời của chính bạn, dựa trên những gì bạn
> quan sát được khi chạy code — không sao chép đáp án của người khác.
>
> Cách trả lời: thay dòng mẫu ở mỗi câu bằng câu trả lời.
> `grade.py` đếm số câu đã trả lời (15 điểm cho 10 câu).
>
> Họ và tên: Duong Xuan Vinh  Mã học viên: L2A202602622

---

### Câu 1 — Fail fast (CP1)

Trong `Settings`, `agent_api_key` không có giá trị mặc định nên app chết ngay
khi khởi động nếu thiếu biến môi trường. Hãy mô tả một tình huống cụ thể mà
việc "chết sớm" này cứu bạn, so với việc để mặc định `"changeme"`.

> Nếu tôi quên đặt `AGENT_API_KEY` trên Railway, `Settings` báo lỗi ngay lúc
> khởi động và bản deploy không nhận traffic. Tôi sẽ thấy vấn đề ở log deploy
> để sửa biến môi trường. Nếu code tự dùng `"changeme"`, app vẫn lên bình thường;
> người biết khóa mẫu có thể gọi `/ask` và làm phát sinh chi phí trước khi tôi
> phát hiện.

---

### Câu 2 — Log cho máy đọc (CP1)

Chạy service và gọi `/ask` vài lần. Dán một dòng log JSON bạn thu được, rồi
nêu **hai** việc bạn làm được với dòng log đó mà `print("đã trả lời xong")`
không làm được.

> Đây là một dòng tôi thu được khi chạy test gọi `/ask` với mock LLM:
>
> ```json
> {"event": "ask_completed", "level": "info", "timestamp": "2026-09-28T09:53:57.373422+00:00", "user_id": "sv-test", "tokens_in": 3, "tokens_out": 37, "cost_usd": 2.265e-05}
> ```
>
> Tôi có thể lọc các dòng `event=ask_completed` để đếm số lượt hỏi theo user,
> và cộng `cost_usd` để theo dõi chi phí hoặc cảnh báo khi tăng đột biến.
> Dòng `print("đã trả lời xong")` không có user, thời điểm hay chi phí để làm
> hai việc đó.

---

### Câu 3 — Kích thước image (CP2)

Build cả hai phiên bản và ghi lại số đo thật:

```bash
docker build -f <Dockerfile-1-stage> -t agent:single .
docker build -t agent:multi .
docker images | grep agent
```

| Bản | Dung lượng |
|-----|-----------|
| 1 stage (Dockerfile gốc ở commit `1bf8ea5`) | 1.73 GB (`day12-agent:single-stage-measured`, `docker images`) |
| Multi-stage | 271 MB (`day12-agent:multi-stage-measured`, `docker images`) |

Giải thích: phần dung lượng chênh lệch đó là những gì?

> Tôi đã build thật cả hai bản từ cùng repo. Bản một stage dùng lại Dockerfile
> gốc ở commit `1bf8ea5` và cho `1.73 GB`; bản multi-stage hiện tại cho
> `271 MB`, nên nhỏ hơn khoảng `1.46 GB` (hơn sáu lần theo số hiển thị của
> `docker images`). Tôi cũng kiểm tra lại bằng `docker image inspect`: lần lượt
> là `446637790` và `63889657` bytes cho hai tag.
>
> Chênh lệch chính là base `python:3.11` đầy đủ so với `python:3.11-slim`.
> Dockerfile một stage còn đưa toàn bộ build context vào image bằng `COPY . .`
> và chạy `pip install` ngay trong runtime layer (bản gốc không có
> `--no-cache-dir`), nên image cuối giữ cả nhiều thành phần không cần lúc chạy.
> Bản multi-stage cài dependency ở builder rồi chỉ copy `/install`, `app`,
> `utils` và `frontend` sang runtime slim; builder không nằm trong image cuối.

---

### Câu 4 — Thứ tự lệnh trong Dockerfile (CP2)

Sửa một ký tự trong `app/main.py` rồi build lại. Với Dockerfile của bạn, những
layer nào được dùng lại từ cache, layer nào phải chạy lại? Nếu bạn đặt
`COPY . .` lên trước `RUN pip install` thì kết quả khác thế nào?

> Tôi đã chạy build baseline bằng tag `day12-agent:cache-before`, sau đó đổi
> đúng một ký tự trong `title` của `app/main.py` (`Day 12 Agent` thành
> `Day 12 Agent!`) và build lại bằng tag `day12-agent:cache-one-char`. Log
> `--progress=plain` cho thấy:
>
> - `COPY requirements.txt`, `RUN pip install`, `WORKDIR` của builder và
>   `COPY --from=builder /install` đều hiện `CACHED`.
> - `COPY app ./app` chạy lại (`DONE`); vì Docker cache theo chuỗi lệnh, các
>   layer phía sau là `COPY utils`, `COPY frontend` và `RUN useradd` cũng chạy
>   lại dù nội dung riêng của chúng không đổi.
>
> Tôi đã hoàn nguyên ký tự thử nghiệm sau khi build. Nếu đặt `COPY . .` trước
> `RUN pip install`, thay đổi nhỏ ở `app/main.py` sẽ làm layer copy toàn bộ
> source đổi, từ đó buộc `pip install` và mọi layer sau nó chạy lại. Đó là lý
> do phải copy `requirements.txt` và cài dependency trước khi copy source.

---

### Câu 5 — Vì sao không chạy bằng root (CP2)

Container mặc định chạy bằng root. Mô tả chuỗi sự kiện dẫn từ "một lỗ hổng
trong code Python của bạn" tới "kẻ tấn công có quyền cao trên máy host", và
lệnh `USER` cắt đứt chuỗi đó ở chỗ nào.

> Nếu app có lỗ hổng cho phép chạy lệnh trong container, kẻ tấn công sẽ có
> quyền của tiến trình app. Chạy mặc định bằng root khiến họ có quyền cao
> trong container; nếu container còn được cấp mount hoặc đặc quyền quá rộng,
> thiệt hại có thể lan sang host. `USER appuser` chuyển tiến trình sang UID
> thường trước khi chạy uvicorn, nên lỗ hổng ứng dụng không tự cấp quyền root.
> Lệnh này giảm rủi ro chứ không thay thế việc giới hạn mount và đặc quyền.

---

### Câu 6 — Cửa sổ trượt (CP3)

Rate limit của bạn dùng sliding window 60 giây. Nếu thay bằng cách đếm theo
phút đồng hồ (reset lúc giây 00), một người dùng có thể gửi tối đa bao nhiêu
request trong 2 giây liên tiếp khi hạn mức là 10/phút? Giải thích cách đạt được
con số đó.

> Tối đa là 20 request: gửi 10 request ở cuối phút trước, ví dụ
> 10:00:59, rồi 10 request ngay đầu phút sau, ví dụ 10:01:00. Mỗi phút đồng
> hồ vẫn chỉ có 10 request, nhưng cả 20 nằm trong khoảng gần 2 giây.
> Sliding window 60 giây nhìn vào 60 giây gần nhất nên sẽ chặn nhóm thứ hai.

---

### Câu 7 — Rate limit và cost guard (CP3)

Hai cơ chế này khác nhau ở điểm nào? Cho một tình huống mà rate limit cho qua
nhưng cost guard phải chặn, và một tình huống ngược lại.

> Rate limit kiểm soát tốc độ gọi, còn cost guard kiểm soát tổng tiền trong
> tháng. Một user chỉ gửi 1 request trong phút nhưng đã tiêu gần hết 10 USD
> và câu hỏi mới làm vượt ngân sách: rate limit cho qua, cost guard trả 402.
> Ngược lại, user còn nhiều ngân sách nhưng gửi request thứ 11 trong vòng
> 60 giây: cost guard vẫn cho qua về tiền, rate limit trả 429.

---

### Câu 8 — /health khác /ready (CP4)

Nếu gộp hai endpoint làm một và cho nó kiểm tra Redis, chuyện gì xảy ra với cụm
3 container khi Redis mất kết nối 30 giây? Trả lời theo đúng thứ tự sự kiện.

> Redis mất kết nối; nếu `/health` cũng ping Redis thì cả ba container cùng
> trả 503. Orchestrator hiểu nhầm cả ba tiến trình đã hỏng và bắt đầu restart
> chúng. Trong lúc khởi động lại, không instance nào nhận request; nếu Redis
> vẫn chưa lên, các container tiếp tục bị coi là unhealthy. Khi Redis hồi
> phục sau 30 giây, cụm còn phải chờ container khởi động và qua health check
> lại. Tách `/health` khỏi Redis giữ process sống; `/ready` mới tạm rút
> instance khỏi traffic khi dependency chưa sẵn sàng.

---

### Câu 9 — Stateless (CP4)

Chạy `docker compose up --scale agent=3` rồi gọi `/ask` nhiều lần với cùng một
`X-User-Id`. Quan sát `history_length` trong response. Nếu lịch sử được lưu
trong một dict Python thay vì Redis, bạn sẽ thấy con số đó thay đổi thế nào?

> Tôi đã chạy một project Compose cô lập với cùng image hiện tại và Redis dùng
> chung, dùng lệnh tương đương `docker compose up -d --scale agent=3`. Vì
> `docker-compose.yml` chính publish cố định `8000:8000` (Compose sẽ đụng
> cổng host khi scale), bản thí nghiệm tạm thời bỏ publish host và chỉ dùng
> `expose: 8000`, rồi gọi trực tiếp vào từng replica trong network Compose.
> Cả ba agent và Redis đều ở trạng thái `healthy`. Với cùng
> `X-User-Id: scale-user`, kết quả thực tế là:
>
> | Replica | Câu hỏi | `history_length` |
> |---------|---------|------------------|
> | `day12-scale-agent-1` | `scale request 1` | `0` |
> | `day12-scale-agent-2` | `scale request 2` | `2` |
> | `day12-scale-agent-3` | `scale request 3` | `4` |
>
> Như vậy mỗi instance đọc được hai message của các lượt trước từ Redis,
> dù request đi vào container khác. Nếu dùng dict Python riêng, mỗi process
> bắt đầu với lịch sử rỗng: lần đầu đi vào từng replica đều có thể là `0`,
> còn chỉ những request quay lại đúng replica đó mới tăng thành `2`, `4`, …
> Load balancer khi đó làm số đo nhảy lùi/lặp và người dùng thấy lịch sử
> không nhất quán.

---

### Câu 10 — Deploy thật (CP5)

Ghi lại **một** lỗi bạn gặp khi deploy lên cloud (build fail, health check
timeout, sai REDIS_URL, app không đọc `$PORT`...): thông báo lỗi là gì, bạn
tìm ra nguyên nhân bằng cách nào, và sửa ra sao?

> Một lỗi trong quá trình làm bản deploy là DeepSeek đôi khi trả nội dung
> rỗng. Code báo `DeepSeek returned an empty answer`, và lịch sử commit có
> bản sửa `Harden DeepSeek deployment response handling`; dashboard Railway
> cũng hiển thị lần deploy `Retry empty DeepSeek responses`. Tôi kiểm tra
> đường xử lý response trong `app/deepseek.py`: trước đây một lần trả rỗng
> khiến request thất bại. Bản sửa thử lại một lần rồi chỉ báo lỗi nếu cả hai
> lần vẫn không có câu trả lời. Tôi không coi retry là cách xử lý mọi lỗi:
> timeout hoặc HTTP lỗi vẫn được báo riêng để kiểm tra log.
