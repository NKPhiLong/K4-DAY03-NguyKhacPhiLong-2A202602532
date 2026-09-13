"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPAcademicServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list, filename: str = "trace_waterfall.json"):
    """Ghi vết log Waterfall Trace Log ra file docs/<filename> (mặc định docs/trace_waterfall.json)"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, filename)
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def run_react_agent(user_query: str, provider, mcp_server: MCPAcademicServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.

    Mỗi vòng lặp: LLM (Thought) -> quyết định Final Answer hoặc Tool Call (Action)
      -> MCP Client gửi JSON-RPC tới MCP Server -> nhận Observation
      -> Observation được nạp vào history để LLM suy luận tiếp ở vòng kế tiếp.
    Vòng lặp dừng khi LLM trả lời bằng text hoặc chạm MAX_ITERATIONS.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    step = 0
    trace_logs = []
    tools_list = mcp_server.list_tools()
    # Lịch sử hội thoại ReAct (provider-agnostic) — xem chuẩn "history" trong providers.py
    history = [{"role": "user", "content": user_query}]
    tool_call_count = 0
    # Metadata nhận diện LLM thật/mock cho từng sự kiện trace (bằng chứng nghiệm thu)
    llm_meta = {"provider": provider.__class__.__name__, "model": getattr(provider, "model_name", "unknown")}

    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")

        # ===== THOUGHT: Gọi LLM với Native Tool Calling Specs + toàn bộ Observation trước đó =====
        llm_response = provider.generate_with_tools(
            user_query, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT, history=history
        )
        llm_latency_ms = round((time.time() - step_start_time) * 1000, 2)

        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")

        # ===== Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp (FINAL ANSWER) =====
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                **llm_meta,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "tool_calls_used": tool_call_count,
                "latency_ms": llm_latency_ms
            })
            break

        # ===== Trường hợp 2: LLM đề xuất gọi Tool (ACTION) =====
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {}) or {}
            tool_call_id = llm_response.get("tool_call_id") or f"call_{step}"

            print(f"🛠️ [Action Proposed]: {tool_name}({json.dumps(arguments, ensure_ascii=False)})")

            # MCP Client gửi request JSON-RPC 2.0 tới MCP Server và nhận Observation
            mcp_start_time = time.time()
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            mcp_latency_ms = round((time.time() - mcp_start_time) * 1000, 2)
            obs_data = mcp_result.get("result", {}) if isinstance(mcp_result, dict) else {}
            tool_call_count += 1

            if not obs_data:
                print("👁️ [Observation từ MCP Server]: {}")
                print("⚠️ [CHÚ Ý]: MCP Server trả về kết quả rỗng! Học viên cần hoàn thành TODO 2.1 trong 'src/mcp_server.py'.")
                obs_data = {"status": "EMPTY_RESPONSE", "message": "MCP Server trả về rỗng (chưa hoàn thành TODO 2.1)."}
            else:
                print(f"👁️ [Observation từ MCP Server]: {json.dumps(obs_data, ensure_ascii=False)}")

            trace_logs.append({
                "step": step,
                "query": user_query,
                **llm_meta,
                "action_type": "TOOL_EXECUTION",
                "thought": thought,
                "tool_name": tool_name,
                "arguments": arguments,
                "mcp_request": {
                    "jsonrpc": "2.0",
                    "id": mcp_result.get("id") if isinstance(mcp_result, dict) else None,
                    "method": "tools/call",
                    "server": mcp_result.get("server") if isinstance(mcp_result, dict) else None
                },
                "observation": obs_data,
                "latency_ms": llm_latency_ms,
                "mcp_latency_ms": mcp_latency_ms
            })

            # Nạp Action + Observation vào history để LLM suy luận tiếp ở vòng kế tiếp
            history.append({
                "role": "assistant",
                "content": thought,
                "tool_call": {"id": tool_call_id, "name": tool_name, "arguments": arguments},
                "raw_content": llm_response.get("raw_content")  # Gemini: giữ thought_signature khi phát lại
            })
            history.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": obs_data
            })
            # -> Quay lại đầu vòng lặp: LLM đọc Observation và quyết định bước tiếp theo

        # ===== Trường hợp 3: Phản hồi không hợp lệ từ provider =====
        else:
            print(f"⚠️ [CHÚ Ý]: Phản hồi LLM không hợp lệ: {llm_response}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                **llm_meta,
                "action_type": "ERROR",
                "thought": thought,
                "output": str(llm_response),
                "latency_ms": llm_latency_ms
            })
            break

    else:
        # Hết MAX_ITERATIONS mà LLM vẫn chưa kết luận -> tổng hợp Final Answer từ Observation cuối cùng
        last_obs = next((m["content"] for m in reversed(history) if m.get("role") == "tool"), {})
        final_content = (
            f"Đã đạt giới hạn {MAX_ITERATIONS} vòng lặp ReAct. Kết quả gần nhất từ MCP Server: "
            f"{json.dumps(last_obs, ensure_ascii=False)}"
        )
        print(f"⛔ [MAX_ITERATIONS]: {final_content}")
        trace_logs.append({
            "step": step + 1,
            "query": user_query,
            **llm_meta,
            "action_type": "FINAL_ANSWER",
            "thought": "Chạm giới hạn vòng lặp, tổng hợp từ Observation cuối cùng.",
            "output": final_content,
            "tool_calls_used": tool_call_count,
            "latency_ms": 0.0
        })

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")
    
    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện trực tiếp với ReAct Agent:")
        print("💡 Gợi ý câu hỏi thử nghiệm:")
        print("   - Câu hỏi chung: 'Quy chế học vụ VinUni yêu cầu bao nhiêu tín chỉ?'")
        print("   - Tra cứu học vụ: 'Hãy tra cứu thông tin học vụ của sinh viên SV2026001'")
        print("   - Đặt lịch hẹn: 'Đặt lịch hẹn tư vấn cho SV2026001 vào 14:00 ngày 15/09/2026'")
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc phiên trò chuyện.\n")
        while True:
            try:
                user_input = input("👤 Sinh viên hỏi: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break
                logs = run_react_agent(user_input, provider, mcp_server)
                # Phiên chat lưu file riêng để không ghi đè artifact nộp bài trace_waterfall.json (từ --all)
                save_waterfall_trace(logs, filename="trace_interactive.json")
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break
    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra 5 Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []
        
        for tc in tests:
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] Loại test: {tc['type']} (Độ phức tạp: {tc['complexity']})")
            print(f"📌 Kỳ vọng: {tc['expected_behavior']}")
            
            if tc["question"].strip().startswith("TODO"):
                print(f"⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]:")
                print(f"   {tc['question']}")
                print(f"   👉 Hãy mở file 'config/test_cases.json' để viết câu hỏi thực tế cho Test Case này!")
                todo_count += 1
            else:
                logs = run_react_agent(tc["question"], provider, mcp_server)
                # Gắn nhãn test case vào từng sự kiện trace để dễ đối chiếu trong báo cáo
                all_traces.extend([{"test_case": tc["id"], **log} for log in logs])
                completed_count += 1
                
        print(f"\n==================================================")
        print(f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi {completed_count}/{len(tests)} Test Cases | {todo_count} Test Cases đang chờ điền câu hỏi (TODO)")
        if all_traces:
            save_waterfall_trace(all_traces)
        print(f"💡 Để trò chuyện trực tiếp từng câu: Chạy 'python src/app.py --interactive'")
    elif "--baseline" in sys.argv:
        # So sánh Cấp 2 (Chatbot không Tool) vs Cấp 3 (ReAct Agent + MCP) trên cùng câu hỏi
        print("⚖️ [BASELINE COMPARE MODE] Chatbot Cấp 2 vs ReAct Agent Cấp 3:")
        for tc in tests:
            if tc["question"].strip().startswith("TODO"):
                continue
            print(f"\n==================================================")
            print(f"🧪 [{tc['id']}] {tc['type']}")
            run_baseline_chatbot(tc["question"], provider)
            run_react_agent(tc["question"], provider, mcp_server)
    else:
        # Chế độ mặc định khi chỉ gõ 'python src/app.py'
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG CHƯƠNG TRÌNH:")
        print("  1. Chat trực tiếp liên tục:   python src/app.py --interactive")
        print("  2. Chạy toàn bộ Test Cases:    python src/app.py --all")
        print("  3. So sánh Chatbot vs Agent:   python src/app.py --baseline\n")
        
        sample_query = tests[1]["question"]
        print(f"--- 🏁 DEMO CHẠY THỬ 1 TEST CASE MẪU (TC02: Tra cứu học vụ) ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)
        print("\n💡 Hãy thử ngay lệnh: python src/app.py --interactive để chat trực tiếp!")
