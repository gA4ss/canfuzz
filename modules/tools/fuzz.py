# -*- coding: utf-8 -*-
import time

from frame.message.can import CANMessage
from frame.message.isotp import ISOTPMessage
from frame.kernel.module import CANModule
from frame.stream.cmdres import CmdResult, CMDRES_STR


class fuzz(CANModule):
    name = "FUZZ"
    version = 1.0
    help = {
        "describe": "当前模块用于随机发送单字节的随机数据包到CAN总线上。",
        # "init_parameters": None,
        "action_parameters": {
            "id": {
                "describe": "要进行发送的的CANID列表。",
                "type": "list,int,ipair",
                "default": [0, 1, 2, 111, 333, [334, 339]]
            },
            "mode": {
                "describe": "包模式，仅可以是ISOTP。",
                "type": "str",
                "default": "ISOTP",
                "range": ['ISOTP']
            },
            "data": {
                "describe": "基础数据，index字段范围不能超过此数据模板。",
                "type": "list,int"
            },
            "index": {
                "describe": "要进行改变，基础数据的索引。不能超过data的长度范围",
                "type": "list,int"
            },
            "bytes": {
                "describe": "要进行填充数值的范围，用此数据来填充data模板",
                "type": "ipair",
                "default": 0
            },
            "delay": {
                "describe": "发送数据的延迟。",
                "type": "int",
                "default": 0,
                "range": []
            }
        }
    }

    def do_init(self, params):
        self.describe = fuzz.help.get('describe', fuzz.name)
        self._bus = 'fuzz'
        self._queue_messages = []
        self._last = 0
        self._full = 1

    def get_status(self):
        status = "当前状态: " + str(self._active) + \
            "\n在队列中的数据帧: " + str(len(self._queue_messages))
        return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=status)

    def fuzz(self, fuzz_list, idf, data, bytes_to_fuzz, level, iso_mode):
        """
        fuzz_list : bytes队列, range(0, 0x20)
        idf : CANID。
        data : 基础数据。
        bytes_to_fuzz : 要FUZZ的索引。
        level : data的长度。
        iso_mode : 是否是ISOTP协议。

        最终构造出要给数据包
        """
        messages = []
        x_data = [] + data
        #
        # 遍历bytes参数列表,构造fuzz数据列表
        # fuzz_list默认是0-255
        #
        for byte in fuzz_list:
            #
            # bytes_to_fuzz是一个基础数据索引列表，如果不指定，则选定整个基础数据范围
            # level是当前fuzz要填充改变的索引(从后向前进行改变基础数据)
            #
            x_data[bytes_to_fuzz[level]] = byte

            #
            # 如果level不为0，则继续递归进行构造
            # 这里依次缩减level
            #
            if level != 0:
                messages.extend(self.fuzz(fuzz_list, idf, x_data,
                                bytes_to_fuzz, level - 1, iso_mode))
            else:
                #
                # 到了递归的最后一层，则查看iso_mode然后构造消息
                #
                if iso_mode == 1:
                    iso_list = ISOTPMessage.generate_can(idf, x_data)
                    iso_list.reverse()
                    messages.extend(iso_list)
                else:
                    #
                    # 构造原始的CAN包
                    #
                    messages.append(CANMessage.init_data(
                        idf, len(x_data), x_data[:8]))
        return messages

    def do_start(self, args):
        self._last = time.clock()
        self._queue_messages = []

        # 在mode仅可以使用ISOTP
        iso_mode = 1 if args.get('mode') in [
            'ISO', 'iso', 'ISOTP', 'isotp'] else 0
        if 'id' in args:
            #
            # 遍历所有CANID
            #
            for z in args['id']:
                # 如果是[2,10]，这样的形式，则表示一个范围
                if isinstance(z, list) and len(z) == 2:
                    x = list(range(z[0], z[1]))
                elif isinstance(z, int):
                    x = [z]
                else:
                    break

                # 遍历CANID
                for i in x:
                    # 获取数据
                    _body2 = list(args.get('data', []))

                    # 生成索引队列,假如'data'中为[45, 78]，则 bytes_to_fuzz = [0, 1]
                    bytes_to_fuzz = args.get('index', range(0, len(_body2)))

                    # 获取FUZZ数据, 这里假设bytes = [0, 0x20]
                    bytez_for_fuzz = args.get('bytes', None)

                    #
                    # 构造一个列表数据
                    # 如果bytes为空则采用一个列表range(0, 255)的字节列表
                    # 如果bytes不为空且是一个列表，则直接使用
                    # 如果bytes不为空且是一个元组，则使用一个范围
                    #
                    if not bytez_for_fuzz:
                        fuzz_list = range(0, 255)
                    elif isinstance(bytez_for_fuzz, list):
                        fuzz_list = bytez_for_fuzz
                    elif isinstance(bytez_for_fuzz, tuple):
                        fuzz_list = range(bytez_for_fuzz[0], bytez_for_fuzz[1])
                    else:
                        fuzz_list = range(0, 255)
                    levels = len(bytes_to_fuzz) - 1
                    # 合成fuzz数据
                    self._queue_messages.extend(
                        self.fuzz(fuzz_list, i, _body2, bytes_to_fuzz, levels, iso_mode))
        self._full = len(self._queue_messages)
        self._last = 0

    def do_effect(self, can_msg, args):
        if not self._queue_messages:
            self._active = False
            self.do_start(args)
        elif not can_msg.CANData:
            d_time = float(args.get('delay', 0))
            if d_time > 0:
                if time.clock() - self._last >= d_time:
                    self._last = time.clock()
                    can_msg.CANFrame = self._queue_messages.pop()
                    can_msg.CANData = True
                    can_msg.bus = self._bus
                    self._last += 1
                    self._status = self._last / (self._full / 100.0)
            else:
                can_msg.CANFrame = self._queue_messages.pop()
                can_msg.CANData = True
                can_msg.bus = self._bus
                self._last += 1
                self._status = self._last / (self._full / 100.0)
        return can_msg
