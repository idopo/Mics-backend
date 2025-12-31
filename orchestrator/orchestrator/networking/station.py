import multiprocessing
import threading
import time
import socket
import logging
from itertools import count
from copy import copy
from typing import Dict, Callable, Optional

import zmq
from zmq.eventloop.zmqstream import ZMQStream
from tornado.ioloop import IOLoop

from .message import Message


class Station(multiprocessing.Process):
    """
    Pure ZeroMQ networking process.

    NO prefs.
    NO global state.
    ALL configuration injected via constructor.
    """

    repeat_interval = 5.0  # seconds

    def __init__(
        self,
        *,
        station_id: str,
        listen_port: int,
        listens: Optional[Dict[str, Callable]] = None,
        pusher: bool = False,
        push_ip: Optional[str] = None,
        push_port: Optional[int] = None,
        push_id: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__()

        # ---- Identity / config ----
        self.id = station_id
        self.listen_port = int(listen_port)

        self.pusher_enabled = bool(pusher)
        self.push_ip = push_ip
        self.push_port = push_port
        self.push_id = push_id.encode("utf-8") if isinstance(push_id, str) else push_id

        # ---- Logging ----
        self.logger = logger or logging.getLogger(f"station.{station_id}")

        # ---- ZMQ runtime ----
        self.context = None
        self.loop = None
        self.listener = None
        self.pusher = None

        # ---- Message handling ----
        self.listens: Dict[str, Callable] = listens or {}
        self.listens.setdefault("CONFIRM", self.l_confirm)
        self.listens.setdefault("STREAM", self.l_stream)

        self.msg_counter = count()
        self.send_outbox = {}
        self.push_outbox = {}
        self.senders = {}
        self.routes = {}

        self.msgs_received = multiprocessing.Value("i", 0)
        self.closing = multiprocessing.Event()
        self.file_block = multiprocessing.Event()

        # ---- Networking info ----
        self.ip = self._get_ip()

    # ------------------------------------------------------------------
    # Process lifecycle
    # ------------------------------------------------------------------

    def run(self):
        self.logger.info("Station starting (id=%s port=%s)", self.id, self.listen_port)

        self.context = zmq.Context()
        self.loop = IOLoop()

        # ROUTER socket
        router = self.context.socket(zmq.ROUTER)
        router.setsockopt_string(zmq.IDENTITY, self.id)
        router.bind(f"tcp://*:{self.listen_port}")
        self.listener = ZMQStream(router, self.loop)
        self.listener.on_recv(self.handle_listen)

        # DEALER socket (optional)
        if self.pusher_enabled:
            if not all([self.push_ip, self.push_port, self.push_id]):
                raise ValueError("Pusher enabled but push_* config missing")

            dealer = self.context.socket(zmq.DEALER)
            dealer.setsockopt_string(zmq.IDENTITY, self.id)
            dealer.connect(f"tcp://{self.push_ip}:{self.push_port}")
            self.pusher = ZMQStream(dealer, self.loop)
            self.pusher.on_recv(self.handle_listen)

        threading.Thread(target=self.repeat, daemon=True).start()

        self.logger.info("Station listening")
        self.loop.start()

    def release(self):
        self.logger.info("Station shutting down")
        self.closing.set()

        try:
            ctx = zmq.Context.instance()
            sock = ctx.socket(zmq.DEALER)
            sock.setsockopt_string(zmq.IDENTITY, f"{self.id}.closer")
            sock.connect(f"tcp://localhost:{self.listen_port}")
            sock.send_multipart([self.id.encode(), b"CLOSING"])
            sock.close()
        except Exception:
            pass

        self.terminate()

    # ------------------------------------------------------------------
    # Message send helpers
    # ------------------------------------------------------------------

    def prepare_message(self, to, key, value, repeat=True, flags=None):
        msg = Message()
        msg.sender = self.id
        msg.to = to
        msg.key = key
        msg.value = value
        msg.id = f"{self.id}_{next(self.msg_counter)}"

        if flags:
            msg.flags.update(flags)
        if not repeat:
            msg.flags["NOREPEAT"] = True

        return msg

    def send(self, to, key, value=None, msg=None, repeat=True, flags=None):
        if msg is None:
            msg = self.prepare_message(to, key, value, repeat, flags)

        encoded = msg.serialize()
        self.listener.send_multipart([to.encode(), encoded])

        if repeat and msg.key != "CONFIRM":
            self.send_outbox[msg.id] = (time.time(), msg)

    def push(self, key, value=None, msg=None, repeat=True, flags=None):
        if not self.pusher:
            return

        if msg is None:
            msg = self.prepare_message(self.push_id.decode(), key, value, repeat, flags)

        encoded = msg.serialize()
        self.pusher.send_multipart([self.push_id, encoded])

        if repeat and msg.key != "CONFIRM":
            self.push_outbox[msg.id] = (time.time(), msg)

    # ------------------------------------------------------------------
    # Message receiving
    # ------------------------------------------------------------------

    def handle_listen(self, frames):
        with self.msgs_received.get_lock():
            self.msgs_received.value += 1

        if frames[-1] == b"CLOSING":
            self.loop.stop()
            return

        if len(frames) >= 2:
            sender = frames[0]
            msg = Message(frames[-1])
        else:
            msg = Message(frames[0])
            sender = msg.sender.encode()

        if msg.key in self.listens:
            try:
                threading.Thread(
                    target=self.listens[msg.key],
                    args=(msg,),
                    daemon=True,
                ).start()
            except Exception:
                self.logger.exception("Listener failed for key=%s", msg.key)

        if msg.key != "CONFIRM" and "NOREPEAT" not in msg.flags:
            self.send(msg.sender, "CONFIRM", msg.id)

    # ------------------------------------------------------------------
    # Repeat / confirm
    # ------------------------------------------------------------------

    def repeat(self):
        while not self.closing.is_set():
            now = time.time()

            for outbox in (self.send_outbox, self.push_outbox):
                for msg_id, (ts, msg) in list(outbox.items()):
                    if now - ts > self.repeat_interval:
                        msg.ttl -= 1
                        if msg.ttl <= 0:
                            del outbox[msg_id]
                        else:
                            outbox[msg_id] = (now, msg)
                            if outbox is self.send_outbox:
                                self.send(msg.to, msg.key, msg.value, msg=msg)
                            else:
                                self.push(msg.key, msg.value, msg=msg)

            time.sleep(self.repeat_interval)

    def l_confirm(self, msg: Message):
        self.send_outbox.pop(msg.value, None)
        self.push_outbox.pop(msg.value, None)

    def l_stream(self, msg: Message):
        inner_key = msg.value["inner_key"]
        payload = msg.value["payload"]
        handler = self.listens.get(inner_key)
        if not handler:
            return

        for v in payload:
            msg.key = inner_key
            msg.value = v
            handler(msg)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _get_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"
