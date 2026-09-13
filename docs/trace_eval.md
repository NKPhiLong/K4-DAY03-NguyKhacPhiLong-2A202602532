# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Nguy Khắc Phi Long  
> **Mã Sinh Viên / Mã Học viên:** 2A202602532  
> **Chủ đề Lựa chọn:** Gợi ý 1.1 — *Trợ lý Học vụ & Tra cứu VinUni* (tra cứu hồ sơ học vụ theo mã sinh viên + đặt lịch tư vấn với Cố vấn học tập). 2 Tools qua MCP: `academic_query` (tra cứu) và `schedule_appointment` (hành động).  

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 4 / 5 | Yêu cầu điển hình như *"tra cứu cố vấn của tôi rồi đặt lịch với cố vấn đó"* (TC04) bắt buộc chia thành ≥ 2 bước nối tiếp: Bước 1 gọi `academic_query` lấy trường `advisor`, Bước 2 mới đủ tham số để gọi `schedule_appointment`. Không thể trả lời trong 1 lượt sinh text đơn thuần. Chưa chấm 5 vì chuỗi suy luận tối đa chỉ 2–3 bước, không cần lập kế hoạch phức tạp. |
| **2. Tool Interaction** | 5 / 5 | Toàn bộ dữ liệu cốt lõi (GPA, lớp, email, trạng thái, cố vấn, lịch hẹn) nằm **ngoài** tri thức của LLM, phải truy xuất từ CSDL học vụ qua MCP Server. Chatbot Cấp 2 không có tool sẽ chỉ có thể từ chối hoặc bịa đặt (Hallucination). Ngoài tra cứu, hệ thống còn cần tool **hành động** (ghi booking) — đúng tinh thần 1 tool đọc + 1 tool ghi. |
| **3. Dynamic Decision** | 4 / 5 | Bước tiếp theo phụ thuộc trực tiếp vào Observation: nếu `academic_query` trả `SUCCESS` → lấy `advisor` để đặt lịch; nếu trả `NOT_FOUND` (TC05 – SV9999999) → phải dừng, không đặt lịch và phản hồi lịch sự thay vì bịa dữ liệu. Agent cũng phải tự quyết định *không* gọi tool với câu hỏi chung (TC01). Chưa 5/5 vì không gian rẽ nhánh còn nhỏ (2 tool, 2 trạng thái). |
| **4. Long Horizon Goal** | 3 / 5 | Agent phải giữ mục tiêu gốc ("đặt lịch cho tôi") xuyên suốt nhiều lượt gọi LLM và bảo toàn ngữ cảnh (mã SV, thời gian, cố vấn vừa tra được) qua lịch sử hội thoại/Observation. Tuy nhiên mỗi phiên kết thúc trong 1 yêu cầu (≤ 5 vòng lặp), chưa có memory dài hạn hay theo dõi mục tiêu qua nhiều phiên như Agent Cấp 4. |
| **TỔNG ĐIỂM AGENTIC FIT** | **16 / 20** | *Tổng điểm 16/20 > 12/20 ⇒ Bài toán **rất phù hợp** triển khai Agentic System (ReAct Agent Cấp 3), thay vì LLM Chatbot Cấp 2 chỉ sinh text.* |

**Kết luận Agentic Fit:** Trợ lý Học vụ VinUni cần *Tool use* (bắt buộc), *Multi-step* và *Dynamic Decision* ở mức cao, nên việc nâng cấp từ Chatbot lên ReAct Agent + MCP Server là hợp lý; chi phí token tăng thêm được bù lại bằng khả năng trả lời đúng dữ liệu thực và thực hiện được hành động (đặt lịch).

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

**Môi trường nghiệm thu thực tế:** `LLM_PROVIDER=gemini` · Provider `GeminiProvider` · Model `gemini-3.5-flash` (Google Gemini API thật, free-tier) · MCP Server `vinuni-academic-mcp-server` v2026.1.0 · Lệnh: `python src/app.py --all`.
Mỗi sự kiện trong `docs/trace_waterfall.json` đều được gắn `provider`/`model` để chứng minh không dùng Mock; `latency_ms` là thời gian gọi LLM, `mcp_latency_ms` là thời gian MCP Server thực thi tool.

**Bảng tổng hợp 5 Test Cases (từ `docs/trace_waterfall.json`):**

