# ISO15765-2

UDS定义的是诊断服务，属于应用层的内容，实现诊断通信的底层总线技术有很多，比如CAN，LIN，Ethernet，Flexray等，由于法规强制的OBD接口是CAN总线的，所以绝大多数场景中诊断都是基于CAN实现的。这就带来了一个问题，classical CAN总线物理层的每一帧只能传输8个字节，CAN FD第帧最多能传输64个字节，那么如果UDS产生的一条诊断命令超过了8个字节，在CAN总线上一帧是承载不了的，就需要进行分包，这也是DoCAN(Diagnose over CAN)要解决的最主要的问题。

为了实现诊断命令的分包传输，15765-2总共定义了4种类型的帧结构，每种帧结构以数据域的前两个或一个字节来标识（取决于帧类型）。这四种类型分别是：

* SingleFrame
* FirstFrame
* ConsecutiveFrame
* FlowControl

其中SingleFrame用于长度不超过7个字节的诊断命令或响应。FirstFrame，ConsecutiveFrame，FlowControl用于传输长度大于7个字节的诊断命令或响应。每个诊断帧的第一个字节的高4bit用于描述该帧的类型，即该帧属于上述四种中的哪一种。

![isotp1](../canfuzz/img/isotp1.png)

SingleFrame用于下面这种简单的场景：当诊断报文长度小于等于7时，再加上一个字节的PCI控制信息就是小于等于8，可以在一帧CAN报文上传输，所以不需要进行分包。此时数据域的第一个字节高4bit值为0000，标识这是一个帧SingleFrame，低4bit是SF_DL，即DataLength，描述后面有几个字节。如果有没有使用的字节，通常要用0x55或0xAA来填充，因为这两个值的二进制表述其实就是01010101和10101010，这样在CAN总线上可以让信号跳变得更频繁一些，不会出现长时间电平不变的情况。

![isotp2](../canfuzz/img/isotp2.jpg)

如果一帧CAN报文无法承载一条诊断报文，则需要按照下面的流程进行分包发送：


![isotp3](../canfuzz/img/isotp3.jpg)

首先，发送端要以一个FirstFrame开启通信，告诉接收端还有后续的内容要发，FirstFrame使用前两个字节作为PCI信息，第一个字节高4bit为0001，标识这是一个FirstFrame，低4bit加上第二个字节用于描述总共发送的数据长度是多少（包括在FirstFrame中和在ConsecutiveFrame中的所有字节数）。

之后接收端发送FlowControl，告诉发送端能以什么样的速度来发送数据，FlowControl第一字节的高4bit为0011，低4bit为FS，即FlowStatus，第二个字节为BS(BlockSize)，第三个字节为STmin（SeperateTime）。FlowControl有0，1，2三种状态，分别命名为ContinueToSend (CTS)，Wait (WT)，Overflow (OVFLW)。如果允许发送端继续发送ConsecutiveFrame，则FlowStatus=0；若要求发送端等一会再发送ConsecutiveFrame，则FlowStatus=1，再下次允许sender发送ConsecutiveFrame时，receiver再发一个FlowStatus=0的FlowControl。如果receiver因为资源问题无法接收sender发送的数据，则发送一个FlowStatus=2的FlowControl。

BS指示sender一次可以发送多少个ConsecutiveFrame，当发送ConsecutiveFrame数量达到BS时，需要receiver再次以一个FlowControl开启下一波的ConsecutiveFrame发送。

receiver根据自身的接收和处理能力使用STmin指示sender在发送ConsecutiveFrame时最小的时间间隔是多少，从而实现流控制。

ConsecutiveFrame就是承载FirstFrame无法完全承载的剩余数据了，它使用第一个字节用作PCI，高4bit为0010，低4bit用于标识ConsecutiveFrame的序列号，从1开始，每发送一次ConsecutiveFrame增加1。


# 不分段传输的诊断服务举例

|类型|字节1|字节2|字节3|字节4|字节5|字节6|字节7|字节8|
|---|-----|----|-----|----|----|-----|----|-----|
|request|**02**|10|03|55|55|55|55|55|
|response|**06**|50|03|00|32|01|F4|AA|


这是一个请求进入extended session的最简单的诊断服务，请求和应答都是SingleFrame，加粗的0标识了SingleFrame，后面的2和6表示了这条诊断报文拥有几个字节的数据。

# 分段传输的诊断服务举例

这是一个读取DTC的命令和应答。

|字节1|字节2|字节3|字节4|字节5|字节6|字节7|字节8|说明|
|----|-----|----|-----|----|----|-----|----|----|
|**03**|19|02|08|55|55|55|55|诊断仪发送的SingleFrame的request|
|**10**|**33**|59|02|19|01|00|07|ECU以FirstFrame开始传输的response|
|**30**|**00**|**00**|55|55|55|55|55|诊断仪发送的FlowControl|
|**21**|09|03|05|02|09|05|04|ECU发送的ConsecutiveFrame|
|**22**|07|09|05|06|06|09|05|ECU发送的ConsecutiveFrame|
|**23**|08|03|08|07|01|05|08|ECU发送的ConsecutiveFrame|
|**24**|07|01|06|08|07|01|0C|ECU发送的ConsecutiveFrame|
|**25**|08|07|01|0D|08|07|03|ECU发送的ConsecutiveFrame|
|**26**|07|09|08|01|01|09|09|ECU发送的ConsecutiveFrame|
|**27**|01|07|09|AA|AA|AA|AA|ECU发送的ConsecutiveFrame，此时传输结束|


在这里所有传输层相关的PCI信息都用粗体标识了。
注意当BS和STmin等于0时，表示接收端可以以最快的速度来接收数据，发送端可以一次发送的ConsecutiveFrame数量不受限制。