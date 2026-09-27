# Go 编译器的 ABI：原理与实现对照

> **这份文档回答什么**：一次函数调用，在编译器眼里到底被拆成了哪些动作？这些动作凭什么能被不同编译器、不同语言、不同时间编译出来的代码拼在一起？
>
> **怎么用**：上半部分（§1–§5）是 *Engineering a Compiler* Ch06/Ch07 的原理提炼，讲"为什么这么设计"；下半部分（§6–§9）是 Go 1.27.1 的真实实现对照，讲"Go 具体怎么做的、和书哪里不一样"。
>
> **配套阅读**：`doc/go_book_mapping.md` §Ch06 / §Ch13（源码↔章节双向索引）、`go_source_code/src/cmd/compile/abi-internal.md`（Go ABI 权威规范，必读）。

---

## §0 主题 ↔ 书章节 ↔ 源码 对照表

| 主题 | 书章节 | Go 源码 / 文档 |
|---|---|---|
| 过程调用、调用者与被调用者、参数和返回值 | Ch06 §6.2 | `compile/internal/ssagen/abi.go`（wrapper）、`ssa/expand_calls.go` |
| 活动记录、运行时结构、栈帧 | Ch06 §6.3.2 | `cmd/compile/abi-internal.md` §Stack layout、`ssa/stackalloc.go`、`ssa/location.go` |
| 参数传递、返回值、跨函数通信 | Ch06 §6.4 | **`compile/internal/abi/abiutils.go`**、`abi-internal.md` §Function call argument and result passing |
| 标准化链接约定（ABI 理论基础） | Ch06 §6.5 | **`cmd/compile/abi-internal.md`**、`src/internal/abi/`、`cmd/internal/goobj/` |
| 过程序言、尾声、调用序列、寄存器保存 | Ch07 §7.9 | 各架构 `ssa/*.go` 的 `regInfo.clobbers`、`ssa/prologue.go`、`abiutils.go` |
| IR 到机器指令的生成 | Ch11 §11.2 | `ssa/lower.go`、`ssa/_gen/*.rules` → `ssa/rewrite*.go` |
| 寄存器分配与 spill | Ch13（§13.2/13.3/13.4/13.5.2） | **`ssa/regalloc.go`**、`ssa/stackalloc.go` |

---

## §1 ABI 是什么：一份三方契约

书 §6.5 开篇的定义是全章最凝练的一句：

> "The procedure linkage is a contract between the compiler, the operating system, and the target machine that clearly divides responsibility for **naming, allocation of resources, addressability, and protection**."
> —— Ch06 §6.5

也就是说，**链接约定（linkage convention，今天叫 ABI）把四件事的责任在调用方/被调用方之间划清**：

| 责任 | 具体指什么 | 落在哪一侧 |
|---|---|---|
| **naming（命名）** | 符号怎么起名（name mangling）、怎么让 linker 找到 | 编译器 + linker |
| **resource allocation（资源分配）** | 栈帧谁开谁关、寄存器谁存谁恢复 | 双方分工 |
| **addressability（可寻址性）** | 参数/局部变量在哪儿、怎么算地址 | 双方约定 |
| **protection（保护）** | 被调用方不许破坏调用方的运行环境 | 双方约定 |

### 为什么非有不可：分别编译（separate compilation）

书 §6.1 给的理由非常直接：编译 `p` 的时候，编译器**看不到** `q` 的实现，也不知道调用 `p` 的现场长什么样。

> "Assume that procedure *p* has an integer parameter *x*. Different calls to *p* might bind *x* to a local variable stored in the caller's stack frame, to a global variable, to an element of some static array, and to the result of evaluating an integer expression such as *y*+2."
> —— Ch06 §6.5

正是链接约定规定了"实参怎么求值、怎么放"，也规定了"被调用方怎么取形参"，`p` 的代码才能对这四种现场一视同仁。

**一句话记住**：ABI 是二进制的接口；API 管源码级兼容，ABI 管二进制级兼容。改了寄存器分配方案 = 改了 ABI = 必须重编所有依赖方。

---

## §2 一次调用 = 四段代码（书 §6.5 + §7.9 的核心图景）

书 Figure 6.10 / 7.19 把一次调用切成四段，这是整章的骨架：

```
调用者 p                                        被调用者 q
┌──────────────┐                            ┌──────────────┐
│  precall     │  ── 传参 / 传返回地址 ──▶  │  prologue    │
│  调用前序列  │                            │  序言        │
│              │                            │              │
│              │  ◀── 返回值 / 恢复环境 ──  │  epilogue    │
│  postreturn  │                            │  尾声        │
│  返回后序列  │                            │              │
└──────────────┘                            └──────────────┘
      每个 call site 一份                        每个过程一份
```

| 段 | 属于 | 职责（书 §6.5 原文要点） |
|---|---|---|
| **precall** | caller | 求值实参；确定返回地址；必要时为返回值预留空间；若传引用参数当前在寄存器里，要先把它存回 AR 以便取地址 |
| **postreturn** | caller | 撤销 precall 的动作：把 value-result / 引用参数写回寄存器；从寄存器保存区恢复 caller-saves 寄存器；释放 callee 的 AR |
| **prologue** | callee | 把 caller 通过寄存器传来的值落到 AR 里；为局部变量开空间并初始化；把过程级静态数据区标签载入寄存器 |
| **epilogue** | callee | 拆掉自己的环境、重建 caller 的环境；把返回值写回 caller 指定的位置；恢复 caller 的 ARP 并跳回返回地址 |

### 唯一要背的优化原则

书 §7.9 给了这条原则，它是所有调用约定的设计动机：