| Test Case | Số sự kiện | Chuỗi ReAct (Action → … → Final) | Tổng LLM latency (ms) |
| :---: | :---: | :--- | ---: |
| TC01 | 1 | Final Answer | 6,673 |
| TC02 | 2 | `academic_query` → Final Answer | 4,641 |
| TC03 | 2 | `schedule_appointment` → Final Answer | 4,194 |
| TC04 | 3 | `academic_query` → `schedule_appointment` → Final Answer | 5,980 |
| TC05 | 2 | `academic_query` → Final Answer | 4,186 |

*Ghi chú:* Free-tier Gemini giới hạn 5 request/phút; `GeminiProvider` có cơ chế tự chờ theo `retryDelay` và gọi lại (không fallback Mock). Ở lần chạy nghiệm thu cuối này không phát sinh lần chờ nào (0 retry), latency ~2s/bước là latency thật của LLM.

**Trích xuất tiêu biểu 1 — TC04 (ReAct đa bước: Thought → Action `academic_query` → Observation → Thought → Action `schedule_appointment` → Observation → Final Answer):**

```json
[
  {
    "test_case": "TC04",
    "step": 1,
    "query": "Mình là sinh viên SV2026002 nhưng không nhớ tên cố vấn học tập của mình. Hãy tra cứu xem cố vấn của mình là ai rồi đặt lịch hẹn tư vấn với cố vấn đó vào 09:00 ngày 20/09/2026.",
    "provider": "GeminiProvider",
    "model": "gemini-3.5-flash",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'academic_query' với tham số: {\"student_id\": \"SV2026002\"}",
    "tool_name": "academic_query",
    "arguments": {
      "student_id": "SV2026002"
    },
    "mcp_request": {
      "jsonrpc": "2.0",
      "id": 3,
      "method": "tools/call",
      "server": "vinuni-academic-mcp-server"
    },
    "observation": {
      "status": "SUCCESS",
      "student_id": "SV2026002",
      "data": {
        "full_name": "Trần Thị Bình",
        "class": "AI-K4",
        "gpa": 3.6,
        "email": "binh.tt@vinuni.edu.vn",
        "status": "Đang học",
        "advisor": "TS. Lê Thị B"
      }
    },
    "latency_ms": 1931.9,
    "mcp_latency_ms": 0.09
  },
  {
    "test_case": "TC04",
    "step": 2,
    "query": "Mình là sinh viên SV2026002 nhưng không nhớ tên cố vấn học tập của mình. Hãy tra cứu xem cố vấn của mình là ai rồi đặt lịch hẹn tư vấn với cố vấn đó vào 09:00 ngày 20/09/2026.",
    "provider": "GeminiProvider",
    "model": "gemini-3.5-flash",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'schedule_appointment' với tham số: {\"advisor_name\": \"TS. Lê Thị B\", \"datetime_str\": \"09:00 20/09/2026\", \"student_id\": \"SV2026002\"}",
    "tool_name": "schedule_appointment",
    "arguments": {
      "advisor_name": "TS. Lê Thị B",
      "datetime_str": "09:00 20/09/2026",
      "student_id": "SV2026002"
    },
    "mcp_request": {
      "jsonrpc": "2.0",
      "id": 4,
      "method": "tools/call",
      "server": "vinuni-academic-mcp-server"
    },
    "observation": {
      "status": "SUCCESS",
      "booking_id": "BK-SV2026002-99",
      "student_id": "SV2026002",
      "datetime": "09:00 20/09/2026",
      "advisor": "TS. Lê Thị B",
      "message": "Đặt lịch thành công cho sinh viên SV2026002 với TS. Lê Thị B vào lúc 09:00 20/09/2026."
    },
    "latency_ms": 2118.84,
    "mcp_latency_ms": 0.05
  },
  {
    "test_case": "TC04",
    "step": 3,
    "query": "Mình là sinh viên SV2026002 nhưng không nhớ tên cố vấn học tập của mình. Hãy tra cứu xem cố vấn của mình là ai rồi đặt lịch hẹn tư vấn với cố vấn đó vào 09:00 ngày 20/09/2026.",
    "provider": "GeminiProvider",
    "model": "gemini-3.5-flash",
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini đã tổng hợp Observation từ MCP Server thành câu trả lời cuối cùng.",
    "output": "Chào bạn, \n\nQua tra cứu, cố vấn học tập của bạn (sinh viên Trần Thị Bình - SV2026002) là **TS. Lê Thị B**.\n\nMình đã đặt thành công lịch hẹn tư vấn cho bạn với cố vấn học tập theo thông tin sau:\n* **Cố vấn:** TS. Lê Thị B\n* **Thời gian:** 09:00 ngày 20/09/2026\n …",
    "tool_calls_used": 2,
    "latency_ms": 1928.98
  }
]
```

