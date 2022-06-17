# -*- coding: utf-8 -*-
import copy
import time
import threading


class IOStream:
    def __init__(self):
        self._mutex = threading.Event()
        self.output_buffer = {}

    def output(self, source, msg, timeout=3):
        self._mutex.wait(timeout)
        self._mutex.clear()

        if source not in self.output_buffer:
            self.output_buffer[source] = []
        outmsg = {time.time(), msg}
        self.output_buffer[source].append(outmsg)

        self._mutex.set()

    def copy(self, timeout=3):
        self._mutex.wait(timeout)
        self._mutex.clear()
        return copy.deepcopy(self.output_buffer)
        self._mutex.set()

    def clear(self, timeout=3):
        self._mutex.wait(timeout)
        self._mutex.clear()
        self.output_buffer = {}
        self._mutex.set()

    def wait_clear(self, timeout=3):
        self._mutex.wait(timeout)
        self._mutex.clear()

    def clear_mutex(self):
        self._mutex.set()