> "moving operations from the precall and postreturn sequences into the prologue and epilogue sequences should reduce the overall size of the final code."
> —— Ch07 §7.9

因为 **precall/postreturn 是"每个调用点一份"，prologue/epilogue 是"每个过程一份"**。一个被 10 处调用的函数，把一条指令从调用点挪到序言里，代码体积就省下 9 份。书里还补了一句反过来的话：如果某个过程全程序只被调用一次，那应该干脆内联掉。

**顺带一个设计自由度的提醒**（书 §6.5）：这些活儿在 caller 和 callee 之间**可以挪**。挪到哪边是设计选择，不是物理必然——下面 §5 会看到 Go 做了一个很激进的选择。

---

## §3 活动记录（AR）→ 栈帧（书 §6.3.2）

### 3.1 AR 里有什么

书 Figure 6.4 给出典型的 AR 布局，七个字段。注意它是**通过一个 ARP（activation record pointer，帧指针）寻址**的，各字段在 ARP 的正负偏移处：

| 字段 | 内容 | 对应控件 |
|---|---|---|
| parameter area | 调用点的实参，按出现顺序 | caller 填 |
| register save area | 需要跨调用保存的寄存器 | 由 caller/callee 分工决定 |
| return-value slot | 把数据传回 caller | 双方约定 |
| return-address slot | 返回后从哪里继续执行 | 由 `call` 指令产生 |
| addressability slot | 访问**词法外层**（不一定是调用者）变量的信息 | access link / display |
| caller's ARP | caller 的帧指针，返回时要恢复 | prologue 填 |
| local data area | 本过程声明的变量 | callee 填 |

两个常被忽略的细节：

1. **ARP 通常独占一个寄存器**，因为过程访问自己的 AR 太频繁了。ILOC 里叫 `rarp`，x86 里是 `RBP`。
2. **AR 的中间部分是静态布局（固定偏移），两端才是变长的**——一端放参数、一端放局部数据。所以"变长数组"可以挂在 AR 末尾，用 top-of-stack 指针增量扩张（书 Figure 6.5）。

### 3.2 AR 放在哪：三种分配策略

书 §6.3.2 给了三个选项，判断依据是**生命周期是否服从 LIFO**：

| 策略 | 适用条件 | 代价 | 语言实例 |
|---|---|---|---|
| **栈分配** | 过程不会活得比调用者长；无闭包逃逸 | 分配/释放各一条指针加减 | Pascal / C / Java |
| **堆分配** | 过程可能活得比调用者长；或返回了引用局部的闭包 | 分配器开销；需要 GC 或显式 free | Scheme / ML |
| **静态分配** | 叶过程（leaf procedure，不含任何调用），同一时刻至多一个活跃 | 零运行时开销 | 书里提到可让**所有**叶过程共享一个静态 AR |

栈分配还有一个免费的好处（书 §6.3.2）：调试器可以从栈顶走到栈底，直接打印出当前活跃的过程链。

### 3.3 非局部访问：access link 与 display

嵌套过程要访问词法外层的变量，需要把"静态坐标 ⟨level, offset⟩"翻译成运行时地址。书给了两种方案：

| 方案 | 数据结构 | 非局部访问代价 | 维护代价 |
|---|---|---|---|
| **access link**（静态链） | 每个 AR 存一个指向**词法直接外层** AR 的指针，串成链 | `m − n` 次解引用，**与嵌套深度差成正比** | 每次调用要算出正确的 link |
| **global display** | 一个全局数组，第 `i` 项存词法第 `i` 层最近一次激活的 ARP | 固定代价（一次数组索引 + 一次解引用） | 进入/离开过程时要更新数组项；不调用更深层过程的过程可跳过 |

书 §6.4.3 还给了维护 access link 的三种情形，值得背：设 caller 在第 *m* 层、callee 在第 *n* 层——

- `n = m + 1`（callee 嵌在 caller 里）→ callee 的 link 就是 caller 的 ARP
- `n = m`（兄弟过程）→ callee 的 link 等于 caller 的 link
- `n < m`（访问更外层）→ 沿 caller 的 link 走 `m − n` 步

**Go 的特殊之处见 §3.4。**

### 3.4 Go 怎么落地

对照 `abi-internal.md` 的 amd64 Stack layout：

```
+------------------------------+
| return PC                    |   ← 由 CALL 指令压入
| RBP on entry                 |   ← 被调用者保存的帧指针
| ... locals ...               |
| ... outgoing arguments ...   |
+------------------------------+ ↓ 低地址
```

差异点，逐条：

1. **没有独立的"返回地址槽"**：amd64 的 `CALL` 指令自己把 return PC 压栈，返回地址由硬件产生，不是编译器塞进 AR 的字段。
2. **ARP 只保存不更新语义**：Go 用 `RBP` 作帧指针，且是**为兼容平台调试器/profiler 才保留的**（`abi-internal.md` amd64 §Stack layout 原文）。叶子函数如果不需要栈空间，可以**完全省略** saved RBP。
3. **Go 没有嵌套函数，所以不用 display**。书讲的 access link / display 在 Go 里几乎找不到对应物——**唯一需要"静态链"的地方是闭包**。
4. **闭包 = 静态链的现代变体**。Go 把捕获的变量打包成一个对象，函数值就是指向它的指针：

   ```
   // walk/closure.go:170 的注释原文
   //   clos = &struct{F uintptr; R T}{T.M·f, x}
   ```
   
   即 `closure object = { F uintptr（函数入口 PC）; X... （闭包变量） }`，与 `abi-internal.md` §Closures 的描述一致。调用闭包时，把 closure object 的地址放进该架构约定的 **closure context pointer 寄存器**（amd64 是 `RDX`，arm64 是 `R26`）。

   > 对比书 §6.2 的 "More Complex Control Flow"：书指出简单栈不足以支撑闭包，需要更一般的结构。Go 的答案就是"把环境提到堆上 + 用寄存器传上下文指针"。

