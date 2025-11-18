````markdown
MCP-chatbot — trợ thủ MCP cục bộ và tìm kiếm web đa nguồn

Tóm tắt ngắn
- Một dự án nhỏ cung cấp công cụ MCP cục bộ (thông qua `hieu.py`) thu thập kết quả tìm kiếm web từ nhiều nguồn (SerpAPI, Serper, DuckDuckGo HTML). `mcp_pipe.py` kết nối một endpoint WebSocket MCP để chạy script MCP. Giao diện Tkinter trước đây đã được loại bỏ — sử dụng `start_main.py` (chạy không giao diện) để cấu hình và chạy dịch vụ.

Cách chạy (Linux / macOS / WSL)
1. Tạo và kích hoạt một virtual environment, sau đó cài đặt các yêu cầu:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Cấu hình khóa API
- `config.json` trong repo có thể chứa các khóa (SERPAPI_KEY có sẵn). Ưu tiên đặt bí mật trong file `.env` để dùng lúc chạy hoặc lưu vào biến môi trường của hệ điều hành.

3. Cấu hình và chạy dịch vụ không giao diện
- Lưu một endpoint MCP vào `config.json`:

```bash
python start_main.py save-config --mcp-endpoint "wss://your-mcp-endpoint"
```

- Khởi động dịch vụ dưới nền:

```bash
python start_main.py start
```

- Chạy dịch vụ ở foreground (ghi log ra stdout):

```bash
python start_main.py start --foreground
```

Ghi chú & các sửa đề nghị
- `hieu.py` mong đợi một package `mcp.server.fastmcp` (FastMCP). Hãy đảm bảo `fastmcp` có sẵn hoặc điều chỉnh các import cho phù hợp.
- `mcp_pipe.py` đọc `MCP_ENDPOINT` từ `config_manager.load_config()` và đặt nó làm biến môi trường. Đảm bảo `CONFIG_PATH` trong `config_manager.py` có quyền ghi.

Ghi chú
- `start_main.py` thay thế GUI trước đó và dùng `sys.executable` để tạo tiến trình nên sẽ tôn trọng virtual environment/interpreter của bạn.
- `hieu.py` mong đợi package `mcp.server.fastmcp` (FastMCP). Hãy đảm bảo `fastmcp` có sẵn hoặc điều chỉnh import nếu cần.
- `mcp_pipe.py` đọc `MCP_ENDPOINT` từ `config_manager.load_config()` và đặt nó làm biến môi trường. Đảm bảo `CONFIG_PATH` trong `config_manager.py` có thể ghi được.

Bảo mật
- Không commit `config.json` hoặc `.env` có chứa API keys. Một `.gitignore` đã được thêm để hỗ trợ.

Bước tiếp theo
- Thêm unit test cho các adapter tìm kiếm (happy path + lỗi mạng)
- Thêm xử lý dừng/gọi thoát (graceful shutdown) cho các subprocess trong `main.py` và cơ chế quay vòng/logging (log rotation) ổn định hơn

````