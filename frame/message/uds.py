# -*- coding: utf-8 -*-
import collections

from frame.message.isotp import ISOTPMessage


class UDSMessage:

    """
    UDS protocols support
    UDS协议即ISO14229,是Unified Diagnostic Services，统一诊断服务，是诊断服务的规范化标准，
    比如读取故障码应该向ecu发什么指令，读数据流又是发什么指令。OBD是关注车辆售后实时排放的理念形成的行业规范，
    而UDS是诊断服务的统一化规范，只是应用层的规范。UDS(Unified diagnostic services)，与OBD最大的区别就在于“Unified”上，
    它是面向整车所有ECU(电控单元)的，而OBD是面向排放系统ECU的。单说UDS而言，它只是一个应用层协议(ISO 14229-1)，
    所以它既可以在CAN线上实现,甚至也能在Ethernet上实现(DoIP, Diagnostic over Internet protocol)。
    并且，UDS提供的是一个诊断服务的基本框架，主机厂和零部件供应商可以根据实际情况选择实现其中的一部分或是自定义出一些私有化的诊断服务来，
    所以基于UDS协议的诊断又常常被称为Enhanced diagnosic(增强型诊断)，UDS不是法规要求的，没有统一实现标准，
    其优势在于方便生产线检测设备的开发，同时更大的方便了售后维修保养和车联网的功能实现。
    """

    services_base = {
        0x01: {
            None: 'Powertrain',
            0x0d: 'Req Current Powertrain'
        },
        0x03: {
            None: 'Req Emission-Related Diag. Trb. Codes'
        },
        0x04: {
            None: 'Clear/Reset Emsission Diag. Trb. Codes'
        },
        0x07: {
            None: 'Req Emission-Related Diag. Trb. Codes during last cycle'
        },
        0x09: {
            None: 'Vehicle info',
            0x02: 'Req Vehicle info (VIN)',
            0x04: 'Req ID',
            0x06: 'Veryf. num',
            0x0A: 'ECU name',
            0x0D: 'Vehicle info'
        },
        0x0A: {
            None: 'Req Emission-Related Diag. Trb. Codes with perm status'
        },
        0x10: {
            None: 'Diagnostic Session Control',
            0x01: 'Enter diag session',
            0x03: 'Extended Diag Session'
        },
        0x11: {
            None: 'Reset',
            0x01: 'ECU HARD Reset',
            0x03: 'Soft reset',
            0x02: 'ECU Reset'},
        0x19: {
            None: 'DTC unknws',
            0x01: 'Report num of DTC by status',
            0x02: 'Report DTC by status',
            0x03: 'Report DTC Snapshot ID'
        },
        0x20: {
            None: 'Restart communication'
        },
        0x27: {
            None: 'Security Access',
            0x01: 'Seed request',
            0x02: 'Resposne'
        },
        0x28: {None: 'Communication Control'},
        0x3E: {None: 'Tester', 0x01: "Tester present"},
        0x83: {None: 'Access Timing Parameters'},
        0x84: {None: 'Secured Data Transmission'},
        0x85: {None: 'Control DTC Settings'},
        0x86: {None: 'Response On Event'},
        0x87: {None: 'Link Control'},
        0x22: {None: 'Read Data By Identifier'},
        0x23: {None: 'Read Memory By Address'},
        0x24: {None: 'Read Scaling Data By Identifier'},
        0x2A: {None: 'Read Data By Identifier Periodic'},
        0x2C: {None: 'Dynamically Define Data Identifier'},
        0x2E: {None: 'Write Data By Identifier'},
        0x3D: {None: 'Write Memory By Address'},
        0x14: {None: 'Clear Diagnostic Information'},
        0x2F: {None: 'Input Output Control By Identifier'},
        0x31: {None: 'Routine Control'},
        0x34: {None: 'Request Download'},
        0x35: {None: 'Request Upload'},
        0x36: {None: 'Transfer Data'},
        0x37: {None: 'Request Transfer Exit'},
        0x38: {None: 'Request File Transfer'}
    }

    error_responses = {
        0x10: 'General reject',
        0x11: 'Service not supported',
        0x12: 'Subfunction not supported',
        0x13: 'Incorrect message length or invalid format',
        0x14: 'Response too long',
        0x21: 'Busy repeat request',
        0x22: 'Condition not correct',
        0x24: 'Request sequence error',
        0x25: 'No response from subnet component',
        0x26: 'Failure prevents execution of requested action',
        0x31: 'Request out of range',
        0x33: 'Security access denied',
        0x35: 'Invalid key',
        0x36: 'Exceeded number of attempts',
        0x37: 'Required time delay not expired',
        0x39: 'Reserved by extended data link security document',
        0x3A: 'Reserved by extended data link security document',
        0x3B: 'Reserved by extended data link security document',
        0x3C: 'Reserved by extended data link security document',
        0x3D: 'Reserved by extended data link security document',
        0x3E: 'Reserved by extended data link security document',
        0x3F: 'Reserved by extended data link security document',
        0x40: 'Reserved by extended data link security document',
        0x41: 'Reserved by extended data link security document',
        0x42: 'Reserved by extended data link security document',
        0x43: 'Reserved by extended data link security document',
        0x44: 'Reserved by extended data link security document',
        0x45: 'Reserved by extended data link security document',
        0x46: 'Reserved by extended data link security document',
        0x47: 'Reserved by extended data link security document',
        0x48: 'Reserved by extended data link security document',
        0x49: 'Reserved by extended data link security document',
        0x4A: 'Reserved by extended data link security document',
        0x4B: 'Reserved by extended data link security document',
        0x4C: 'Reserved by extended data link security document',
        0x4D: 'Reserved by extended data link security document',
        0x4E: 'Reserved by extended data link security document',
        0x4F: 'Reserved by extended data link security document',
        0x70: 'Upload/download not accepted',
        0x71: 'Transfer data suspended',
        0x72: 'General programming failure',
        0x73: 'Wrong block sequence counter',
        0x78: 'Request correctly received but response is pending',
        0x7E: 'Subfunction not supported in active session',
        0x7F: 'Service not supported in active session'
    }

    def __init__(self, _shift=0x08, _padding=None):  # Init Session
        self.sessions = {}
        self.shift = _shift
        self.padding = _padding

    def start_session(self, _id):
        if _id in self.sessions:
            return -1
        else:
            self.sessions[_id] = {}
            return 1

    def delete_session(self, _id):
        if _id not in self.sessions:
            return -1
        else:
            del self.sessions[_id]
            return 1

    def check_status(self, _input_message):
        if len(_input_message.message_data) >= 2 and _input_message.message_id in self.sessions and _input_message.message_data[0] in self.sessions[_input_message.message_id] \
                and _input_message.message_data[1] in self.sessions[_input_message.message_id][_input_message.message_data[0]]:
            return -1
        elif len(_input_message.message_data) >= 2 and (_input_message.message_id - self.shift) in self.sessions and (_input_message.message_data[0] - 0x40) in self.sessions[_input_message.message_id - self.shift] and\
                _input_message.message_data[1] in self.sessions[_input_message.message_id - self.shift][_input_message.message_data[0] - 0x40]:
            return 2  # RESPONSE
        elif (_input_message.message_id - self.shift) in self.sessions and (_input_message.message_data[0] - 0x40) in self.sessions[_input_message.message_id - self.shift]:
            return 4  # RESPONSE WITHOUT SUB
        elif len(_input_message.message_data) > 2 and (_input_message.message_id - self.shift) in self.sessions and _input_message.message_data[0] == 0x7f and \
                _input_message.message_data[1] in self.sessions[_input_message.message_id - self.shift]:
            return 3  # ERROR
        elif _input_message.message_id not in self.sessions or _input_message.message_data[0] not in self.sessions[_input_message.message_id] or \
                len(_input_message.message_data) == 1 or (len(_input_message.message_data) > 1 and _input_message.message_data[1] not in self.sessions[_input_message.message_id][_input_message.message_data[0]]):
            return 0  # NEW Request
        else:
            return -3

    # Method to handle messages ISO TP messages
    def handle_message(self, _input_message):
        uds_type = self.check_status(_input_message)
        if uds_type == 2:  # Possible response came
            sts = self.sessions[_input_message.message_id -
                                self.shift][_input_message.message_data[0] - 0x40][_input_message.message_data[1]]['status']
            if sts == 0:  # Ok, now we have Response... looks like
                return self.add_raw_response(_input_message)
            return False
        elif uds_type == 3:  # Maybe error
            return self.add_raw_response(_input_message)
        elif uds_type == 4:  # Response without sub-function
            sts = self.sessions[_input_message.message_id -
                                self.shift][_input_message.message_data[0] - 0x40][0x1ff]['status']
            if sts == 0:  # Ok, now we have Response... looks like
                return self.add_raw_response(_input_message)
        elif uds_type == 0:  # New service request                                       # New Service request and new ID
            self.add_raw_request(_input_message)
            return True

        return False

    def add_request(self, _id, _service, _subcommand, _data):
        if not _data:
            _data = []

        if _subcommand is None or _subcommand < 0:
            _subcommand = []
        else:
            _subcommand = [_subcommand]
        byte_data = [_service] + _subcommand + _data
        return ISOTPMessage.generate_can(_id, byte_data, self.padding)

    def add_raw_response(self, _input_message):
        response_id = _input_message.message_id - self.shift
        if len(_input_message.message_data) >= 2:
            if response_id in self.sessions:
                response_byte = _input_message.message_data[0] - 0x40
                sub_command = _input_message.message_data[1]
                # Error
                if len(_input_message.message_data) >= 3 and _input_message.message_data[0] == 0x7f and _input_message.message_data[1] in self.sessions[response_id]:

                    x = _input_message.message_data[1]
                    lst = self.sessions[response_id][x].items()
                    y = None
                    for sub, bd in lst:
                        if bd['status'] == 0:
                            y = sub
                            break
                        if sub > 0xff:
                            break
                    if y is not None:
                        self.sessions[response_id][x][y]['response']['id'] = _input_message.message_id
                        self.sessions[response_id][x][y]['response']['data'] = None
                        self.sessions[response_id][x][y]['status'] = 2
                        self.sessions[response_id][x][y]['response']['error'] = self.error_responses.get(
                            _input_message.message_data[2], "UNK ERROR")

                        if y < 0x1ff:
                            self.sessions[response_id][x][0x1ff]['response']['id'] = _input_message.message_id
                            self.sessions[response_id][x][0x1ff]['response']['data'] = None
                            self.sessions[response_id][x][0x1ff]['status'] = 2
                            self.sessions[response_id][x][0x1ff]['response']['error'] = self.error_responses.get(
                                _input_message.message_data[2], "UNK ERROR")
                        return True
                # Response
                elif response_byte in self.sessions[response_id] and sub_command in self.sessions[response_id][response_byte]:
                    self.sessions[response_id][response_byte][sub_command]['response']['id'] = _input_message.message_id
                    self.sessions[response_id][response_byte][sub_command]['response']['data'] = _input_message.message_data[2:]
                    self.sessions[response_id][response_byte][sub_command]['status'] = 1
                    self.sessions[response_id][response_byte][0x1ff]['status'] = 3
                    return True
                elif response_byte in self.sessions[response_id] and sub_command not in self.sessions[response_id][response_byte]:
                    for sub, req in self.sessions[response_id][response_byte].items():
                        if sub == 0x1ff and req['status'] == 0:
                            req['response']['id'] = _input_message.message_id
                            req['response']['data'] = _input_message.message_data[1:]
                            req['status'] = 1
                            break
                    return True
        return False