5. **栈会增长（stack split）**：这是 Go 独有、书里没有的一维。每个函数序言里有栈空间检查，不够就调 `runtime.morestack` 把整个 goroutine 的栈**搬到更大的地方**（栈是复制的，所以指针要修正）。这一个机制直接导致两个后果——
   - **Go 不对用户代码做通用尾调用消除**（书 §10.4.1 讲的技术）。因为尾调用要复用当前帧，而 Go 需要保持可增长、可精确回溯的栈。
   - **参数 spill space 必须由 caller 预留**（见 §4.2）。

---

## §4 参数传递与返回值（书 §6.4 + Go 的实现）

### 4.1 四种传参语义（书 §6.4.1）

书用同一个例子 `fee` 演示了所有差异：

| 语义 | 传什么 | 被调用方改动是否可见 | 书里的例子结果（`fee(a,a)`） |
|---|---|---|---|
| **call-by-value** | 值本身 | 否 | 返回 6 |
| **call-by-reference** | 地址 | **是** | 返回 8（因为 `x`、`y` 成了 alias） |
| **call-by-value-result** | 值 + 返回时写回 | 是（返回时） | Fortran 77 / Ada 的语义 |
| **call-by-name** | 一个 thunk（延迟求值的函数） | 视情况 | Algol 60 的语义，实现复杂，已淘汰 |

书对 call-by-reference 的 **alias（别名）** 陷阱讲得很细：第三个调用 `fee(a,a)` 让 `x` 和 `y` 指向同一块存储，`x = 2*x; y = x + y` 于是变成 `a=4; a=4+4=8`。

> 对照 Go：**Go 全是 call-by-value**，语义上干净，没有 alias 陷阱。要"传引用"就显式传指针（`*T`）。R 语言的 lazy 传参（promise/thunk）是 call-by-name 思想在今天的少数幸存者。

### 4.2 大对象的麻烦与 Go 的取舍

书 §6.4.1 "Space for Parameters" 指出：标量参数很便宜，但**大对象传值**会给每次调用加上昂贵的拷贝成本。书给的建议是让程序员显式传指针（C 里的 `const` 属性也是这个思路）。

Go 的取舍写在 `abi-internal.md` 的 Rationale 里，非常值得逐条读——**每一条都是在"性能 / 简单性 / 可寻址性"三角里做选择**：

| 决策 | 理由（原文要点） |
|---|---|
| 优先用寄存器（寄存器比栈快） | 现代架构寄存器足够多，实测 9 个整数寄存器就能让 ~92% 的函数全部走寄存器 |
| **每个 base value 占一个独立寄存器**，不做 packing | 替代方案是把子字长的值打包或多个值共用一个寄存器（**C ABI 的常见做法**），但那会在使用时要 pack/unpack，加成本 |
| **放不进剩余寄存器的参数，整个走栈** | 否则 callee 若取该参数的地址，就得在内存里把它重新拼起来，成本与参数大小成正比 |
| **数组一律走栈**（0 元素、1 元素例外） | 数组索引需要"计算出的偏移"，寄存器做不到。顺带给了数据：Go 1.15 标准库里只有 0.7% 的函数签名含数组 |
| 参数和返回值**可以共用寄存器**，但**不共用栈空间** | —— |
| **零大小类型也分配到栈** | 为了让算法退化成"零寄存器"时等价于 ABI0，否则 ABI0 的对齐填充会对不上 |

### 4.3 Go 的参数分类算法

这是整个 Go ABI 的心脏，`abiutils.go` 就是它的实现。算法在 `abi-internal.md` 里写得像伪代码，可以直接读：

```
输入：函数 F 的 receiver / 参数 / 返回值列表，架构定义的
      整数寄存器序列（长度 NI）与浮点寄存器序列（长度 NFP）

1. I = 0, FP = 0（下一个可用的整数/浮点寄存器下标）；S = 空（栈序列）
2. 若 F 是方法，先分配 receiver
3. 依次分配每个参数
4. 在 S 上添加一个指针对齐占位
5. I = 0, FP = 0    ← 注意：返回值从头开始用寄存器，和参数共用
6. 依次分配每个返回值
7. 在 S 上添加一个指针对齐占位
8. 为每个"寄存器分配的"receiver/参数，把它的类型加进 S
   ——这就是 spill space，调用时是未初始化的
9. 在 S 上添加一个指针对齐占位
```

递归拆解规则（"Register-assignment of a value V of underlying type T"）：

| 类型 | 处理 |
|---|---|
| bool / 整数，装得进一个整数寄存器 | 占一个整数寄存器 |
| 整数，需要两个整数寄存器（如 32 位平台上的 int64） | 占两个，低半在高半之前 |
| 浮点，能无损放进浮点寄存器 | 占一个浮点寄存器 |
| complex | 拆成实部/虚部递归 |
| pointer / map / chan / func | 占一个整数寄存器 |
| **string / interface / slice** | **递归拆解**（string 和 interface 2 个分量，slice 3 个） |
| struct | 递归拆解每个字段 |
| array 长度 0 | 什么都不做 |
| array 长度 1 | 递归拆解那一个元素 |
| **array 长度 > 1** | **失败 → 整个参数回退到栈** |
| 任何递归子项失败 | 整个失败 |

