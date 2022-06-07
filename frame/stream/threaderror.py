import sys
import traceback
from threading import Thread


class MyThread(Thread):

  def __init__(self, funcName, *args):
    Thread.__init__(self)
    self.args = args
    self.funcName = funcName
    self.exitcode = 0
    self.exception = None
    self.exc_traceback = ''

  def run(self):
    try:
      self._run()
    except Exception as e:
      # 如果线程异常退出，将该标志位设置为1，正常退出为0
      self.exitcode = 1
      self.exception = e
      # 在改成员变量中记录异常信息
      self.exc_traceback = ''.join(traceback.format_exception(*sys.exc_info()))
      print(self.exception)
      print(self.exc_traceback)

  def _run(self):
    try:
      self.funcName(*(self.args))
    except Exception as e:
      raise e



