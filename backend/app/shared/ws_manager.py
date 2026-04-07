"""
Shared Kernel — WebSocket Manager
====================================
Quản lý danh sách admin đang kết nối WebSocket.
Nằm trong shared/ vì được dùng bởi nhiều context:
  ordering/application/event_handlers.py  → broadcast đơn mới + đổi trạng thái
  catalog/application/event_handlers.py   → broadcast menu thay đổi
  main.py                                  → wire WebSocket endpoint
Khi có đơn hàng mới → broadcast tới tất cả admin panel đang mở.

WHY WebSocket thay vì polling 30s:
- Quán nhận đơn ngay lập tức (0s delay thay vì 0-30s)
- Tiết kiệm bandwidth (không gọi API mỗi 30 giây)
- Có thể phát âm thanh thông báo (polling không biết khi nào có đơn mới)

⚠️ GIỚI HẠN: In-memory only — CHỈ HOẠT ĐỘNG VỚI 1 WORKER.
Nếu chạy nhiều Uvicorn workers, mỗi worker có _connections riêng biệt.
Worker A nhận đơn nhưng KDS kết nối Worker B → KDS không nhận thông báo.

Giải pháp khi cần nhiều workers:
- Option 1: Giữ 1 worker (đủ cho quán nhỏ, ~100 concurrent users)
- Option 2: Thêm Redis Pub/Sub để sync giữa workers
- Option 3: Dùng uvicorn --workers 1 + async concurrency (không cần multi-process)

AUTH:
- WebSocket không hỗ trợ custom headers từ browser
- Dùng query param: ws://host/api/v1/ws/orders?token=xxx
- Token được verify giống HTTP endpoints

RECONNECTION:
- Client tự reconnect khi mất kết nối (xem admin.html)
- Server ping mỗi 30s để detect dead connections
"""

import asyncio
import json
import logging
import os
from datetime import datetime

from fastapi import WebSocket

logger = logging.getLogger("ngonngon.ws")

# FIX G1: Phát hiện multi-worker và cảnh báo
_workers = int(os.environ.get("UVICORN_WORKERS", "1"))
if _workers > 1:
    logger.warning(
        f"⚠️ UVICORN_WORKERS={_workers} — WebSocket broadcast sẽ KHÔNG ĐÁNG TIN CẬY! "
        f"Mỗi worker có danh sách connections riêng. "
        f"KDS/Admin có thể KHÔNG nhận được thông báo đơn hàng mới. "
        f"Khuyến nghị: set UVICORN_WORKERS=1 hoặc thêm Redis Pub/Sub."
    )


class OrderWSManager:
    """
    Quản lý WebSocket connections cho admin panel.
    Thread-safe vì asyncio là single-threaded (1 event loop).
    """

    def __init__(self):
        # Set of active WebSocket connections
        self._connections: set[WebSocket] = set()
        # Ping task reference (for cleanup)
        self._ping_task: asyncio.Task | None = None

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def connect(self, ws: WebSocket):
        """Accept và track connection mới."""
        await ws.accept()
        self._connections.add(ws)
        logger.info(f"🔌 WS connected (total: {self.active_count})")

        # Start ping loop nếu chưa có
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._ping_loop())

    def disconnect(self, ws: WebSocket):
        """Xóa connection khi client ngắt."""
        self._connections.discard(ws)
        logger.info(f"🔌 WS disconnected (total: {self.active_count})")

    async def broadcast_new_order(self, order_data: dict):
        """
        Gửi thông báo đơn hàng mới tới TẤT CẢ admin/KDS đang kết nối.

        WHY fire-and-forget pattern:
        - Đơn hàng đã lưu DB thành công → notification là bonus
        - Nếu 1 WS connection chết, không ảnh hưởng đơn hàng
        - Dead connection sẽ bị dọn trong _ping_loop
        """
        if not self._connections:
            return

        message = json.dumps({
            "type": "new_order",
            "data": order_data,
            "timestamp": datetime.now().isoformat(),
        })

        await self._broadcast_raw(message)

        logger.info(
            f"📡 Broadcast new order to {self.active_count} client(s)"
        )

    async def broadcast_status_change(self, status_data: dict):
        """Gửi thông báo thay đổi trạng thái đơn tới tất cả clients."""
        if not self._connections:
            return
        message = json.dumps({
            "type": "status_change",
            "data": status_data,
            "timestamp": datetime.now().isoformat(),
        })
        await self._broadcast_raw(message)
        logger.info(f"📡 Broadcast status change to {self.active_count} client(s)")

    async def broadcast_menu_update(self):
        """
        Báo tất cả clients clear cache và reload menu.
        WHY: Admin thay đổi sản phẩm → khách cần thấy menu mới ngay.
        Client nhận event này → clear JS cache + xóa SW cache + re-fetch /menu.
        """
        if not self._connections:
            return
        message = json.dumps({
            "type": "menu_updated",
            "timestamp": datetime.now().isoformat(),
        })
        await self._broadcast_raw(message)
        logger.info(f"📡 Broadcast menu_updated to {self.active_count} client(s)")

    async def _broadcast_raw(self, message: str):
        """Gửi message tới tất cả connections, dọn dead connections."""
        dead: list[WebSocket] = []
        for ws in self._connections.copy():
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

        if dead:
            logger.info(f"🧹 Cleaned {len(dead)} dead WS connection(s)")

    async def _ping_loop(self):
        """
        Gửi ping mỗi 30s để:
        1. Detect dead connections (admin đóng tab, mất mạng)
        2. Giữ connection alive qua proxy/load balancer (có timeout)

        WHY 30s: đủ thường xuyên để detect nhanh, không tốn bandwidth
        """
        while self._connections:
            await asyncio.sleep(30)
            dead: list[WebSocket] = []
            for ws in self._connections.copy():
                try:
                    await ws.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.discard(ws)
            if dead:
                logger.debug(f"🧹 Ping cleanup: {len(dead)} dead connection(s)")


# Singleton — import ở bất kỳ đâu
ws_manager = OrderWSManager()
