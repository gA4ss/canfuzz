import time
import struct
import socket
import threading
import traceback
import socketserver

from frame.message.can import CANMessage
from frame.kernel.module import CANModule, Command
from frame.stream.cmdres import CmdResult, CMDRES_ERROR, CMDRES_NULL, CMDRES_INT, CMDRES_STR, CMDRES_TAB, CMDRES_OBJ


class CustomTCPClient:

    def __init__(self, conn):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._stop_handle = False
        self.socket.settimeout(5.0)
        self.socket.connect(conn)
        self.CANList_in = []
        self.CANList_out = []
        self._access_in = threading.Event()
        self._access_out = threading.Event()
        self._thread_is_stoped = False
        self._thread = threading.Thread(target=self.handle)

        self._thread.daemon = True
        self._thread.start()

    def handle(self):
        """
        线程函数，循环处理数据。
        """
        self._thread_is_stoped = False
        while self._stop_handle is False:
            try:
                # 发送头协议 c\x01\x00\x00
                self.socket.sendall(b'c\x01\x00\x00')
                inc_header = self.socket.recv(4)            # 获取服务器的回应
                # 等待回应,前两个字节为'c\x02',如果不是则协议错误
                if inc_header[0:2] != b'c\x02':
                    self.selfx.error("协议头错误")
                    continue
                else:
                    # 如果正确则解包随后的数据，后两个字节是数据包的数量
                    ready = struct.unpack("!H", inc_header[2:4])[0]
                    inc_size = 16 * ready   # 每16个字节为一组
                    if ready > 0:
                        inc_data = self.socket.recv(inc_size)  # 获取数据
                        idx = 0
                        # 循环接收数据
                        while ready != 0:
                            packet = inc_data[idx:idx + 16]
                            # 如果接收到的数据前3个并非'ct\x03'，则协议出错,这个表明是CAN包
                            if packet[0:3] != b'ct\x03':
                                self.selfx.error('客户端获取错误协议')
                                break
                            else:
                                # 分别从packet中取出 fid,flen,fdata
                                fid = struct.unpack("!I", packet[3:7])[0]
                                flen = packet[7]
                                fdata = packet[8:16]
                                # 检查队列是否在使用，如果在使用则停止一段时间
                                while self._access_in.is_set():
                                    time.sleep(0.0001)
                                self._access_in.set()
                                # 写入列表
                                self.CANList_in.append(
                                    CANMessage.init_data(int(fid), flen, fdata)
                                )
                                self._access_in.clear()
                            # 下一组
                            idx += 16
                            ready -= 1
                #
                # 从这里开始是处理发送的字段，首先会检测输出队列是否在使用
                #
                while self._access_out.is_set():
                    time.sleep(0.0001)
                self._access_out.set()
                # 获取当前输出队列的CAN包的个数
                ready = len(self.CANList_out)
                if ready > 0:
                    #
                    # 进行组包
                    # 1. 'c\x04' + CAN包的个数
                    # 2. 'ct\x05' + CAN包数据
                    #
                    sz = struct.pack("!H", ready)
                    send_msg = b'c\x04' + sz
                    self.socket.sendall(send_msg)
                    send_msg = b''
                    for can_msg in self.CANList_out:
                        # 16字节，CAN包数据如果字段没有占用满，则使用0补齐
                        send_msg += b'ct\x05' + (b'\x00' * (4 - len(can_msg.frame_raw_id))) + can_msg.frame_raw_id + \
                            can_msg.frame_raw_length + can_msg.frame_raw_data + \
                            (b'\x00' * (8 - can_msg.frame_length))
                    if ready > 0:
                        self.socket.sendall(send_msg)
                        self.CANList_out = []

                self._access_out.clear()
            except Exception as e:
                self._thread_is_stoped = True
                time.sleep(0.01)        # 保证线程停止后再抛出异常
                self.selfx.fatal_error('TCPClient: 接收回应错误', e)
        self._thread_is_stoped = True

    def write_can(self, can_frame):
        """
        发送CAN数据,使用_access_out.is_set()检查CANList是否被占用
        """
        while self._access_out.is_set():
            time.sleep(0.0001)
        self._access_out.set()
        self.CANList_out.append(can_frame)
        self._access_out.clear()

    def read_can(self):
        """
        读取CAN总线数据
        """
        if len(self.CANList_in) > 0:
            while self._access_in.is_set():
                time.sleep(0.0001)
            self._access_in.set()
            msg = self.CANList_in.pop(0)
            self._access_in.clear()
            return msg
        else:
            return None

    def close(self):
        self._stop_handle = True
        while (self._access_out.is_set() or self._access_in.is_set()):
            time.sleep(0.0001)
        while self._thread_is_stoped is False:
            time.sleep(0.0001)
        time.sleep(0.1)
        self._thread._stop()
        self.socket.close()


