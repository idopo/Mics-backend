import threading
import queue
from abc import ABC, abstractmethod


class DataHandler(ABC):
    def __init__(self):
        """Initialize the DataHandler."""
        self.running = False
        self.data_queue = None
        self.thread = None

    @abstractmethod
    def data_thread(self):
        """Thread method to handle data from the queue.
        Subclasses must implement this method.
        """
        pass

    @abstractmethod
    def save(self, data):
        """Insert data into the queue.
        Subclasses must implement this method.
        """
        pass

    @abstractmethod
    def prepare_run(self):
        """Prepare the data handler for running.
        Subclasses must implement this method.
        """
        pass

    @abstractmethod
    def stop_run(self):
        """Terminate the thread.
        Subclasses must implement this method.
        """
        pass