# 介绍

# 工作原理

# CAN总线协议介绍
这里的CAN总线协议是包括了底层实现逻辑的规则，本子模块的节点其实不用关心完整CAN协议的运行规则。只需要关心上层CAN协议的组装即可。

![can1](../canfuzz/img/can1.png)

在一个CAN总线上，存在CAN传输器，CAN控制器以及微控制器。CAN传输器以及控制器负责建立CAN协议的底层规则，微控制器负责提取CAN协议部分并提供给应用程序使用。

## 寻址方式

![can2](../canfuzz/img/can2.png)

CAN协议具备两种寻址方式一种是点对点传输，一种是广播传输。

## CAN过滤器

![can3](../canfuzz/img/can3.png)

在CAN网络上控制器部分，实现了过滤节点，将不属于自身以及自身不感兴趣的报文进行过滤。

## 冲突访问与仲裁

![can4](../canfuzz/img/can4.png)

上图可以看出总线上三个节点同时发送报文，但是是由优先级的，谁先发谁后发都是有一定规则。

### 优先级裁定

显性与机制

![can5](../canfuzz/img/can5.png)

不同节点同时发送数据，0为显性位，1位隐形位。将按照$1 & 0$的方式来确定发送优先级，仲裁优胜一方将继续发送并仲裁，另外一方将从发送节点转为接收节点，上图的节点A仲裁输了，将转换身份从发送节点转变为接收节点。随后B,C节点继续仲裁。

![can6](../canfuzz/img/can6.png)

#### 优先级
介于仲裁优先级判断方式，*CANID*越低月底优先级越高。

![can7](../canfuzz/img/can7.png)

## 报文协议

|名称|id长度|数据长度|常见度|
|----|-----|-------|-----|
|远程帧|11位|0|不常见，仅起请求作用|
|标准帧|11位|64位|常见|
|扩展帧|29位|64位|商用车常见|
|扩展远程帧|29位|0位|极少见|

![can8](../canfuzz/img/can8.png)

### 完整的一帧CAN报文

![can9](../canfuzz/img/can9.png)

|字段名称|解释|
|-------|---|

### 帧起始(*SOF*)

![can10](../canfuzz/img/can10.png)

发送节点设置起始为0，表示总线非空闲。接收节点与发送节点做硬同步。

### 标识(*Identifier*)

![can11](../canfuzz/img/can11.png)

### 远程传输请求(*RTR*)

![can12](../canfuzz/img/can12.png)

* 0 表示此帧是数据帧
* 1 表示此帧是远程帧

### 标识扩展(*Identifier Extension*)

![can13](../canfuzz/img/can13.png)

* 0 表示此帧是标准CAN报文
* 1 表示此帧是扩展CAN报文

#### 扩展帧的远程请求位(*SRR*)
在**扩展帧**状态下，*SRR*位与*RTR*的作用相同，都是表示此帧是否是一个远程帧。

### 保留位(*r*)
此位是存在标准帧上无意义，一般为0。在[CANFD](./modules/canfd.md)时对此进行重新定义。

### 数据长度与数据(*DLC*)

![can14](../canfuzz/img/can14.png)

此域总共4位可以表示0-15个整数。

* 0-8 表示实际数据段的字节数
* 9-15 表示数据段有8个字节

在[CANFD](./modules/canfd.md)中将数据段可以扩展到16个字节。

### 循环校验(*CRC*)

![can15](../canfuzz/img/can15.png)

发送节点计算从*SOF*到数据部分的校验值存入*CRC*字段中。接收节点按照同样的算法进行计算并与*CRC*中的值进行比较。

### 界定符位(*DEL*)

固定格式1，目前无实际意义。

### 应答位(*ACK*)

![can16](../canfuzz/img/can16.png)

接收节点会根据CRC得校验来设置*ACK*位来表明传输是否存在错误。

* 0 表示成功
* 1 表示失败

发送节点在发送帧之后会接收回应帧，如果*ACK*位为0，则表示发送数据成功，它会继续发送。如果为1，则发送节点会停止发送并再之后发送一个错误帧。

### 界定符位(*DEL*)

固定格式1，目前无实际意义。

### 结束位(*EOF*)

![can17](../canfuzz/img/can17.png)

*EOF*是连续的7个1表示一帧的结束。*ITM*是帧间隔，是三个111，紧跟在每帧的*EOF*后。

## 总线空闲

因为*DEL* + *EOF* + *ITM*一般是连续11个1。所以在检测到总线上存在连续11个1时，即表示总线空闲。当有节点检测到总线上连续11个1时既可以在总线上发送数据。

这里就造成了一个问题，如果在一帧报文中出现11个1的话如何解决。这里就涉及到位填充的机制了。

## 位填充

![can18](../canfuzz/img/can18.png)

在总线上，如果存在连续5个1或者0，那么会在随后插入一个相反的位。填充范围是从*SOF*开始到*CRC*结束。也就是说报文区域不可能存在连续相同的位。从上图可以看出，连续存在是包含了插入相反位的状况，也就是说连续五个1后，插入一个0，如果报文正常时跟的连续4个0，那么加上插入的0又构成连续5个0，那么就又插入了1。下图清晰的展示了这种情况。