class CustomTCPServer(socketserver.ThreadingTCPServer):

    # 设置允许TCP端口复用，在TIME_WAIT状态下可用
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):

        super().__init__(server_address, RequestHandlerClass)
        # self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.CANList_in = []
        self.CANList_out = []
        self._access_in = threading.Event()
        self._access_out = threading.Event()
        self.socket.settimeout(5.0)
        self.prt = ""
        self._stop_handle = False
        self.lasted_time = time.time()

    def write_can(self, can_frame):
        self.selfx.info("服务器执行命令发送数据 : {}".format(can_frame.get_text()))
        while self._access_out.is_set():
            time.sleep(0.0001)
        self._access_out.set()
        # if time.time() - self.lasted_time > 10:
        #     if len(self.CANList_out) > 1000:
        #         self.CANList_out = []
        #     else:
        #         self.CANList_out.append(can_frame)
        self.CANList_out.append(can_frame)
        self._access_out.clear()

    def read_can(self):
        if len(self.CANList_in) > 0:
            while self._access_in.is_set():
                time.sleep(0.0001)
            self._access_in.set()
            msg = self.CANList_in.pop(0)
            self._access_in.clear()
            return msg
        else:
            return None

    def close(self):
        self._stop_handle = True


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):

    def handle(self):
        # self.request is the TCP socket connected to the client
        self.server.selfx.info("TCP2CAN 链接到 " + str(self.server.prt))

        self.server._access_in.clear()
        self.server._access_out.clear()

        while self.server.selfx._server._stop_handle is False:
            # 获取前四个字节的头
            data = self.request.recv(4)

            # 判断第一个字节是否是'c'
            if data[0:1] == b'c':
                if data[1] == 1:
                    while self.server._access_out.is_set():
                        time.sleep(0.0001)
                    self.server._access_out.set()
                    ready = len(self.server.CANList_out)

                    sz = struct.pack("!H", ready)
                    send_msg = b'c\x02' + sz
                    self.request.sendall(send_msg)
                    send_msg = b''
                    for can_msg in self.server.CANList_out:
                        # 16 字节
                        send_msg += b'ct\x03' + (b'\x00' * (4 - len(can_msg.frame_raw_id))) + can_msg.frame_raw_id + \
                            can_msg.frame_raw_length + can_msg.frame_raw_data + \
                            (b'\x00' * (8 - can_msg.frame_length))
                    if ready > 0:
                        self.request.sendall(send_msg)
                        self.server.CANList_out = []

                    self.server._access_out.clear()
                elif data[1] == 4:
                    ready = struct.unpack("!H", data[2:4])[0]
                    inc_size = 16 * ready
                    if ready > 0:
                        inc_data = self.request.recv(inc_size)
                        idx = 0
                        while ready != 0:
                            packet = inc_data[idx:idx + 16]
                            if packet[0:3] != b'ct\x05':
                                self.server.selfx.error('服务器获取错误协议')
                                break
                            else:
                                fid = struct.unpack("!I", packet[3:7])[0]
                                flen = packet[7]
                                fdata = packet[8:16]
                                while self.server._access_in.is_set():
                                    time.sleep(0.0001)
                                self.server._access_in.set()
                                self.server.CANList_in.append(
                                    CANMessage.init_data(int(fid), flen, fdata)
                                )
                                self.server._access_in.clear()

                            idx += 16
                            ready -= 1


