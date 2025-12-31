import time
import threading
from itertools import count
from typing import Callable, Dict, Optional, Any

import zmq
from zmq.eventloop.zmqstream import ZMQStream
from tornado.ioloop import IOLoop

from .networking.message import Message


class RouterGateway:
    """
    Threaded ZMQ ROUTER endpoint that speaks *legacy* Pilot_Station format.

    Legacy expectations:
      - Incoming frames: [sender_identity, ..., serialized_message]
      - sender_identity (ROUTER frame) is the authoritative sender
      - serialized_message is JSON bytes for Message(...)
      - Receiver replies with CONFIRM unless NOREPEAT or key==CONFIRM

    This gateway:
      - Runs Tornado IOLoop in its own thread via start()
      - Allows send() from any thread (uses IOLoop.add_callback)
      - Optional resend loop for repeat=True messages
    """

    repeat_interval = 5.0

    def __init__(
        self,
        *,
        id: str,
        listen_port: int,
        listens: Optional[Dict[str, Callable[[Message], None]]] = None,
        log: Optional[Any] = None,
    ):
        self.id = str(id)
        self.listen_port = int(listen_port)
        self.log = log

        self.listens: Dict[str, Callable[[Message], None]] = listens or {}
        self.listens.setdefault("CONFIRM", self._l_confirm)

        self._counter = count()
        self._closing = threading.Event()

        self._outbox: Dict[str, tuple[float, Message]] = {}
        self._outbox_lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None

        # created in _thread_main
        self.context: Optional[zmq.Context] = None
        self.loop: Optional[IOLoop] = None
        self.router_stream: Optional[ZMQStream] = None

    # -------------------------
    # lifecycle

    def start(self):
        """Start ZMQ gateway in a background thread (non-blocking)."""
        if self._thread and self._thread.is_alive():
            return
        self._closing.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop gateway and its IOLoop."""
        self._closing.set()
        if self.loop:
            try:
                self.loop.add_callback(self.loop.stop)
            except Exception:
                pass

    def _thread_main(self):
        # Create per-thread context + loop
        self.context = zmq.Context()
        self.loop = IOLoop()

        sock = self.context.socket(zmq.ROUTER)
        sock.setsockopt_string(zmq.IDENTITY, self.id)
        sock.bind(f"tcp://*:{self.listen_port}")

        self.router_stream = ZMQStream(sock, self.loop)
        self.router_stream.on_recv(self._on_recv)

        # resend loop
        threading.Thread(target=self._repeat_loop, daemon=True).start()

        if self.log:
            self.log.info("RouterGateway up id=%s port=%s", self.id, self.listen_port)

        try:
            self.loop.start()
        finally:
            try:
                if self.router_stream:
                    self.router_stream.close()
            except Exception:
                pass
            try:
                if self.context:
                    self.context.destroy(linger=0)
            except Exception:
                pass

    # -------------------------
    # sending

    def _prepare(self, to: str, key: str, value: Any, flags: Optional[dict] = None) -> Message:
        msg = Message()
        msg.sender = self.id
        msg.to = to
        msg.key = key
        msg.value = value
        msg.id = f"{self.id}_{next(self._counter)}"
        if flags:
            msg.flags.update(flags)
        msg.get_timestamp()
        return msg

    def send(
        self,
        to: str,
        key: str,
        value: Any = None,
        *,
        flags: Optional[dict] = None,
        repeat: bool = False,
    ):
        """
        Thread-safe send: schedules actual send on the gateway's IOLoop thread.
        """
        if not self.loop or not self.router_stream:
            raise RuntimeError("RouterGateway not started yet")

        msg = self._prepare(to, key, value, flags=flags)
        data = msg.serialize()
        if not data:
            raise RuntimeError("Failed to serialize message")

        def _do_send():
            # ROUTER requires first frame = recipient identity
            self.router_stream.send_multipart([to.encode("utf-8"), data])

        self.loop.add_callback(_do_send)

        if repeat and key != "CONFIRM" and ("NOREPEAT" not in (msg.flags or {})):
            with self._outbox_lock:
                self._outbox[msg.id] = (time.time(), msg)

    # -------------------------
    # receive + dispatch

    def _on_recv(self, frames):
        """
        frames[0] = ROUTER identity of sender (authoritative sender)
        frames[-1] = serialized Message JSON bytes
        """
        if not frames or len(frames) < 2:
            return

        sender_ident = frames[0]  # bytes
        raw = frames[-1]          # bytes

        try:
            msg = Message(raw)
        except Exception as e:
            if self.log:
                self.log.exception("Bad message from %s: %s", sender_ident, e)
            return

        # ✅ legacy-correct: sender comes from ROUTER identity frame
        msg.sender = sender_ident.decode("utf-8", errors="replace")

        handler = self.listens.get(msg.key)
        if handler:
            try:
                handler(msg)
            except Exception as e:
                if self.log:
                    self.log.exception("Handler error key=%s from=%s: %s", msg.key, msg.sender, e)
        else:
            if self.log:
                self.log.warning("No handler for key=%s (from=%s)", msg.key, msg.sender)

        # ✅ legacy confirm behavior
        if msg.key != "CONFIRM" and ("NOREPEAT" not in (msg.flags or {})):
            confirm = self._prepare(msg.sender, "CONFIRM", msg.id, flags={"NOREPEAT": True})
            try:
                self.router_stream.send_multipart([
                    msg.sender.encode("utf-8"),
                    confirm.serialize(),
                ])
            except Exception:
                pass

    def _l_confirm(self, msg: Message):
        # CONFIRM payload is msg.id being confirmed
        with self._outbox_lock:
            self._outbox.pop(msg.value, None)

    def _repeat_loop(self):
        while not self._closing.is_set():
            now = time.time()
            with self._outbox_lock:
                items = list(self._outbox.items())

            for mid, (ts, msg) in items:
                if msg.ttl <= 0:
                    with self._outbox_lock:
                        self._outbox.pop(mid, None)
                    if self.log:
                        self.log.warning("Message expired id=%s", mid)
                    continue

                if (now - ts) > (self.repeat_interval * 2):
                    # schedule resend on loop thread
                    if self.loop and self.router_stream:
                        def _resend(m=msg, mid_=mid, now_=now):
                            try:
                                self.router_stream.send_multipart([m.to.encode("utf-8"), m.serialize()])
                                m.ttl -= 1
                                with self._outbox_lock:
                                    self._outbox[mid_] = (now_, m)
                            except Exception:
                                pass

                        try:
                            self.loop.add_callback(_resend)
                        except Exception:
                            pass

            time.sleep(self.repeat_interval)