注意最后一步的"回退"（`abi-internal.md` 主算法的 step 3）：某个参数若寄存器分配失败，**寄存器下标要回滚**，然后整个参数进栈。这保证了"一个参数要么全在寄存器、要么全在栈"。

### 4.4 为什么要有 spill space（Go 独有的设计）

`abi-internal.md` 的 Rationale 讲得很清楚，它是 ABI 与"可增长栈"耦合的产物：

> "The algorithm reserves spill space for arguments in the **caller's** frame so that the compiler can generate a stack growth path that spills into this reserved space."

展开来说：当被调用方发现栈不够、要调 `runtime.morestack` 时，**必须在调用 morestack 之前把所有参数寄存器存起来**（morestack 会覆盖所有寄存器）。如果只有被调用方自己开栈，它可能已经开不出额外空间了——所以**必须在 caller 帧里预留好这块落点**。

代价：栈空间浪费（中位数 16 字节/调用）。`abi-internal.md` 的 "Future directions" 明确说这是想改进的方向。

### 4.5 返回值（书 §6.4.2）

书给的三种机制，按返回值大小递增：

1. **小、定长** → 放寄存器，或放 caller 的 AR（书指出：call-by-value 的约定常把"第一个参数寄存器"复用为"返回值寄存器"）。
2. **定长但较大** → caller 在自己的 AR 里留空间，把**指针**放进 callee 能看到的 return-value slot。
3. **大小未知** → callee 在堆上分配，把指针写回 caller 的 return slot，caller 负责释放。

Go 的做法：多返回值 = 一个隐式的结构体，然后**走同一套 §4.3 算法**。所以 `func f() (int, error)` 的返回值就是 `(R0, R1)`。这也解释了 `abi-internal.md` 例子里 `r2 string` 会被拆成 `r2.base` 和 `r2.len` 两个寄存器。

### 4.6 一个容易翻车的顺序问题（书 §7.9.1）

> "a program that used two routines `push` and `pop` to manipulate a stack would produce different results for the sequence `subtract(pop(), pop())` under left-to-right and right-to-left evaluation."
> —— Ch07 §7.9.1

求值顺序**对有副作用的实参是有语义影响的**。Go 语言规范里明确规定：函数调用中，函数值和参数的求值顺序是**未指定**的（各实现自定），但**同一函数内的参数按从左到右**的顺序求值。这就是这条原理在 Go 里的落点。

另外书 §7.9.1 还提到**过程型参数**（procedure-valued parameter）需要传 `⟨address, level⟩` 二元组，光传地址不够——因为被调用方可能要按词法层级去找正确的 access link。Go 不做嵌套函数，所以这里对应的是闭包的 closure context pointer。

---

## §5 寄存器保存责任：书讲折中，Go 走极端

### 5.1 书里的分析（§6.5 + §7.9.2）

书把这归结为一个"谁保存"的权衡：

| 谁保存 | 优势 |
|---|---|
| caller 保存 | caller 知道自己跨调用还需要哪些值，可以**少存** |
| callee 保存 | callee 知道自己实际用了哪些寄存器，可以**少存** |

书的结论：

> "For any specific division of labor between caller and callee, we can construct programs for which it works well and programs for which it does not. Most modern systems take a middle ground."
> —— Ch06 §6.5

折中的好处（书原文）：鼓励编译器把**长寿命值放 callee-saves 寄存器**（只在 callee 真用到时候才存），把**短寿命值放 caller-saves 寄存器**（可能在调用点就不必存了）。

书 §7.9.2 还列了三种降低保存开销的工程手段：

1. **多寄存器内存操作**：相邻寄存器一起存/取（doubleword / quadword load-store、SPARC 的 register window、VAX 的高层 call 指令）
2. **用编译器自带的库例程**做 save/restore：把一长串 store 换成一次调用，代码体积显著下降；因为这对例程只有编译器知道，可以用最省的调用序列
3. **合并责任**：caller 传一个"需要保存的寄存器掩码"给 callee，callee 把自己的需求或上去再调一次 save 例程——**用一次调用搞定双方的需求**，把"责任划分"和"调用成本"解耦

### 5.2 Go 的极端选择：一个 callee-save 寄存器都没有

`abi-internal.md` 一句话：

> "There are no callee-save registers, so a call may overwrite **any** register that doesn't have a fixed meaning, including argument registers."

这是 Go ABI 里最反直觉的一条（对比 SysV amd64 ABI 有 RBX/RBP/R12–R15 六个 callee-save 寄存器）。注意 `abi-internal.md` 的 amd64 参数寄存器序列里有 **RBX**：

```
RAX, RBX, RCX, RDI, RSI, R8, R9, R10, R11
```

RBX 在平台 ABI 里是 callee-save，Go 拿它当参数寄存器用——这就是"没有 callee-save"的直接后果。

**为什么敢这么干**（`abi-internal.md` §Clobber sets 原文）：

> "This significantly simplifies the **garbage collector** and the compiler's **register allocator**, but at some performance cost."

- **简化 GC**：GC 需要在安全点精确知道哪些寄存器里有指针。如果寄存器有 callee-save 语义，栈回溯时就要逐层判断"这一层的寄存器值属于哪一层"，复杂度暴涨。全 caller-save 意味着**任何一处调用之后，寄存器里的活性只属于当前函数**，GC 位图直接可算。
- **简化 regalloc**：不用做跨调用的寄存器活性分析，不用维护"哪些寄存器在调用后还活着"。

**代价**：任何跨调用的活值都要在调用点 spill 回栈。

**Go 想过的替代方案**（同一节）：**clobber sets**——为每个函数记录它（及其传递调用链）会破坏的寄存器集合，没被破坏的寄存器就可以跨调用保活。Go 的包依赖 DAG 允许这类元数据沿着调用图上浮，即使跨包也行。缺点是对间接调用和接口方法调用无效（拿不到静态信息）。

