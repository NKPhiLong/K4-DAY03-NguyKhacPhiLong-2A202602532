"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.

📝 Chuẩn "history" dùng chung cho vòng lặp ReAct (provider-agnostic):
    {"role": "user",      "content": "<câu hỏi>"}
    {"role": "assistant", "tool_call": {"id": "...", "name": "...", "arguments": {...}}, "content": "<thought/text>"}
    {"role": "tool",      "tool_call_id": "...", "name": "...", "content": {<observation dict>}}
Mỗi provider tự chuyển đổi history này sang định dạng SDK tương ứng.
"""

import os
import re
import sys
import json
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "",
                            history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Trả về dict chuẩn hóa:
          {"type": "tool_call", "tool_name": str, "arguments": dict, "thought": str}
          {"type": "text", "content": str, "thought": str}
        `history` (nếu có) là toàn bộ hội thoại ReAct tính đến hiện tại (bao gồm cả Observation từ MCP Server).
        """
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để chạy thử mà không tốn API Key (mô phỏng suy luận ReAct đa bước)"""
    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return f"[Mock Chatbot Response]: Xin chào! Tôi đã nhận được câu hỏi '{prompt}'. (Chế độ Chatbot không có Tool tra cứu dữ liệu thời gian thực)."

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "",
                            history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        history = history or []
        prompt_lower = prompt.lower()
        sid_match = re.search(r"sv\d{7}", prompt_lower)
        student_id = sid_match.group(0).upper() if sid_match else None
        wants_booking = "đặt lịch" in prompt_lower or "hẹn" in prompt_lower
        time_match = re.search(r"(\d{1,2}:\d{2})\s*(?:ngày\s*)?(\d{1,2}/\d{1,2}/\d{4})", prompt)
        datetime_str = f"{time_match.group(1)} {time_match.group(2)}" if time_match else "14:00 15/09/2026"
        advisor_match = re.search(r"((?:PGS\.?\s?TS\.?|TS\.?|ThS\.?)\s+[^\d,.;]+?)(?=\s+vào|\s+lúc|,|\.|$)", prompt)
        advisor_in_prompt = advisor_match.group(1).strip() if advisor_match else None

        # ---- Các lượt sau: suy luận dựa trên Observation gần nhất (mô phỏng ReAct) ----
        last_obs = next((m for m in reversed(history) if m.get("role") == "tool"), None)
        if last_obs:
            obs = last_obs.get("content", {}) or {}
            tool = last_obs.get("name")
            if tool == "academic_query":
                if obs.get("status") == "SUCCESS":
                    d = obs.get("data", {})
                    if wants_booking:
                        return {
                            "type": "tool_call",
                            "tool_name": "schedule_appointment",
                            "arguments": {"student_id": obs.get("student_id", student_id),
                                          "datetime_str": datetime_str,
                                          "advisor_name": d.get("advisor", "PGS.TS Nguyễn Văn A")},
                            "thought": f"Observation cho biết cố vấn của sinh viên là '{d.get('advisor')}'. Đã đủ tham số, tôi sẽ gọi schedule_appointment."
                        }
                    return {
                        "type": "text",
                        "content": (f"Thông tin học vụ của sinh viên {obs.get('student_id')} ({d.get('full_name')}): "
                                    f"Lớp {d.get('class')}, GPA {d.get('gpa')}, Email {d.get('email')}, "
                                    f"Trạng thái: {d.get('status')}, Cố vấn học tập: {d.get('advisor')}."),
                        "thought": "Đã nhận dữ liệu học vụ từ MCP Server. Tổng hợp câu trả lời cuối cùng."
                    }
                return {
                    "type": "text",
                    "content": (f"Xin lỗi, hệ thống không tìm thấy sinh viên có mã '{student_id or 'đã cung cấp'}' trong cơ sở dữ liệu học vụ. "
                                "Bạn vui lòng kiểm tra lại mã sinh viên (định dạng SVxxxxxxx) hoặc liên hệ Phòng Đào tạo để được hỗ trợ."),
                    "thought": "Observation trả về NOT_FOUND. Không bịa dữ liệu, phản hồi lịch sự và dừng."
                }
            if tool == "schedule_appointment":
                if obs.get("status") == "SUCCESS":
                    return {
                        "type": "text",
                        "content": (f"Đã đặt lịch thành công! Mã booking: {obs.get('booking_id')}. "
                                    f"Sinh viên {obs.get('student_id')} sẽ gặp {obs.get('advisor')} vào lúc {obs.get('datetime')}."),
                        "thought": "Observation xác nhận đặt lịch thành công. Tổng hợp câu trả lời cuối cùng."
                    }
                return {
                    "type": "text",
                    "content": f"Rất tiếc, việc đặt lịch chưa thành công: {json.dumps(obs, ensure_ascii=False)}",
                    "thought": "Observation báo lỗi khi đặt lịch. Thông báo cho sinh viên."
                }

        # ---- Lượt đầu: nhận diện intent từ câu hỏi ----
        if wants_booking and student_id and advisor_in_prompt:
            return {
                "type": "tool_call",
                "tool_name": "schedule_appointment",
                "arguments": {"student_id": student_id, "datetime_str": datetime_str, "advisor_name": advisor_in_prompt},
                "thought": f"Người dùng yêu cầu đặt lịch cho {student_id} và đã cung cấp đủ cố vấn + thời gian. Gọi schedule_appointment."
            }
        if wants_booking and student_id:
            return {
                "type": "tool_call",
                "tool_name": "academic_query",
                "arguments": {"student_id": student_id},
                "thought": f"Người dùng muốn đặt lịch nhưng chưa rõ tên cố vấn. Cần tra cứu hồ sơ {student_id} trước để lấy trường 'advisor'."
            }
        if student_id or "tra cứu" in prompt_lower:
            return {
                "type": "tool_call",
                "tool_name": "academic_query",
                "arguments": {"student_id": student_id or "SV2026001"},
                "thought": f"Người dùng muốn tra cứu thông tin học vụ của sinh viên {student_id or 'SV2026001'}. Gọi academic_query."
            }
        return {
            "type": "text",
            "content": "[Mock Agent Response]: Xin chào! Quy chế học vụ VinUni yêu cầu sinh viên tích lũy tối thiểu 120 tín chỉ và duy trì GPA trên 2.0 để tốt nghiệp.",
            "thought": "Câu hỏi chung về quy chế học vụ, trả lời trực tiếp không cần gọi Tool."
        }


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-3.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    @staticmethod
    def _build_contents(prompt: str, history: List[Dict[str, Any]]):
        """Chuyển history chuẩn chung -> list[types.Content] của Gemini (user / model / function response)"""
        from google.genai import types
        if not history:
            return [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        contents = []
        for m in history:
            role = m.get("role")
            if role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.get("content", ""))]))
            elif role == "assistant":
                # Ưu tiên phát lại nguyên Content gốc của Gemini (giữ thought_signature bắt buộc với Gemini 3.x)
                if m.get("raw_content") is not None:
                    contents.append(m["raw_content"])
                    continue
                parts = []
                if m.get("tool_call"):
                    tc = m["tool_call"]
                    parts.append(types.Part.from_function_call(name=tc["name"], args=tc.get("arguments", {})))
                elif m.get("content"):
                    parts.append(types.Part.from_text(text=m["content"]))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif role == "tool":
                contents.append(types.Content(role="user", parts=[
                    types.Part.from_function_response(name=m.get("name", ""), response={"result": m.get("content", {})})
                ]))
        return contents

    def _generate_with_retry(self, client, contents, config, max_retries: int = 4):
        """Gọi Gemini; nếu gặp 429 (free-tier rate limit) thì chờ theo retryDelay API gợi ý rồi thử lại."""
        attempt = 0
        while True:
            try:
                return client.models.generate_content(model=self.model_name, contents=contents, config=config)
            except Exception as e:
                msg = str(e)
                is_rate_limit = "429" in msg or "RESOURCE_EXHAUSTED" in msg
                if not is_rate_limit or attempt >= max_retries:
                    raise
                attempt += 1
                m = re.search(r"retry in ([\d.]+)s", msg, flags=re.IGNORECASE)
                delay = min(max(float(m.group(1)) + 1 if m else 15.0, 5.0), 65.0)
                print(f"⏳ [Gemini Rate Limit]: Free-tier quota tạm hết. Chờ {delay:.0f}s rồi thử lại (lần {attempt}/{max_retries})...")
                time.sleep(delay)

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "",
                            history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)
        
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            contents = self._build_contents(prompt, history or [])
            response = self._generate_with_retry(client, contents, config)

            raw_content = None
            try:
                raw_content = response.candidates[0].content
            except Exception:
                pass

            # Gemini có thể trả kèm text (Thought) trước khi gọi function
            text_parts = []
            for part in (raw_content.parts if raw_content else []) or []:
                if getattr(part, "text", None) and not getattr(part, "thought", False):
                    text_parts.append(part.text)
            model_text = "\n".join(text_parts).strip()
            has_observation = any(m.get("role") == "tool" for m in (history or []))

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": model_text or f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}",
                    "raw_content": raw_content  # dùng để phát lại history kèm thought_signature
                }
            else:
                return {
                    "type": "text",
                    "content": model_text or (response.text or ""),
                    "thought": "Gemini đã tổng hợp Observation từ MCP Server thành câu trả lời cuối cùng." if has_observation
                               else "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    @staticmethod
    def _build_messages(prompt: str, system_prompt: str, history: List[Dict[str, Any]]):
        """Chuyển history chuẩn chung -> messages của OpenAI Chat Completions (assistant.tool_calls / role=tool)"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if not history:
            messages.append({"role": "user", "content": prompt})
            return messages
        for m in history:
            role = m.get("role")
            if role == "user":
                messages.append({"role": "user", "content": m.get("content", "")})
            elif role == "assistant":
                if m.get("tool_call"):
                    tc = m["tool_call"]
                    messages.append({
                        "role": "assistant",
                        "content": m.get("content") or None,
                        "tool_calls": [{
                            "id": tc.get("id", "call_0"),
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)}
                        }]
                    })
                else:
                    messages.append({"role": "assistant", "content": m.get("content", "")})
            elif role == "tool":
                messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", "call_0"),
                    "content": json.dumps(m.get("content", {}), ensure_ascii=False)
                })
        return messages

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "",
                            history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = self._build_messages(prompt, system_prompt, history or [])

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_call_id": call.id,
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": (msg.content or "").strip() or f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)." if not history
                               else "OpenAI đã tổng hợp Observation từ MCP Server thành câu trả lời cuối cùng."
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt, history)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