![can19](../canfuzz/img/can19.png)

## 数据保护机制

![can20](../canfuzz/img/can20.png)

以下列出了几种检测手段。

* 位检查
* ACK回应包
* ACK回应位检查
* CRC校验
* 位填充
* 格式检测

ACK回应包，CRC校验，位填充。都在以上小节叙述过了，下面小节讲解位检查、格式检查以及ACK回应位检查。

### 位检查

![can21](../canfuzz/img/can21.png)

发送节点通过位监控的手段来检测是否发送错误，具体原理就是检测回应报文是否与发送一致。这里分几个部分，在上图中在仲裁场也就是*Identifier*+*RTR*部分（图中显示为虚线）如果发1读0，不会认为这事一个位错误，当作仲裁失败处理。但是发0读1。在*ACK*部分也是虚线表示，因为*ACK*是返回0表示回应正确。1表示错误，所以发1读0，是没有错误的。

### 格式检测
格式检测就是检测两个*DEL*位以及*EOF*位是否为1，这样的固定格式。如果检测到错误则会发送错误帧。

### ACK回应位检查
ACK回应检查一般由接收节点来填充回应，当它发送了回应包，它也会回读总线上的回应包，如果它发送的是1，回读到的是0，那么它会认为破坏了帧的内容，则这个节点就会在下一帧发错误帧。

## 错误帧
当一个错误被检测到，那么错误帧会在下一刻立即发送。这里除了CRC校验错误。CRC校验错误会在返回给发送节点之后，由发送节点判断ACK位是否为1来确定是否发送错误帧。

![can22](../canfuzz/img/can22.png)

### 错误帧格式

错误帧是由错误标志位+错误界定符组成。错误标志位由主动状态与被动状态组成。

#### 主动错误状态(*Error-Active Node*)
在主动检测到发送存在错误时，节点会发送6个0的测试标志位+8个1的错误界定符，但是可能总线上存在其他节点也在发送主动错误帧，所以这里的错误标志位可能不止6个。

#### 被动错误状态(*Error-Passive Node*)
在被动错误状态，将发送6个1的测试标志位+8个1的错误界定符。如果是发送节点它的错误状态是直接可以发出来的，但当接收节点处于被动错误状态时，检测到错误，它发送的错误帧可能会被其他节点的发送覆盖掉，所以它只能等待处于主动状态的节点发送6个0后，它再发送6个1。

### 错误帧例子讲解

首先假设所有节点都处于主动状态，也就是说当它们检测到错误后，会连续发6个0和8个1。下图展示了，当发送节点发送数据3个1后又发送了1个0，但是根据位监控机制回读总线上读出来是1。

![can23](../canfuzz/img/can23.png)

那么它会发送6个0与8个1，表示错误。

![can24](../canfuzz/img/can24.png)

但是接收节点读取总线数据，它读到错误发送1，它是不知道1是错误的。它继续读取直到读取到连续的6个0。由于位填充规则总线上是不可能有连续6个相同的位的。破坏了填充规则。

![can25](../canfuzz/img/can25.png)

它会任何这是一个错误，它会发送一个6个0加8个1的主动错误帧。从下图可以看出是所有接收节点都会这样去做。

![can26](../canfuzz/img/can26.png)

那么此时错误帧可能存在连续12个0外加8个1。最后会再填充3个1的帧间隔，总共连续11个1，那么总线又进入一个空闲状态。那么发送节点会将这帧进行重发。从上图可以看出，再出现错误时，只要是参与通讯的节点都会发送错误帧。

### 错误状态判断
下图展示了主动错误状态与被动错误状态的转换。可以看出总共有三种状态，那么一个节点就有这三种状态。

1. 主动错误状态
2. 被动错误状态
3. BUS OFF状态

![can27](../canfuzz/img/can27.png)

在每个节点内实现了两个寄存器，一个是TEC（发送错误计数器）一个是REC（接收错误计数器）。节点内部通过这两个计数器的数值来完成两个错误状态的切换。当**TEC与REC都小于等于127**时，节点处于主动错误状态，当**TEC或者REC数值大于127**时，状态切换到被动错误状态，当**TEC和REC都小于128时**节点又切换回主动错误状态，当处于被动错误状态时，**TEC大于255**那么会切换到BUSOFF状态，在BUSOFF状态，或者通过软件重置或者等待连续128组11个1后转为主动错误状态。

在CAN11898-1中明确定义了TEC,REC的数值说明。简要来讲就是当一个节点成功发送一帧报告，那么它的TEC与REC的计数就减1。发送节点在发送数据后检测到错误，那么它的TEC就会加8。接收节点率先检测到错误之后它的REC就会加8。如果在其他节点检测到错误帧的状况下，又检测到错误那么它的REC就会加1。具体可参见标准。

### 主动错误状态与被动错误状态的不同

![can28](../canfuzz/img/can28.png)

三种错误状态的不同，在主动错误状态的节点，就是正常的节点，收发都是正常的。但是当处于被动错误状态在检测到连续11个1的帧末尾后，它是不能直接发送数据的，它必须等待8位的空闲时间后再进行发送。这是对它的一个惩罚。当进入BUSOFF状态的节点那么是不允许它发送数据的。