### 5.3 amd64 的固定用途寄存器（书 §6.5 的"机器相关"佐证）

书 §6.5 说链接约定"of necessity, machine dependent"。Go 的这张表是最好例证：

| 寄存器 | 调用时含义 | 返回时含义 | 函数体内含义 |
|---|---|---|---|
| `RSP` | 栈指针 | 同 | 同 |
| `RBP` | 帧指针 | 同 | 同 |
| `RDX` | **闭包上下文指针** | scratch | scratch |
| `R12` `R13` | scratch（**永久保留**） | scratch | scratch |
| `R14` | **当前 goroutine** | 同 | 同 |
| `R15` | 动态链接时的 GOT 临时 | 同 | 同 |
| `X15` | **零值寄存器** | 同 | scratch |

设计理由（`abi-internal.md` 给了 Rationale）：

- `R12`/`R13` 必须是永久 scratch，因为**栈增长**和 `reflect` 调用需要在"不破坏任何参数/返回值"的前提下操作 call frame。
- `R14`（goroutine 指针）故意选了一个需要 REX 前缀的寄存器——每个函数序言多一个字节，但函数体外几乎不访问它，换来更多单字节寄存器可用。
- `X15` 用作零值寄存器，因为函数**经常需要整片清零栈帧**。

arm64 的对照（`abi-internal.md` §arm64）：`R0–R15` 传整数参数、`F0–F15` 传浮点、`R30` 是 link register（在函数体内可当 scratch）、`R29` 帧指针、`R28` goroutine、`R26` 闭包上下文、`ZR` 零值。

一个有意思的架构差异：**amd64 没有 link register**（返回地址靠 `CALL` 压栈），**arm64/riscv64/loong64/ppc64/s390x 都有 link register**（`CALL` 把返回地址放进 LR），所以在这些架构上序言要显式把 LR 存栈——这个差异被 `abi-internal.md` 用同一张栈布局图统一描述了。

---

## §6 两套 ABI：ABI0 与 ABIInternal

这是 Go 特有的复杂度，书上没有对应内容。

| | **ABI0** | **ABIInternal** |
|---|---|---|
| 参数传递 | **全部走栈** | 寄存器优先，放不下才走栈 |
| 稳定性 | **稳定**，写汇编就靠它 | **不稳定**，Go 版本间会变 |
| 谁用 | 手写汇编（`.s`）、`//go:linkname`、外部工具 | **所有 Go 源码定义的函数** |
| 出处 | `abi-internal.md` 开头 + `doc/asm.html` | `abi-internal.md` 全文 |

`abi-internal.md` 开头两句话把关系说清了：

> "This document describes Go's internal ABI, known as ABIInternal. This ABI is *unstable* and will change between Go versions. If you're writing assembly code, please instead refer to Go's assembly documentation, which describes Go's stable ABI, known as ABI0."

两者通过 **ABI wrapper** 透明互调（`abi-internal.md` 转述 design doc 27539）：

```
Go 函数 A (ABIInternal)  ──▶  ABI wrapper  ──▶  Go 函数 B (ABI0)
                              (把寄存器参数搬到栈)
```

一个很妙的设计（`abi-internal.md` §Rationale 末尾）：

> "The ABI assignment algorithm above is equivalent to Go's stack-based ABI0 calling convention if there are **zero** architecture registers."

也就是说 **ABI0 不是另一套算法，而是 ABIInternal 算法在 NI = NFP = 0 时的退化情形**。这让编译器可以用同一份代码生成两种调用约定——第 6 行那张分析表的第一行（0 整数 / 0 浮点寄存器，6.3% 的函数全走寄存器）就是在测这个退化点。

`regInfo.clobbers` 等每架构的 clobber 信息在 `ssa/*.go` 里；ABI wrapper 的生成在 `ssagen/abi.go`。

---

## §7 IR → 机器指令（书 §11.2）：为什么 ABI 会渗透到指令选择

书 §11.2 立起后端的三根支柱：

| 问题 | 名称 | 复杂度 |
|---|---|---|
| 把 IR 操作映射成目标 ISA 操作 | **instruction selection** | 搜索空间可达上亿状态 |
| 决定操作执行顺序 | **instruction scheduling** | 单基本块在多数现实模型下 **NP-complete** |
| 决定每个点哪些值在寄存器、哪些在内存 | **register allocation** | 一般形式（含控制流）**NP-complete** |

书的核心观察：**一个 IR 操作在真实机器上往往有多种实现**。它举的例子极妙——只是"把一个寄存器拷到另一个寄存器"，在 ILOC 上就有这么多写法：

```
i2i r1 ⇒ r2              （最直接）
add r1, r0 ⇒ r2          （若 r0 恒为 0）
sub r1, r0 ⇒ r2
lshift r1, 0 ⇒ r2
or  r1, r0 ⇒ r2
xor r1, r0 ⇒ r2
store r1 ⇒ M ; load M ⇒ r2   （两指令序列）
```

书提醒：人类程序员一眼就知道用 `i2i`，但**自动化流程必须把所有可能性纳入考虑并选择**。这就是为什么需要代价模型和系统性方法（树模式匹配 / peephole）。

书 §11.2 还把"选择 / 调度 / 分配"三者的耦合讲得很透，其中一条与本文主题直接相关：

> "If, on the other hand, the target machine has rules that restrict register usage, then the selector must pay close attention to specific physical registers. This can complicate selection and predetermine some or all of the allocation decisions."
> —— Ch11 §11.2