**Trích xuất tiêu biểu 2 — TC05 (Edge case: Observation `NOT_FOUND` → Agent không bịa dữ liệu):**

```json
[
  {
    "test_case": "TC05",
    "step": 1,
    "query": "Cho mình hỏi GPA và tên cố vấn học tập của sinh viên có mã SV9999999 là gì?",
    "provider": "GeminiProvider",
    "model": "gemini-3.5-flash",
    "action_type": "TOOL_EXECUTION",
    "thought": "Gemini quyết định gọi công cụ 'academic_query' với tham số: {\"student_id\": \"SV9999999\"}",
    "tool_name": "academic_query",
    "arguments": {
      "student_id": "SV9999999"
    },
    "mcp_request": {
      "jsonrpc": "2.0",
      "id": 5,
      "method": "tools/call",
      "server": "vinuni-academic-mcp-server"
    },
    "observation": {
      "status": "NOT_FOUND",
      "message": "Không tìm thấy dữ liệu sinh viên có mã 'SV9999999'"
    },
    "latency_ms": 1811.5,
    "mcp_latency_ms": 0.06
  },
  {
    "test_case": "TC05",
    "step": 2,
    "query": "Cho mình hỏi GPA và tên cố vấn học tập của sinh viên có mã SV9999999 là gì?",
    "provider": "GeminiProvider",
    "model": "gemini-3.5-flash",
    "action_type": "FINAL_ANSWER",
    "thought": "Gemini đã tổng hợp Observation từ MCP Server thành câu trả lời cuối cùng.",
    "output": "Rất tiếc, hệ thống không tìm thấy dữ liệu của sinh viên có mã **SV9999999**. Bạn vui lòng kiểm tra lại mã sinh viên của mình xem đã chính xác chưa nhé!",
    "tool_calls_used": 1,
    "latency_ms": 2374.07
  }
]
```

**Bổ sung — chế độ `--interactive` (file `docs/trace_interactive.json`):** câu hỏi *"Đặt lịch hẹn tư vấn cho SV2026001 vào 10:00 ngày 22/09/2026"* (không cho tên cố vấn) → Gemini tự quyết định tra cứu `academic_query` để lấy `advisor` trước, rồi mới gọi `schedule_appointment` → 3 sự kiện, kết thúc bằng Final Answer xác nhận booking.

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [x] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini/OpenAI). *(Model `gemini-3.5-flash`; 10/10 sự kiện trace đều có `provider: GeminiProvider`, 0 lần fallback Mock.)*
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases. *(TC01 trả lời trực tiếp không gọi tool; TC02, TC03, TC05 gọi 1 tool; TC04 gọi 2 tool nối tiếp.)*
- **Số lượt gọi Tool qua MCP Server chính xác:** 5 / 5 lượt. *(academic_query ×3, schedule_appointment ×2; tất cả đúng tool, đúng tham số, phản hồi JSON-RPC 2.0 hợp lệ.)*
- **Kết quả đẩy Repo nộp bài:** [ ] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

**Các thay đổi mã nguồn chính so với Starter Repo:**
| File | Thay đổi |
| :--- | :--- |
| `src/tools.py` | TODO 1.2 — JSON Schema đầy đủ cho `schedule_appointment` (3 properties + required). |
| `src/mcp_server.py` | TODO 2.1 — `call_tool()` gọi `dispatch_tool_call`, `json.loads`, đóng gói JSON-RPC 2.0 (`jsonrpc`, `id`, `server`, `method`, `tool`, `result`, `error` khi lỗi). |
| `src/app.py` | ReAct Loop thực sự: Observation được nạp lại vào `history` cho LLM suy luận vòng kế tiếp (đa bước), dừng khi Final Answer hoặc `MAX_ITERATIONS`; trace gắn `test_case`, `provider`, `model`, `mcp_request`, `mcp_latency_ms`; thêm `--baseline` so sánh Chatbot Cấp 2 vs Agent Cấp 3; `--interactive` lưu `trace_interactive.json`. |
| `src/providers.py` | `generate_with_tools(..., history=...)` cho Gemini/OpenAI/Mock; Gemini phát lại `Content` gốc (giữ `thought_signature` — bắt buộc với Gemini 3.x), tự retry khi 429 rate-limit. |
| `src/prompts.py` | Bổ sung quy tắc đa bước, xử lý NOT_FOUND và yêu cầu nêu Thought trước khi gọi tool. |
| `config/test_cases.json` | Viết TC03 (đặt lịch), TC04 (đa bước), TC05 (mã SV không tồn tại). |

---
> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
