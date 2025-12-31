from orchestrator.data_handlers.Data_Handler import DataHandler
from elasticsearch import Elasticsearch
import threading
import queue
import pytz
from datetime import datetime


class ElasticSearchDataHandler(DataHandler):
    SENTINEL = object()

    def __init__(self, client=None, index="event_log_v2", num_workers=2):
        super().__init__()
        self.dropped_messages = 0
        # Add short timeouts to avoid long hangs if ES is unhappy
        self.client = client or Elasticsearch(
            [{"host": "132.77.73.217", "port": 9200, "scheme": "http"}],
            # transport options can vary by version; this keeps it modest
            max_retries=1,
            retry_on_timeout=False,
        )
        self.index = index
        self.num_workers = num_workers

        self.data_queue = queue.Queue()
        self.running = False
        self.threads = []
        self._lock = threading.Lock()

    # ---------- Worker ----------

    def data_thread(self):
        while True:
            data = self.data_queue.get()
            try:
                if data is self.SENTINEL:
                    break  # exit worker
                self.process_data(data)
            except Exception as e:
                print(f"Error processing data: {e}")
            # no task_done(), no queue.join()

    def process_data(self, data):
        if not self.running:
            return

        try:
            dt_utc = datetime.fromtimestamp(data["timestamp"], tz=pytz.utc)
            jerusalem_tz = pytz.timezone("Asia/Jerusalem")
            dt_jerusalem = dt_utc.astimezone(jerusalem_tz)
            data["timestamp"] = dt_jerusalem

            # Short request timeout so we don't hang forever
            self.client.index(index=self.index, document=data, request_timeout=2)
        except Exception as e:
            print(f"Error indexing data: {e}")

    # ---------- API ----------

    def save(self, data):
        with self._lock:
            if not self.running:
                raise RuntimeError("Handler is not running. Call `prepare_run` first.")
            self.data_queue.put(data)

    def prepare_run(self):
        with self._lock:
            if self.running:
                return

            try:
                if not self.client.ping():
                    self.client = Elasticsearch(
                        [{"host": "132.77.73.217", "port": 9200, "scheme": "http"}],
                        max_retries=1,
                        retry_on_timeout=False,
                    )
            except Exception as e:
                print(f"Error pinging Elasticsearch: {e}")

            print("Connected to Elasticsearch.")

            self.running = True
            self.threads = []
            for _ in range(self.num_workers):
                t = threading.Thread(target=self.data_thread, daemon=True)
                t.start()
                self.threads.append(t)

            if self.threads:
                self.thread = self.threads[0]

    def stop_run(self):
        with self._lock:
            if not self.running:
                return

            # stop accepting new items
            self.running = False

            # Tell all workers to exit once they've drained the queue
            for _ in self.threads:
                self.data_queue.put(self.SENTINEL)

        # DON'T block the GUI thread waiting for workers or queue
        # We also DON'T close the client here to avoid ClosedPoolError races.
        print("Handler stopping (non-blocking).")

    def _summarize_data(self, data):
        try:
            subject = data.get("subject")
            pilot = data.get("pilot")
            ts = data.get("timestamp")
            event = data.get("event", {})
            event_type = event.get("event_type")
            return f"subject={subject}, pilot={pilot}, ts={ts}, event_type={event_type}"
        except Exception:
            return repr(data)