**这正是 ABI 与指令选择耦合的地方**：因为 ABI 规定"第 1 个整数参数在 RAX、第 2 个在 RBX……"，指令选择阶段就不能假装有无限寄存器，必须把这些物理寄存器约束传下去（书 §13.4.8 讲的"在干扰图里编码机器约束"就是同一件事的两个面）。

另一条也很关键：

> "an IR with a lower level of abstraction than the ISA allows the selector to tailor its selections accordingly."
> —— Ch11 §11.2

Go 就是这么做的：`ssa/lower.go` 先做 generic → arch 的 lower，再由 `ssa/_gen/*.rules` 经 `go generate` 生成的 `rewrite*.go` 做模式重写。**注意 `rewrite*.go` 是生成物，别手改**（见 AGENTS.md 约定 3）。

---

## §8 寄存器分配与 spill（Ch13）

### 8.1 先分清两件事（书 §13.2.2）

| | 定义 | 复杂度 |
|---|---|---|
| **allocation** | 把无限的名字空间映射到"有 k 个位置的寄存器集合" | **NP-complete**（一般形式）；单基本块 + 单一数据宽度 + 每条值都落内存 才是多项式 |
| **assignment** | 把已分配的名字集合映射到**具体物理寄存器编号** | 基本块内**线性时间**（区间图着色）；整个过程的可行分配也是多项式时间 |

书特意强调：优化分配器时要先搞清楚**瓶颈在 allocation 还是 assignment**，否则会白干。

### 8.2 局部：两种算法（书 §13.3）

| | top-down（频次法） | bottom-up（下次使用最远） |
|---|---|---|
| 依据 | 每个虚拟寄存器在块内被引用多少次 | 详细的操作级信息，边走边决定 |
| 策略 | 按频次降序分配，前 `k − F` 个进寄存器（`F` 是留给 spill 代码用的寄存器数） | 寄存器全空起步，按需分配，不够时 spill **下次使用最远**的那个 |
| 弱点 | **一个寄存器在整个块内锁给一个值**——值只在前半段热、后半段凉时，寄存器被白白占着 | 需要更多低层信息 |
| 原型 | —— | Belady 的离线页面置换算法（书 Chapter Notes 明确点了这层关系） |

书 §13.3.2 还给了一个漂亮的复杂度结果：**clean/dirty 的区分让局部最优分配变成 NP-hard**。

- **clean** 值：不需要 store 就能丢弃（如常量、刚从内存 load 出来的值）
- **dirty** 值：必须 store 才能丢弃

书用同一个"下次使用最远"启发式在两个引用串上得到相反的最优解，说明**"优先 spill clean 值"这条简单规则并不成立**。

### 8.3 全局：图着色（书 §13.4）

#### live range 与干扰

| 概念 | 定义 |
|---|---|
| **live range（活跃区间）** | 一组"值一起流动"的定义与使用的闭包集合。一个源码变量可能对应**多个** live range |
| **interference（干扰）** | lrᵢ 在 lrⱼ 的定义处是活的，且两者值不同 → 不能共用一个寄存器 |
| **interference graph** | 节点 = live range，边 = 干扰。**k-colorable ⟺ 能用 k 个寄存器** |

关键细节（书 §13.4.3）：**copy 和 φ 函数不产生干扰边**（源和目标是同一个值，可以共用寄存器）。这个"例外"正是 coalescing（合并）能成立的前提。

#### 两种着色方向

| | top-down（Chow） | bottom-up（Chaitin/Briggs） |
|---|---|---|
| 定序依据 | 高层信息：按"留在寄存器能省多少运行时间"排序 | 低层结构：从干扰图里反复摘节点 |
| 着色顺序 | 先给**受约束**节点（度数 ≥ k）着色，再随处理无约束节点 | 先用"无约束节点先把它们摘掉"的顺序建栈，再逆序插回并着色 |
| 摘不动时 | 直接 spill | 用 **spill metric** 选一个节点（Chaitin 原版：最小化 `cost / degree`） |

书解释 bottom-up 为什么正确（§13.4.5）：被第一子句（无约束）摘掉的节点，插回时也必然无约束，**必定有色**；唯一可能没色的是被 spill metric 摘掉的节点。

#### 四个改良技术（都是工业编译器实际在用的）

| 技术 | 做什么 | 解决什么 |
|---|---|---|
| **coalescing（合并）** | copy 两边若不干扰就合并成一个 live range，消掉 copy | 消指令、降度数、缩小图。Briggs 论文给出"最多消掉 1/3 的 live range" |
| **conservative coalescing** | 只在 lrᵢⱼ 的"显著度数"邻居 < k 时才合并 | 防止合并后反而更难着色 |
| **live-range splitting（分裂）** | 把一个 live range 切成几段 | 让片段度数下降；**还能控制 spill 代码的位置**（比如挪到循环外） |
| **rematerialization（重算）** | 小常量之类"重算比 spill 便宜"的值，直接重算不 spill | 省 memory 操作 |

#### 线性扫描：绕开图着色

书 §13.4.7 的边栏讲了一个重要的工程妥协，也是 **Go 采用的路子**：

- 用**区间 [i, j]** 近似 live range（宽松上界），这样构造出的干扰图必然是**区间图**
- **区间图的 k-colorability 线性可解**（而一般图是 NP-complete）
- 分配和指派可以在**一遍线性扫描**里完成 —— 所以叫 linear scan
- 代价：近似带来更多 spill；且必须另行处理 copy 合并

书明确点名适用场景：**JIT**——编译速度 vs spill 代码量的权衡向速度倾斜。

#### SSA 上的分配（书 §13.5.2）

