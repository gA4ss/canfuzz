# -*- coding: utf-8 -*-
import time

from frame.message.can import CANMessage
from frame.message.uds import UDSMessage
from frame.message.isotp import ISOTPMessage
from frame.kernel.module import CANModule
from frame.stream.cmdres import CmdResult, CMDRES_STR


class ping(CANModule):
    name = "ping"
    version = 1.0
    help = {
        "describe": "用于ping功能，探测模块。",
        # "init_parameters": None,
        "action_parameters": {
            "body": {
                "describe": "十六进制数据字符串格式，用于描述CAN协议的数据。",
                "type": "str",
                "default": "0000000000000000",
                "range": []
            },
            "services": {
                "describe": "UDS服务数据设定。",
                "type": "uds",
                "default": [{'service': 0x01, 'sub': 0x0d}, {'service': 0x09, 'sub': 0x02},
                            {'service': 0x2F, 'sub': 0x03, 'data': [7, 3, 0, 0]}],
                "range": []
            },
            "mode": {
                "describe": "发送包的模式。[CAN,ISOTP,UDS]。",
                "type": "str",
                "default": "CAN",
                "range": ['CAN', 'ISOTP', 'UDS']
            },
            "range": {
                "describe": "要发送的CANID范围。",
                "type": "ipair",
                "default": [0, 1000],
                "range_min": [],
                "range_man": []
            },
            "delay": {
                "describe": "发送数据的延迟。",
                "type": "int",
                "default": 0,
                "range": []
            },
            "padding": {
                "describe": "用于UDS与ISOTP协议做填充数据，一般不使用。",
                "type": "int",
                "default": 0,
            },
            "shift": {
                "describe": "仅用于UDS协议做偏移量使用。",
                "type": "int",
                "default": 8,
            }
        }
    }

    def do_init(self, params):
        self.describe = ping.help.get('describe', ping.name)
        self._bus = 'ping'
        self._queue_messages = []

        self._last = 0
        self._full = 1

    def get_status(self):
        status = "当前状态: " + str(self._active) + \
            "\n在队列中的数据帧: " + str(len(self._queue_messages))
        return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=status)

    def do_ping(self, params):
        if not self._queue_messages:
            self._active = False
            self.do_start(params)
            return None

        return self._queue_messages.pop()

    @staticmethod
    def _get_iso_mode(args):
        ret = 0
        mode = args.get('mode', '').lower()
        if mode.startswith('iso'):
            ret = 1
        elif mode.startswith('uds'):
            ret = 2
        return ret

    # FIXME: This should be moved to a util function somewhere else (like util.py) or moved to the parent class since
    # it will always be used to process range user-supplied parameter.
    @staticmethod
    def _get_range(data):
        """Get the lower and upper bounds of the range.

        :param object data: Data to convert to a range. Could be int, str or list.

        :return: Tuple of (start, end).
        :rtype: tuple
        """
        new_range = []
        if isinstance(data, int):
            new_range = [data]
        elif isinstance(data, str):
            # Could be '0-2000' or '0x0 - 0x700', where in the second case the range is specified in hexa.
            new_range = range(*[int(boundary, 0)
                              for boundary in map(str.strip, data.split('-'))])
        elif isinstance(data, list):
            new_range = data
        return new_range

    def do_start(self, args):
        self._queue_messages = []
        self._last = time.clock()

        data = [0, 0, 0, 0, 0, 0, 0, 0]
        if 'body' in args:
            data = list(bytes.fromhex(args['body']))

        iso_mode = self._get_iso_mode(args)

        padding = args.get('padding', None)
        shift = int(args.get('shift', 0x8))

        if 'range' not in args:
            self.error("没有范围指定")
            self._active = False
            return
        start, end = args.get('range', [0, 0])
        for i in range(int(start), int(end)):
            if iso_mode == 1:
                iso_list = ISOTPMessage.generate_can(i, data, padding)
                iso_list.reverse()
                self._queue_messages.extend(iso_list)
            elif iso_mode == 0:
                self._queue_messages.append(
                    CANMessage.init_data(i, len(data), data[:8]))
            elif iso_mode == 2:
                for service in args.get('services', []):
                    uds_m = UDSMessage(shift, padding)
                    for service_id in self._get_range(service['service']):
                        subservice_ids = service.get('sub', None)
                        if subservice_ids is None:
                            subservice_ids = [None]
                        else:
                            subservice_ids = self._get_range(subservice_ids)
                        for subservice_id in subservice_ids:
                            iso_list = uds_m.add_request(
                                i, service_id, subservice_id, service.get('data', []))
                            iso_list.reverse()
                            self._queue_messages.extend(iso_list)
        self._full = len(self._queue_messages)
        self._last = 0

    def do_effect(self, can_msg, args):
        #
        # 此模块的命令，仅有发送数据包的状态，仅在非CAN包的情况下进行调用
        #
        d_time = float(args.get('delay', 0))
        if not can_msg.CANData:
            if d_time > 0:
                if time.clock() - self._last >= d_time:
                    self._last = time.clock()
                    can_msg.CANFrame = self.do_ping(args)
                else:
                    can_msg.CANFrame = None
            else:
                can_msg.CANFrame = self.do_ping(args)

            if can_msg.CANFrame and not can_msg.CANData:
                can_msg.CANData = True
                can_msg.bus = self._bus
                self._last += 1
                self._status = self._last / (self._full / 100.0)
        return can_msg
