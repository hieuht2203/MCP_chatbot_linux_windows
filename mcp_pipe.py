"""
Script này dùng để kết nối tới MCP server và chuyển dữ liệu đầu vào/ra tới endpoint WebSocket.
Version: 0.1.0

Cách dùng:

export MCP_ENDPOINT=<mcp_endpoint>
python mcp_pipe.py <mcp_script>

"""

from config_manager import load_config  # Thêm import
import os
config = load_config()
# Thiết lập biến môi trường MCP_ENDPOINT
os.environ["MCP_ENDPOINT"] = config["MCP_ENDPOINT"]

import asyncio
import websockets
import subprocess
import logging
import signal
import sys
import random
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MCP_PIPE')

# Cấu hình kết nối lại
INITIAL_BACKOFF = 1  # Thời gian chờ ban đầu (giây)
MAX_BACKOFF = 600    # Thời gian chờ tối đa (giây)
reconnect_attempt = 0
backoff = INITIAL_BACKOFF

async def connect_with_retry(uri):
    """Kết nối tới WebSocket server với cơ chế thử lại"""
    global reconnect_attempt, backoff
    while True:  # Kết nối lại vô hạn
        try:
            if reconnect_attempt > 0:
                wait_time = backoff * (1 + random.random() * 0.1)  # Thêm độ nhiễu ngẫu nhiên
                logger.info(f"Chờ {wait_time:.2f} giây trước khi thử kết nối lần {reconnect_attempt}...")
                await asyncio.sleep(wait_time)
                
            # Thử kết nối
            await connect_to_server(uri)
        
        except Exception as e:
            reconnect_attempt += 1
            logger.warning(f"Kết nối bị đóng (lần thử: {reconnect_attempt}): {e}")            
            # Tính thời gian chờ lần kết nối tiếp theo (exponential backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)

async def connect_to_server(uri):
    """Kết nối WebSocket server và thiết lập kênh 2 chiều với `mcp_script`"""
    global reconnect_attempt, backoff
    try:
        logger.info(f"Đang kết nối tới WebSocket server...")
        async with websockets.connect(uri) as websocket:
            logger.info(f"Kết nối tới WebSocket server thành công")
            
            # Reset bộ đếm kết nối lại nếu đóng kết nối bình thường
            reconnect_attempt = 0
            backoff = INITIAL_BACKOFF
            
            # Khởi động process mcp_script
            # Use text=True for universal newline/text handling and encoding
            process = subprocess.Popen(
                ['python', mcp_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            logger.info(f"Đã khởi động process {mcp_script}")
            
            # Tạo 2 task: đọc từ WebSocket và ghi vào process, đọc từ process và gửi tới WebSocket
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process),
                pipe_process_to_websocket(process, websocket),
                pipe_process_stderr_to_terminal(process)
            )
    except websockets.exceptions.ConnectionClosed as e:
        logger.error(f"Kết nối WebSocket bị đóng: {e}")
        raise  # Ném lại exception để thử kết nối lại
    except Exception as e:
        logger.error(f"Lỗi kết nối: {e}")
        raise  # Ném lại exception
    finally:
        # Đảm bảo process con được kết thúc đúng cách
        if 'process' in locals():
            logger.info(f"Đang kết thúc process {mcp_script}")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.info(f"Process {mcp_script} đã kết thúc")

async def pipe_websocket_to_process(websocket, process):
    """Đọc dữ liệu từ WebSocket và ghi vào stdin của process"""
    try:
        while True:
            message = await websocket.recv()
            logger.debug(f"<< {message[:120]}...")
            
            if isinstance(message, bytes):
                message = message.decode('utf-8')
            process.stdin.write(message + '\n')
            process.stdin.flush()
    except Exception as e:
        logger.error(f"Lỗi khi chuyển dữ liệu từ WebSocket sang process: {e}")
        raise
    finally:
        if not process.stdin.closed:
            process.stdin.close()

async def pipe_process_to_websocket(process, websocket):
    """Đọc dữ liệu từ stdout của process và gửi tới WebSocket"""
    try:
        while True:
            data = await asyncio.get_event_loop().run_in_executor(
                None, process.stdout.readline
            )
            
            if not data:
                logger.info("Process đã kết thúc output")
                break
                
            # Thêm tính năng gửi log
            if data.startswith("[GUI_LOG]"):
                await websocket.send(data)
                continue
                
            logger.debug(f">> {data[:120]}...")
            await websocket.send(data)
    except Exception as e:
        logger.error(f"Lỗi khi chuyển dữ liệu từ process sang WebSocket: {e}")
        raise

async def pipe_process_stderr_to_terminal(process):
    """Đọc dữ liệu stderr từ process và in ra terminal"""
    try:
        while True:
            data = await asyncio.get_event_loop().run_in_executor(
                None, process.stderr.readline
            )
            
            if not data:
                logger.info("Process đã kết thúc stderr output")
                break
                
            sys.stderr.write(data)
            sys.stderr.flush()
    except Exception as e:
        logger.error(f"Lỗi khi đọc stderr từ process: {e}")
        raise

# Xử lý tín hiệu ngắt
def signal_handler(sig, frame):
    """Xử lý tín hiệu interrupt"""
    logger.info("Nhận tín hiệu ngắt, đang tắt chương trình...")
    sys.exit(0)

# Thêm hàm gửi log tới GUI
def send_log_to_gui(message):
    print(f"[GUI_LOG]{message}")

if __name__ == "__main__":
    # Đăng ký signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Kiểm tra mcp_script
    if len(sys.argv) < 2:
        logger.error("Cách dùng: mcp_pipe.py <mcp_script>")
        sys.exit(1)
    
    mcp_script = sys.argv[1]
    
    # Lấy endpoint từ biến môi trường
    endpoint_url = os.environ.get('MCP_ENDPOINT')
    if not endpoint_url:
        logger.error("Vui lòng thiết lập biến môi trường `MCP_ENDPOINT`")
        sys.exit(1)
    
    # Chạy vòng lặp chính
    try:
        asyncio.run(connect_with_retry(endpoint_url))
    except KeyboardInterrupt:
        logger.info("Chương trình bị dừng bởi người dùng")
    except Exception as e:
        logger.error(f"Lỗi khi chạy chương trình: {e}")