书指出：**用 SSA name 当 live range 建出的干扰图是 chordal graph（弦图）**，而 **chordal graph 的 k-coloring 可在 O(|V|+|E|) 时间最优求解**。这是一个很漂亮的理论结果。代价是：分配完还得从 SSA 翻译出去（书 §9.3.5 那堆麻烦），而这个翻译本身可能增加寄存器需求。

### 8.4 Go 的实现：线性扫描 + 直接在 SSA 上做

`ssa/regalloc.go` 的文件头注释就是答案（`regalloc.go:5–15` 原文）：

> "We use a version of a **linear scan** register allocator. We treat the whole function as a **single long basic block** and run through it using a greedy register allocator. Then all merge edges ... are processed to shuffle data into the place that the target of the edge expects.
>
> The greedy allocator moves values into registers just before they are used, spills registers only when necessary, and **spills the value whose next use is farthest in the future**."

逐条对照书：

| 书的说法 | Go 的做法 |
|---|---|
| §13.4.7 linear scan | ✔ 采用 |
| §13.3.2 bottom-up local 的"下次使用最远" | ✔ 直接作为全局贪心策略（`regalloc.go:15`） |
| §13.3.3 跨块传递的困难 | Go 的处理：要求**基本块调度时至少有一个前驱已调度**，用"最近调度过的前驱"作为该块的起始寄存器状态 |
| critical edge 上无法插入 fixup | Go 在进入 regalloc 之前就**保证图中没有 critical edge**（`regalloc.go:21–25`）；这样 merge 边的源只有一个后继，可以把 shuffle 代码贴在其尾部 |
| §13.4.4 / §13.4.5 图着色分配 | ✘ **Go 没有**。干扰图只用在栈槽分配（`ssa/stackalloc.go`） |
| §13.5.2 SSA-based RA | ✔ Go 直接在 SSA 形式上分配；分配完 SSA 即被销毁（见 `go_book_mapping.md` §Ch13） |

#### Go 的 spill 是怎么做对的

这一段值得单独看，因为它是书里没有的工程细节（`regalloc.go:27–82`）：

1. 分配过程中，某个值 `v` 可能在所有寄存器里都被挤掉了。
2. 当后续真的要用 `v` 时，**才发现**它不在任何寄存器里。此时：
   - 为 `v` 分配一个 spill（一条 `StoreReg`），但**暂时不知道插在哪里**，先标记为 blockless；
   - 生成一条 restore（`LoadReg`）把它装回寄存器；
   - **后续对 `v` 的使用都改用这个 restore 出来的新值**。
3. 插在哪儿？——**在所有 restore 的共同支配者**处。
   - 若该块就是 `v` 的定义块 → 紧跟 `v` 定义之后插（此时 `v` 必定在寄存器里，且支配所有 restore）；
   - 否则若 `v` 在块入口就在寄存器里 → 插在块开头；
   - 否则 → 沿**直接支配者**往上递归一步，重试。

4. **phi 分两类**（书里没讲，但这是 SSA 上的分配绕不开的）：
   - **register phi**：phi 及其所有输入都在同一寄存器 → 像普通 op 一样 spill；
   - **stack phi**：phi 及其所有输入都在同一栈槽 → **出生就是 spilled 的**，每个 phi 输入在其前驱块末尾必须是一条 `StoreReg`。

这套"先乐观地在寄存器里算，用到时发现不在再补 spill，并用支配关系回推插入点"的策略，就是 Go 在不建干扰图的条件下得到不错结果的诀窍。

#### ABI 与 regalloc 的第三个交汇点

回到 §4.4：**caller 帧里预留的 argument spill space**，本质上是 ABI 给寄存器分配器**预先准备好的一块 spill 目标**。如果 callee 把某个寄存器参数取了地址，编译器就把该参数 spill 到这块 ABI 定义好的位置（而不是随便找个栈槽）——这样 `reflect` 之类的机制才能用**一个数**概括整块 spill 区（见 `abi-internal.md` §Rationale 最后几段）。

**记住这个三层结构**：

| 层 | spill 相关职责 |
|---|---|
| **ABI 层**（`abi-internal.md` / `abiutils.go`） | 定义 spill space 在哪、多大；规定参数寄存器与栈的参数对应关系 |
| **regalloc 层**（`ssa/regalloc.go`） | 决定 spill 谁（下次使用最远）、spill 代码插在哪（支配关系） |
| **stackalloc 层**（`ssa/stackalloc.go`） | 用干扰图决定各栈槽能不能复用同一块内存 |

---

## §9 端到端：一次 Go 调用的一生

把前面所有东西串起来。以 `func f(a int, b string) (int, error)` 的调用为例：

```
【编译期】                                     【对应书/源码】
1. 类型检查确定签名
2. abiutils.go 跑分类算法：
   a → R0（整数寄存器）
   b → R1,R2（string 拆成 base/len，两个整数寄存器）
   返回值 int,error → R0,R1（寄存器下标重置后用）
   栈帧里预留 aSpill / bSpill              ← §4.3 §4.4
3. ssa/expand_calls.go 把调用展开成
   显式的"存参数到寄存器/栈 + CALL"         ← §2 precall
4. regalloc.go 做线性扫描分配，
   把活值放寄存器，不够的 spill 到栈          ← §8.4
5. lower.go + rewrite*.go 落到机器指令      ← §7
6. obj.Prog 交给汇编器、链接器

【运行期】
7. caller 把参数放进 R0/R1/R2，
   把返回 PC（CALL 压栈，amd64）或放进 LR（arm64）  ← §2 §5.3
8. callee prologue：检查栈空间（不够就 morestack 搬栈）
   → 减 RSP → 存 RBP → 把寄存器参数落到 spill space
   → 置 goroutine 指针寄存器（R14/R28）等         ← §3.4 §5.3
9. body 执行
10. callee epilogue：恢复 RBP、RSP，把结果放回
    R0/R1 并 RET
11. caller postreturn：从栈取回自己跨调用要保活的值
    （Go 里这些值在调用点已经 spill 过了）            ← §5.2
```

