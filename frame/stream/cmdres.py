# -*- coding: utf-8 -*-

CMDRES_ERROR  = -1
CMDRES_NULL   = 0
CMDRES_INT    = 1
CMDRES_STR    = 2
CMDRES_TAB    = 3
CMDRES_OBJ    = 4

class CmdResult:
  def __init__(self, cmdline="", result_type=CMDRES_NULL, describe="", result=None, last_error=0, e=None):
    self.last_error = last_error                # 错误代码
    self.e = e                                  # 异常信息
    self.cmdline = cmdline                      # 执行的命令
    self.describe = describe                    # 描述
    self.result = result                        # 结果

    # 结果的类型
    self.result_type = result_type if self.last_error >= 0 else CMDRES_ERROR
