import threading
import time
import logging
from copy import copy
from itertools import count
from typing import Dict, Callable, Optional, Any

import zmq
from zmq.eventloop.zmqstream import ZMQStream
from tornado.ioloop import IOLoop

from .message import Message


class NetNode:
    """
    Pure DEALER/ROUTER messaging node.
    No prefs. No autopilot. No side effects.
    """

    repeat_interval = 5.0

    def __init__(
        self,
        *,
        node_id: str,
        upstream_id: str,
        upstream_ip: str,
        upstream_port: int,
        listens: Dict[str, Callable],
        router_port: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
        daemon: bool = True,
    ):
        self.id = node_id
        self.upstream_id = upstream_id
        self.upstream_ip = upstream_ip
        self.upstream_port = int(upstream_port)
        self.router_port = router_port

        self.logger = logger or logging.getLogger(f"netnode.{node_id}")

        self.context = zmq.Context.instance()
        self.loop = IOLoop.current()

        self.listens = {"CONFIRM": self.l_confirm}
        self.listens.update(listens)

        self.sock = None
        self.router = None

        self.msg_counter = count()
        self.outbox = {}
        self.senders = {}

        self.closing = threading.Event()

        self._init_sockets()

        self.loop_thread = threading.Thread(target=self._run_loop, daemon=daemon)
        self.loop_thread.start()

        threading.Thread(target=self._repeat_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # ZMQ setup
    # ------------------------------------------------------------------

    def _init_sockets(self):
        # DEALER → upstream Station
        dealer = self.context.socket(zmq.DEALER)
        dealer.setsockopt_string(zmq.IDENTITY, self.id)
        dealer.connect(f"tcp://{self.upstream_ip}:{self.upstream_port}")
        self.sock = ZMQStream(dealer, self.loop)
        self.sock.on_recv(self._handle_recv)

        # Optional ROUTER (direct addressing)
        if self.router_port is not None:
            router = self.context.socket(zmq.ROUTER)
            router.setsockopt_string(zmq.IDENTITY, self.id)
            router.bind(f"tcp://*:{self.router_port}")
            self.router = ZMQStream(router, self.loop)
            self.router.on_recv(self._handle_recv)

    def _run_loop(self):
        try:
            self.loop.start()
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_recv(self, frames):
        msg = Message(frames[-1])

        if not msg.validate():
            self.logger.error("Invalid message: %s", msg)
            return

        handler = self.listens.get(msg.key)
        if handler:
            try:
                handler(msg)
            except Exception:
                self.logger.exception("Listener failed: %s", msg.key)

        if msg.key != "CONFIRM" and "NOREPEAT" not in msg.flags:
            self.send(msg.sender, "CONFIRM", msg.id)

    # ------------------------------------------------------------------
    # Send helpers
    # ------------------------------------------------------------------

    def send(
        self,
        to: str,
        key: str,
        value: Any = None,
        *,
        repeat: bool = False,
        flags: Optional[dict] = None,
    ):
        msg = Message(
            sender=self.id,
            to=to,
            key=key,
            value=value,
            id=f"{self.id}_{next(self.msg_counter)}",
            flags=flags or {},
        )

        encoded = msg.serialize()
        self.sock.send_multipart([self.upstream_id.encode(), encoded])

        if repeat:
            self.outbox[msg.id] = (time.time(), msg)

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _repeat_loop(self):
        while not self.closing.is_set():
            now = time.time()
            for msg_id, (ts, msg) in list(self.outbox.items()):
                if now - ts > self.repeat_interval:
                    msg.ttl -= 1
                    if msg.ttl <= 0:
                        del self.outbox[msg_id]
                        self.logger.warning("Message expired: %s", msg_id)
                    else:
                        self.outbox[msg_id] = (now, msg)
                        self.sock.send_multipart(
                            [self.upstream_id.encode(), msg.serialize()]
                        )
            time.sleep(self.repeat_interval)

    # ------------------------------------------------------------------
    # Built-ins
    # ------------------------------------------------------------------

    def l_confirm(self, msg: Message):
        self.outbox.pop(msg.value, None)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self):
        self.closing.set()
        try:
            self.loop.stop()
        except Exception:
            pass