---

## §10 常见误区 & 与教材的差异

| 误区 | 事实 |
|---|---|
| "Go 用图着色做寄存器分配" | **不是**。Go 用线性扫描（`regalloc.go`）。书 §13.4 的 Chaitin/Chow 图着色在 Go 里没有对应实现；干扰图只出现在 `stackalloc.go` |
| "callee-save 寄存器是标配" | Go **一个都没有**（`abi-internal.md` 明说）。这是为了让 GC 和 regalloc 变简单 |
| "ABI 只跟参数传递有关" | ABI 还管符号命名、栈帧布局、对齐、闭包上下文寄存器、goroutine 指针寄存器、浮点控制字（MXCSR/FPCR）的固定配置 |
| "书里的 display / access link 在 Go 里能直接找到" | 找不到。Go 没有嵌套函数，只有闭包，闭包用"堆上的 closure object + 上下文寄存器"，不是 display |
| "Go 支持尾调用优化" | 用户代码**不**做。只用于编译器自生成的 ABI wrapper / 泛型 shim（`ssagen/abi.go:323`）。原因：goroutine 栈要能增长、要能精确回溯 |
| "ssa/rewrite*.go 是可以改的优化规则" | 是**生成物**。规则看 `ssa/_gen/*.rules`，`.go` 由 `go generate` 生成 |
| "寄存器分配只是优化" | 在 **register-to-register 模型**下它是**产生合法代码的必要环节**；只有在 memory-to-memory 模型下才是纯优化（书 §13.2.1） |

**书上讲了但 Go 没做**（读 Go 源码时不要去找）：DFA 扫描器、LL/LR 解析表、属性文法、display/access link、通用尾调用消除、图着色寄存器分配、踪迹调度、软件流水线。

**Go 有但书里没讲**：统一 IR（`noder/`）、写屏障、GC 安全点活性（`liveness/plive.go`）、逃逸分析（`escape/`）、PGO（`pgoir/`）、**可增长栈与它在 ABI 上的全部后果**（spill space 预留、无 TCO、无 callee-save）。

---

## §11 动手验证

```sh
# 1. 看一个函数的最终汇编（含 precall / prologue / epilogue 全貌）
go build -gcflags='-S' ./yourpkg 2>&1 | less

# 2. 生成交互式 SSA 网页（每个 pass 前后对比，含 regalloc）
#    在包含目标函数的包里执行，会生成 ./ssa.html
GOSSAFUNC=Foo go build
#    只想看某几个 pass：
GOSSAFUNC="Foo:expand_calls,lower,regalloc" go build

# 3. 把某个 pass 之后的 SSA dump 到文件
go build -gcflags='-d=ssa/lower/dump=Foo'
#    生成 lower__Foo_0.dump

# 4. 列出所有可用的 SSA phase 名与 flag
go build -gcflags='-d=ssa/help' 2>&1 | less
```

> `-d=ssa/<phase>/<flag>` 的合法 phase 名来自 `ssa/compile.go` 的 `passes` 数组，名字里的**空格换成下划线**（所以 `"expand calls"` → `expand_calls`）。
> 合法 flag 有：`on, off, debug, mem, time, test, stats, dump, seed`。注意 **`debug=N` 只有那些真的调用 `f.Log` 的 pass 才有输出**（`regalloc` 就没有），此时应改用 `dump=` 或 `GOSSAFUNC=`。
> 权威说明见 `go_source_code/src/cmd/compile/internal/ssa/README.md`（~第 190 行起）。

（注意：本仓库的 `go_source_code/` 是只读参考，验证请在仓库外的临时目录做——见 `AGENTS.md` 约定 1。）

---

## 附：一页速记

1. **ABI = 编译器/OS/硬件三方契约**，管命名、资源分配、可寻址性、保护。
2. **一次调用四段**：precall / postreturn（每调用点）、prologue / epilogue（每过程）。**能往 callee 挪就往 callee 挪**。
3. **AR 七字段**：参数区、寄存器保存区、返回值槽、返回地址槽、可寻址性槽、caller ARP、局部数据区。放栈 / 堆 / 静态，取决于生命周期是否服从 LIFO。
4. **参数传递**：Go 全传值，寄存器优先，规则是"递归拆到 base type"；放不下整个走栈；数组一律走栈。
5. **寄存器保存**：书讲折中；**Go 全 caller-save**——简化 GC 与 regalloc，代价是调用点密集 spill。
6. **两套 ABI**：ABI0（全栈、稳定、给汇编）与 ABIInternal（寄存器、不稳定、给 Go）；ABI0 = ABIInternal 在零寄存器下的退化。
7. **后端三支柱**：selection / scheduling / allocation，都是难问题，分开做；ABI 通过"物理寄存器约束"渗透进 selection。
8. **寄存器分配**：书讲图着色（NP-hard），Go 用**线性扫描 + 下次使用最远**；spill 分三层（ABI 预留 / regalloc 决策 / stackalloc 复槽）。
9. **可增长栈是 Go 的独特维度**，它同时解释了 spill space 预留、无尾调用优化、无 callee-save 三个设计。

---

[← 返回目录](chapters/README.md) · 相关：`doc/go_book_mapping.md` · `doc/go_layout.md` · `doc/go_compiler_tests.md`