class hw_TCP2CAN(CANModule):
    name = "TCP2CAN设备驱动"
    help = {
        "describe": "此模块用来实现一个TCP的 客户端/服务器来传输CAN帧。",
        "init_parameters": {
            "mode": {
                "describe": "是服务器还是客户端。",
                "type": "str",
                "default": "server",
                "range": ["server", "client"]
            },
            "port": {
                "describe": "链接或者监听的端口。",
                "type": "int",
                "default": 19780
            },
            "address": {
                "describe": "远程或者本地监听地址。",
                "type": "str",
                "default": "127.0.0.1"
            },
        },
        "action_parameters": {
            "action": {
                "describe": "动作属性，读或者写。",
                "type": "str",
                "default": "read",
                "range": ["read", "write"]
            }
        }
    }

    version = 1.0

    def get_status(self):
        status = "接收: " + str(len(self._server.CANList_in)) + \
            "是否可接收: " + str(self._server._access_in.is_set()) + "\n" + \
            " 发送: " + str(len(self._server.CANList_out)) + \
            "是否可发送:" + str(self._server._access_out.is_set()) + "\n"
        return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=status)

    def do_start(self, params):
        if self._server is None:
            self.info('启动 : ' + str(self._mode))
            if self._mode == 'server':
                self._server = CustomTCPServer(
                    (self._HOST, self._PORT), ThreadedTCPRequestHandler)
                self._server.prt = self._PORT
                self._thread = threading.Thread(
                    target=self._server.serve_forever)
                self._thread.daemon = True

                self._thread.start()
            else:
                self._server = CustomTCPClient((self._HOST, self._PORT))

            #
            # 这里在客户端与服务器的类对象中使用selfx来访问此类
            #
            self._server.selfx = self

    def do_stop(self, params):
        if self._server is not None:
            self.info('停止 : ' + str(self._mode))
            #
            # 客户端与服务器都需要调用close()函数, 如果是服务器则还需要调用
            # 一系列的关闭流程
            #
            self._server.close()
            if self._mode == 'server':
                self._server.server_close()
                self._server.shutdown()
                self._thread._stop()
            self._server = None

    def do_init(self, params):

        self.describe = hw_TCP2CAN.help.get('describe', hw_TCP2CAN.name)
        self._bus = 'TCP2CAN'

        #
        # 初始化参数
        #
        self._server = None
        self._mode = params.get('mode', 'server')
        if not self._mode or self._mode not in ['server', 'client']:
            self.fatal_error('获取模式失败')

        self._HOST = params.get('address', '127.0.0.1')
        self._PORT = int(params.get('port', 19780))
        self._bus = self._mode + ":" + self._HOST + ":" + str(self._PORT)

        self.commands['write'] = Command(
            "直接发送CAN数据帧, 类似如下字符串形式: 13:8:1122334455667788", 1, " <数据帧字符串> ", self.dev_write, True)
        self.do_start(params)
        return 0

    def dev_write(self, line):
        fid = line.split(":")[0]
        length = line.split(":")[1]
        data = line.split(":")[2]
        can_msg = CANMessage.init_data(int(fid, 0), int(
            length), bytes.fromhex(data)[:int(length)])
        self._server.write_can(can_msg)
        return CmdResult(cmdline='write ' + line, describe="网络发送", result_type=CMDRES_STR, result=can_msg.get_text())

    def do_effect(self, can_msg, args):
        if args.get('action', 'read') == 'read':
            can_msg = self.do_read(can_msg)
        elif args.get('action', 'read') == 'write':
            self.do_write(can_msg)
        else:
            action = str(args.get('action', 'None'))
            self.fatal_error('命令 ' + action + ' 未实现')
        return can_msg

    def do_write(self, can_msg):
        if can_msg.CANData:
            self._server.write_can(can_msg.CANFrame)
        return can_msg

    def do_read(self, can_msg):
        if not can_msg.CANData:
            can_frame = self._server.read_can()
            if can_frame:
                can_msg.CANData = True
                can_msg.CANFrame = can_frame
                can_msg.bus = self._bus
        return can_msg
