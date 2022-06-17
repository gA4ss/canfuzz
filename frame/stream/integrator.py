# -*- coding: utf-8 -*-
from collections import Iterable, deque

from frame.stream.processor import Processor


class Integrator(Processor):

    def __init__(self, size: int, message_builder: callable):
        self._message_builder = message_builder
        self._size = size
        self._queue = deque()

    def process(self, message) -> Iterable:
        value = float(message)

        #
        # 只保存指定长度的数据
        #
        if len(self._queue) == self._size:
            self._queue.popleft()

        self._queue.append(value)

        #
        # sum(self._queue) / len(self._queue)
        # 将队列的所有值都相加，然后划分等份。
        #
        yield self._message_builder(message, sum(self._queue) / len(self._queue))
