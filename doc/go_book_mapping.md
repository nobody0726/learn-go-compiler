# Go 编译器源码 ↔《Engineering a Compiler》对照手册

> **源码**：`go_source_code/`（go1.27.1） · **书籍**：*Engineering a Compiler, 2nd Edition*（`doc/chapters/`）
> **配套文档**：[`go_layout.md`](./go_layout.md)（源码目录地图） · [`go_compiler_tests.md`](./go_compiler_tests.md)（测试用例梳理） · [`go_abi.md`](./go_abi.md)（Ch06/07/11/13 的过程调用与 ABI 专题总结）

## 怎么用这份手册

| 你的场景 | 去查 |
|---|---|
| 读完一章，想知道「Go 里怎么实现的」 | **§1 正向索引**（按书章节 → 源码） |
| 正在读某个文件，想知道「这算法是哪来的」 | **§2 反向索引**（按源码 → 书章节） |
| 发现书里的技术 Go 里找不到 / Go 里有书没讲的 | **§3 差异提醒** |
| 不知从哪开始 | **§4 学习路线** |

路径约定：源码路径省略前缀 `go_source_code/src/`。例如 `compile/internal/ssa/prove.go` 实际位于 `go_source_code/src/cmd/compile/internal/ssa/prove.go`（`compile` = `cmd/compile`）。

---

## 0. 一页总览

| 书章 | 主题 | Go 的主要落脚点 |
|---|---|---|
| 1 | 编译概览 | `cmd/compile/README.md`、`cmd/compile/internal/gc/` |
| 2 | 扫描器 Scanners | `compile/internal/syntax/{scanner,tokens}.go` |
| 3 | 解析器 Parsers | `compile/internal/syntax/parser.go` |
| 4 | 上下文敏感分析 / 类型 | `compile/internal/types2/` |
| 5 | 中间表示 IR | `compile/internal/{syntax,ir,noder,ssa}/` + `cmd/internal/obj` |
| 6 | 过程抽象 | `compile/internal/{abi,ssagen}/`、`ssa/expand_calls.go`、`cmd/compile/abi-internal.md` |
| 7 | 代码形态 Code Shape | `compile/internal/walk/` + `compile/internal/ssa/` |
| 8 | 优化导论 | `ssa/compile.go`（pass 序列）+ `compile/internal/inline/` |
| 9 | 数据流分析 | `ssa/dom.go`、`liveness/`、`ssagen/ssa.go`、`ssa/prove.go` |
| 10 | 标量优化 | `ssa/{deadcode,cse,licm,phiopt,magic,trim}.go` 等 |
| 11 | 指令选择 | `ssa/_gen/*.rules` → `ssa/rewrite*.go`、`ssa/lower.go` |
| 12 | 指令调度 | `ssa/schedule.go`、`ssa/layout.go` |
| 13 | 寄存器分配 | `ssa/regalloc.go`、`ssa/stackalloc.go` |
| 附录 A | ILOC 三地址码 | `cmd/internal/obj/link.go` 的 `Prog` |
| 附录 B | 数据结构 | `ssa/sparse*.go`、`compile/internal/bitvec/bv.go`、`ir/symtab.go` |

---

# 1. 正向索引：按书章节找源码

## Ch01 编译概览（Overview of Compilation）

**书的核心**：§1.2 编译器结构、§1.3 翻译总览（前端 / 优化器 / 后端三分法）。

| 书 § | 概念 | 源码位置 | 说明 |
|---|---|---|---|
| — | 编译器七阶段划分 | `cmd/compile/README.md` | **最权威的导览**，Go 自己把编译分成 Parsing / Type checking / Noding / Middle end / Walk / Generic SSA / Machine code 七步 |
| §1.3.1 前端 | 扫描 → 解析 → 类型检查 | `syntax/` + `types2/` | |
| §1.3.2 优化器 | 中端变换 | `inline/` `escape/` `devirtualize/` `walk/` `ssa/` | |
| §1.3.3 后端 | 指令选择、调度、分配 | `ssa/`(lower 起) + `cmd/internal/obj` | |
| — | 编译器入口 | `compile/internal/gc/main.go`、`compile/main.go` | 看 `Main()` 的调用序列即可对照书里的阶段流程图 |

> 建议：先读 `cmd/compile/README.md`（约 200 行），再读本章，两边阶段划分可直接对齐。

---

## Ch02 扫描器（Scanners）

**书的核心算法**：正则表达式 → NFA（Thompson 构造 §2.4.2）→ DFA（子集构造 §2.4.3）→ 最小 DFA（Hopcroft §2.4.4）；三种实现策略（表驱动 §2.5.1 / 直接编码 §2.5.2 / 手工编码 §2.5.3）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §2.2 识别单词 | 状态转移、前瞻 | `compile/internal/syntax/scanner.go` 的 `next()` | Go 的扫描器就是一个大 `switch` + 字符前瞻 |
| §2.3 正则表达式 | RE 形式化 | — | Go 扫描器**不用 RE 描述**；但完整实现见 `src/regexp/syntax/`（含 parse/simplify/compile） |
| §2.4.1 NFA | 非确定有限自动机 | `src/regexp/syntax/`（`prog.go`、`compile.go`） | 标准库实现，非编译器 |
| §2.4.2 Thompson 构造 | RE → NFA | `src/regexp/syntax/compile.go` | |
| §2.4.3 子集构造 | NFA → DFA | `src/regexp/syntax/`（`Compile` 后 `regexp.Compile` 的 onepass/DFA） | |
| §2.4.4 Hopcroft 最小化 | DFA 最小化 | — | Go 标准库未做最小化；这是纯理论学习点 |
| §2.5.3 手工编码扫描器 | hand-coded | **`syntax/scanner.go`** | Go 的选择：手写状态机，比表驱动快且易读 |
| §2.5.4 关键字处理 | 先标识符再查表 | `syntax/tokens.go` 的 `Lookup`、关键字 map | |

**阅读顺序**：`syntax/scanner.go`（约 900 行）→ `syntax/tokens.go`（token 定义与关键字表）。读完你会理解为什么工业编译器普遍选手写扫描器。

---

## Ch03 解析器（Parsers）

**书的核心算法**：CFG 与推导（§3.2）、自顶向下（递归下降 §3.3.2、LL(1) 表驱动 §3.3.3）、自底向上（LR(1) §3.4.1、LR 表构造 §3.4.2）、实际工程问题（错误恢复 §3.5.1、一元运算符 §3.5.2、上下文敏感歧义 §3.5.3、左右递归 §3.5.4）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §3.2.2 上下文无关文法 | 产生式、推导 | — | Go 的文法见 Go Spec；源码里没有产生式表 |
| §3.2.4 把语义编码进结构 | AST 设计 | `syntax/nodes.go` | 每个语法结构对应一个 Node 类型 |
| §3.3.1 文法变换 | 消除左递归、提取左公因子 | — | 手写解析器**绕开了**这些变换 |
| §3.3.2 递归下降解析器 | recursive descent | **`syntax/parser.go`** | Go 用无回溯递归下降 + **优先级爬升**（precedence climbing）处理二元表达式 |
| §3.3.3 LL(1) 表驱动 | 预测分析表 | — | Go 不用 |
| §3.4.1 / §3.4.2 LR(1) 与 LR 表 | 移进-归约、项集、表构造 | — | Go 不用；想对照可看 `goyacc`（`golang.org/x/tools/cmd/goyacc`） |
| §3.5.1 错误恢复 | panic-mode 恢复、同步记号 | `syntax/parser.go` 的错误处理与 `advance`；`types2/errors.go` | `-e` 标志控制是否继续报错（`syntax/parser.go` 的 `Mode`） |
| §3.5.2 一元运算符 | 优先级处理 | `syntax/parser.go` 的 `parseUnaryExpr` | 对比书里的 unary 优先级表 |
| §3.5.3 上下文敏感歧义 | `{` 是块还是复合字面量 | `syntax/parser.go` 的 `parseStmt`/`parseOperand`；`AllowGenerics`（`syntax/parser.go` 顶部 `Mode`） | **Go 最经典的歧义**：`if x == T{...}` 与泛型 `f[T]` |
| §3.5.4 左递归 vs 右递归 | 结合性 | `syntax/parser.go` 的 `parseBinaryExpr` | Go 用扩展优先级爬升 |
| §3.6.1 优化文法 | 减少产生式 | — | 手写解析器无此问题 |

---

## Ch04 上下文敏感分析 / 类型系统（Context-Sensitive Analysis）

**书的核心**：§4.2 类型系统、§4.3 **属性文法**（综合/继承属性、求值方法、循环性检测）、§4.4 **ad hoc 语法制导翻译**、§4.5 类型推断难题。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §4.2.1 类型系统的目的 | 类型检查、语义合法性 | `types2/type.go`、`types2/typeset.go` | |
| §4.2.2 类型系统的组成 | 类型规则、可赋值性 | `types2/assignments.go`、`types2/conversions.go`、`types2/operand.go` | |
| §4.3 属性文法框架 | 综合属性 / 继承属性 | — | Go **不使用**属性文法框架 |
| §4.3.1 求值方法 | 依赖图、拓扑排序 | — | 同上 |
| §4.3.2 循环性检测 | 属性依赖成环 | — | 同上；但**作用域成环检测**见 `types2/cycles.go`（非法递归类型） |
| §4.3.4 属性文法的问题 | 复杂度、内存 | — | 书在这里解释为什么工业界转向 ad hoc |
| §4.4.1 实现 ad hoc 语法制导翻译 | 访问者遍历 + 副作用 | **`types2/check.go`**（`Checker` 结构、`checkFiles`） | 这是 Go 采用的路线 |
| §4.4.2 实例 | 表达式/语句分派 | `types2/expr.go`、`types2/stmt.go`、`types2/decl.go`、`types2/call.go`、`types2/builtins.go`、`types2/lookup.go` | 按 Node 类型大 `switch` |
| — | 名称解析 | `types2/resolver.go`、`types2/scope.go`、`types2/object.go` | 两趟：先收集声明，再检查 |
| §4.5.1 类型推断难题 | 统一、约束求解 | **`types2/infer.go`**（类型参数推断）、`types2/instantiate.go`（实例化） | Go 泛型的核心；书里称为「更难的推断问题」 |
| §4.5.2 改变结合性 | 结合性调整 | `syntax/parser.go` | |
| — | 大小/对齐计算 | `types2/sizes.go`、`types2/gcsizes.go`、`compile/internal/types/size.go` | 桥接 §7.2.2 |

> 想彻底搞懂类型检查器，**先读 `src/go/types/` 而不是 `types2/`**：二者是同一套代码的两个端口，`go/types` 用 `go/ast`、注释更全、配套测试 35 个，是最佳入门材料。

---

## Ch05 中间表示（Intermediate Representations）

**书的核心**：§5.1.1 IR 分类（图式 / 线性）、§5.2 图式 IR（语法树、图）、§5.3 线性 IR（栈机码、三地址码、表示法、从线性码建 CFG）、§5.4 值与名字的映射（临时值命名、**SSA 形式**、内存模型）、§5.5 符号表。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §5.1.1 IR 分类 | graph vs linear | 三段式：`syntax`(AST) → `ir`(AST) → `ssa`(图) → `obj`(线性) | Go 同时用了两代 AST 和两种表示 |
| §5.2.1 语法相关树 | AST | `compile/internal/syntax/nodes.go`（解析 AST）、`compile/internal/ir/node.go`（编译器 AST） | 两代 AST 的转换在 `noder/` |
| §5.2.2 图 | CFG、SSA 图 | `ssa/block.go`（基本块与边）、`ssa/func.go`（函数容器）、`ssa/value.go`（值定义-使用链） | |
| §5.3.1 栈机码 | stack machine | — | Go 无此中间层 |
| §5.3.2 三地址码 | three-address code | **`cmd/internal/obj/link.go` 的 `Prog`**（`From` / `To` / `Reg` 三个操作数槽） | 与附录 A 的 ILOC 直接对应 |
| §5.3.3 表示线性代码 | 链表 / 数组 | `obj/plist.go` | `Prog` 是双向链表 |
| §5.3.4 从线性码建 CFG | leader 识别、边划分 | `ssa/block.go`、`ssagen/ssa.go` | Go 反过来：**先建 CFG 再生成 SSA** |
| §5.4.1 临时值命名 | 虚拟寄存器 | `ssa/value.go` 的 `Value.ID`、`ir/name.go` 的 `Name` | |
| §5.4.2 **SSA 形式** | φ 函数、定义唯一 | **`ssagen/ssa.go`**（构造）、`ssa/`（全体变换） | Go 的 SSA 是「块内值 + φ 合并」，与书一致 |
| §5.4.3 内存模型 | load/store、别名 | `ssa/` 的 `OpLoad`/`OpStore`、`ssa/memcombine.go`、`ssa/writebarrier.go` | Go 把内存建模为一条 `mem` 值链 |
| §5.5.1 哈希表 | 符号表实现 | `ir/symtab.go`、`types2/scope.go` | |
| §5.5.2 构建符号表 | 插入、查找 | `types2/resolver.go`、`types2/scope.go` | |
| §5.5.3 处理嵌套作用域 | scope 链 | `types2/scope.go`（`Scope` 有 `parent` 指针）、`ir/symtab.go` | 见附录 B §B.4.5 |
| §5.5.4 符号表的多种用途 | 类型、常量、跳转标签 | `types2/object.go`、`ir/name.go`、`ir/const.go` | |

> **Unified IR**（`noder/`）：Go 1.18 起把「noding」与「包导入导出」统一成一套序列化 IR 格式，实现见 `noder/reader.go`、`noder/writer.go`、`noder/unified.go`、`noder/irgen.go`。这是书里没有的现代工程实践，值得单独精读。

---

## Ch06 过程抽象（The Procedure Abstraction）

**书的核心**：§6.2 过程调用、§6.3 命名空间与运行时结构（活动记录、display）、§6.4 值传递（参数、返回值、可寻址性）、§6.5 标准链接约定、§6.6 堆管理。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §6.2 过程调用 | 调用序列、返回序列 | `ssa/expand_calls.go`、`ssagen/ssa.go` | |
| §6.3.1 Algol 式命名空间 | 静态作用域 | `types2/scope.go`、`ir/symtab.go` | |
| §6.3.2 支撑 Algol 的运行时结构 | 活动记录、帧指针、display | `ssa/stackalloc.go`（栈帧布局）、`ssa/location.go`、`cmd/compile/abi-internal.md` | Go 用 **静态链（static link）实现闭包**，不用 display：见 `walk/closure.go`、`ir/func.go` 的 `ClosureVars` |
| §6.3.3 / §6.3.4 OO 命名空间与运行时 | 方法表、动态分派 | `reflectdata/reflect.go`（itab 生成）、`ssa/` 的 `OpITab`、`src/internal/abi/iface.go` | Go 接口 = itab（类型 + 方法指针数组） |
| §6.4.1 传递参数 | 传值 / 传引用 / 传结果 | `compile/internal/abi/abiutils.go`（参数分类）、`abi-internal.md` | Go 全传值；寄存器优先（ABIInternal） |
| §6.4.2 返回值 | 返回机制 | `ssa/expand_calls.go`、`abiutils.go` | 多返回值 = 结构体返回 |
| §6.4.3 建立可寻址性 | 取地址、间接引用 | `walk/expr.go`、`escape/`（决定栈/堆） | 逃逸变量必须堆分配才能取址 |
| §6.5 标准化链接约定 | calling convention、符号命名 | **`cmd/compile/abi-internal.md`**（必读）、`src/internal/abi/`、`cmd/internal/goobj/` | ABI0 / ABIInternal 两套约定与 wrapper |
| §6.6.1 显式堆管理 | malloc / free | — | Go 无手动管理；GC 见 `src/runtime/mgc.go` |
| §6.6.2 隐式释放 | GC、引用计数 | `escape/escape.go`（逃逸分析）、`src/runtime/malloc.go` | 逃逸分析把该在堆上的变量判出来 |

> 本章与 `abi-internal.md` 配合读效果最好：书讲通用原理，Go 文档讲具体寄存器分配方案（如 amd64 的 9 个整数参数寄存器）。
>
> **本章 + Ch07 §7.9 + Ch11 §11.2 + Ch13 的 ABI 专题总结见 [`go_abi.md`](./go_abi.md)**：那里把"一次调用被拆成 precall/postreturn/prologue/epilogue 四段"讲透，并逐条对照 Go 的 ABI0/ABIInternal、参数分类算法、无 callee-save 设计与 spill space 预留。

---

## Ch07 代码形态（Code Shape）

**这是与 Go 源码对应最直接、最适合「边读代码边看书」的一章** —— `walk` 包的职责（降糖 + 定序）几乎就是本章的标题。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §7.2.1 放置运行时数据结构 | 全局/静态/栈/堆 | `compile/internal/staticdata/data.go`、`ssa/stackalloc.go`、`escape/` | |
| §7.2.2 数据区布局 | 记录布局、对齐、填充 | `compile/internal/types/size.go`、`reflectdata/`、`rttype/rttype.go` | |
| §7.2.3 值保存在寄存器 | 寄存器 vs 内存 | `ssa/location.go`、`ssa/regalloc.go` | 桥接 Ch13 |
| §7.3.1 降低寄存器需求 | 求值顺序、重结合 | **`walk/order.go`**（定序）、`ssa/tighten.go` | 「order」是 Go 对 §7.3.1 的实现 |
| §7.3.2 访问参数值 | 形参寻址 | `walk/expr.go`、`ssagen/` 的 `OpArg` | |
| §7.3.3 表达式中的函数调用 | 求值顺序副作用 | `walk/order.go`（`Order` 函数族） | |
| §7.3.4 其他算术运算符 | 溢出、位运算、移位 | `walk/expr.go`、`ssa/_gen/generic.rules` | |
| §7.3.5 混合类型表达式 | 隐式转换 | `walk/convert.go`、`walk/expr.go` | |
| §7.3.6 赋值作为运算符 | 赋值表达式 | `walk/assign.go` | |
| §7.4.1 布尔值表示 | 标志位 vs 字节 | `walk/compare.go`、`ssa/` 的 `OpFlags`、`ssa/phiopt.go` | Go 在 SSA 中把比较结果具化为值 |
| §7.4.2 硬件对关系运算的支持 | 条件码、`setcc` | `ssa/_gen/*.rules`（AMD64 的 `SETcc` 规则） | |
| §7.4.1 短路求值 | `&&` / `||` | **`ssa/shortcircuit.go`** | |
| §7.5.1–7.5.3 数组存取 | 地址计算、行主序 | `walk/expr.go`（索引）、`ssa/addressingmodes.go` | |
| §7.5.4 **范围检查** | bounds check | `ssa/checkbce.go`（生成）、`ssa/loopbce.go`（归纳变量消除）、`ssa/prove.go` | Go 的 BCE 是本书 §7.5.4 的完整工业实现，且有独立测试 `test/checkbce.go` |
| §7.6.1–7.6.4 字符串 | 表示、赋值、连接、长度 | `walk/expr.go`、`src/runtime/string.go` | Go 字符串 = (ptr, len) |
| §7.7.1 / §7.7.2 结构布局与结构数组 | 偏移计算 | `walk/complit.go`、`types/size.go` | |
| §7.7.3 联合与运行时标签 | tagged union | — | Go 无 union；最近的类比是 **interface 的 itab + data 双字**（`src/internal/abi/iface.go`） |
| §7.7.4 指针与匿名值 | 悬垂指针、别名 | `escape/escape.go`、`ssa/` 的 `OpLoad`/`OpStore` | |
| §7.8.1 条件执行 | if、跳转、条件移动 | `walk/stmt.go`、**`ssa/phiopt.go`**（生成条件移动） | |
| §7.8.2 **循环与迭代** | 归纳变量、循环结构 | `walk/range.go`（range 脱糖）、`ssa/looprotate.go`（循环旋转）、`ssa/loopbce.go`、`ssa/licm.go`、`ssa/downward_counting_loop.go` | |
| §7.8.3 **case 语句** | 二分搜索 / 跳转表 | **`walk/switch.go`**（脱糖决策）、`ssa/` 的 `OpJumpTable` | 书里讲「何时用跳转表、何时用二分」；Go 的选择逻辑就在 `walk/switch.go` |
| §7.9.1 求值实参 | 实参求值顺序 | `walk/order.go`、`walk/temp.go` | |
| §7.9.2 保存恢复寄存器 | caller-save / callee-save | `compile/internal/abi/abiutils.go`、各架构 `ssa.go` 的 `regInfo.clobbers` | |

> **首推读物**：`walk/switch.go`（约 700 行）——它把 §7.8.3 的决策过程写得明明白白，是「书 → 代码」最平滑的一处。

---

## Ch08 优化导论（Introduction to Optimization）

**书的核心**：§8.3 优化范围（局部/区域/全局/过程间）、§8.4 局部优化（值编号、树高平衡）、§8.5 区域优化（SVN、循环展开）、§8.6 全局优化（活跃信息、全局代码布置）、§8.7 过程间优化（内联替换、过程布置）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §8.2.2 优化的考量 | 安全性、收益、编译时间 | `ssa/compile.go` 顶部的 pass 注释 | |
| §8.2.3 优化机会 | 冗余、常量、死代码 | `ssa/` 各 pass | |
| §8.3 优化范围 | local / regional / global / interprocedural | **`ssa/compile.go` 的 `passes` 数组** | 这个数组就是 Go 的「优化序列」，直接体现了 §8.3 的分层；也是 §10.7.3 的实例 |
| §8.4.1 局部值编号 | LVN | `ssa/cse.go`、`ssa/zcse.go`（零值 CSE） | |
| §8.4.2 树高平衡 | tree-height balancing | — | Go **没有**这个 pass |
| §8.5.1 超局部值编号 | SVN（跨基本块） | `ssa/cse.go` | Go 的 CSE 直接做到全局（基于支配树），跳过了 SVN 阶段 |
| §8.5.2 循环展开 | loop unrolling | — | Go **不做循环展开**（编译时间与代码体积权衡） |
| §8.6.1 用活跃信息找未初始化变量 | live variable | `compile/internal/liveness/plive.go`（GC 活性位图）、`liveness/intervals.go` | Go 的 liveness 服务 GC 安全点，不是未初始化变量检查 |
| §8.6.2 全局代码布置 | 代码顺序优化 | `ssa/layout.go`（基本块排序）、`ssa/likelyadjust.go`（分支概率） | |
| §8.7.1 **内联替换** | inline substitution | **`compile/internal/inline/inl.go`**、`inline/inlheur/`、`inline/interleaved/` | 两趟：`CanInline` 判定 + `InlineCalls` 展开 |
| §8.7.2 过程布置 | 函数排列减少缺页 | `cmd/link/internal/ld/` 的符号排序、`ssa/layout.go` | |
| §8.7.3 支持 IPO 的编译器组织 | 摘要、调用图、持久化 | **`compile/internal/noder/`**（Unified IR 导出内联体）、`compile/internal/pgoir/`（PGO 调用图）、`cmd/preprofile/` | Go 通过 Unified IR 把函数体导出为「可内联摘要」 |

---

## Ch09 数据流分析（Data-Flow Analysis）

**书的核心**：§9.2 迭代数据流（支配 §9.2.1、活跃变量 §9.2.2、其他问题 §9.2.4）、§9.3 **SSA 形式**（构造 §9.3.1、支配边界 §9.3.2、φ 放置 §9.3.3、重命名 §9.3.4、出 SSA §9.3.5）、§9.4 过程间分析（调用图 §9.4.1、常量传播 §9.4.2）、§9.5 高级主题（结构化算法与可归约性 §9.5.1、加速迭代支配 §9.5.2）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §9.2.1 **支配** | 支配树、直接支配者 | **`ssa/dom.go`** | 一个文件里实现了两种教科书算法：`dominatorsLTOrig`（**Lengauer-Tarjan**）与 `dominatorsSimple`（**迭代式 intersection**，即 Cooper-Harvey-Kennedy） |
| §9.5.2 加速迭代支配框架 | 后序编号 + intersect | `ssa/dom.go` 的 `dominatorsSimple`、`postorder`、`intersect` | **书里的优化在这里有完整代码** |
| — | 最近公共祖先 | `ssa/lca.go` | O(1) 查询的 LCA 数据结构 |
| §9.2.2 活跃变量分析 | live variable | `liveness/plive.go`（GC 安全点活性）、`ssa/regalloc.go` 内的 liveness | 目的不同：书用于优化，Go 用于 GC 位图与寄存器分配 |
| §9.2.4 其他数据流问题 | 可达定义、可用表达式、常量传播 | `ssa/sccp.go`（**Wegman-Zadeck 稀疏条件常量传播**）、`ssa/prove.go`（值域分析）、`ssa/known_bits.go` | 三个都是数据流框架的实例 |
| — | 指向/别名分析 | `escape/escape.go` | 书里未展开；Go 实现为**有向加权图上的静态数据流分析** |
| §9.3.1 构建 SSA 的简单方法 | 插入 φ 后重命名 | `ssagen/ssa.go` | Go 边遍历 IR 边建 SSA 边插 φ，不做独立的 CFG→SSA 转换 |
| §9.3.2 **支配边界** | dominance frontier | `ssagen/ssa.go` + `ssa/` 的 φ 生成逻辑 | 对比书里的 Cytron 算法 |
| §9.3.3 放置 φ 函数 | φ placement | `ssagen/ssa.go` | |
| §9.3.4 重命名 | 变量重命名 | `ssagen/ssa.go` | |
| §9.3.5 **从 SSA 翻译出去** | 出 SSA、泄漏到栈 | **`ssa/regalloc.go`**（`spill`/`reload`） | SSA 在寄存器分配阶段被销毁 |
| §9.3.6 使用 SSA | 基于 SSA 的优化 | 整个 `ssa/` 包 | |
| §9.4.1 调用图构建 | call graph | `compile/internal/pgoir/irgraph.go`、`cmd/internal/pgo/`、`ssa/` 的调用边 | |
| §9.4.2 过程间常量传播 | IPCP | `inline/` + Unified IR 导出体、`ssa/sccp.go` | 内联后 SCCP 自然获得跨过程效果 |
| §9.5.1 结构化算法与可归约性 | reducibility | `ssa/looprotate.go`、`ssa/dom.go` 的循环发现 | |

---

## Ch10 标量优化（Scalar Optimizations）

**书的核心**：§10.2 消除无用/不可达代码、§10.3 代码移动（LCM、提升）、§10.4 特化（尾调用、叶调用、参数提升）、§10.5 冗余消除（值编号）、§10.6 使能其他变换（克隆、循环外提、重命名）、§10.7 高级（强度削减、优化序列选择）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §10.2.1 消除无用代码 | dead code elimination | `ssa/deadcode.go`、`ssa/deadstore.go` 的 `dse`、`ssa/trim.go` | Go 在 pass 序列中多次运行 deadcode（见 `ssa/compile.go`） |
| §10.2.2 消除无用控制流 | 空块、无用跳转 | `ssa/branchelim.go`（分支消除）、`ssa/phiopt.go`、`ssa/shortcircuit.go`、`ssa/copyelim.go`（φ 消除） | |
| §10.2.3 消除不可达代码 | unreachable | `ssa/deadcode.go` | |
| §10.3.1 惰性代码移动 LCM | partial redundancy elimination | — | Go **没有**完整的 LCM/PRE |
| §10.3.2 **代码提升** | hoisting | **`ssa/licm.go`**（循环不变代码外提）、`ssa/loopreschedchecks.go` | 文件头有完整的循环结构 ASCII 图，极适合对照阅读 |
| §10.4.1 **尾调用优化** | TCO | `ir/stmt.go` 的 `TailCallStmt`、`ssa/expand_calls.go`、各架构 `*.rules` 的 `(TailCall ...) => (CALLtail ...)` | **重要**：Go 只在**编译器自生成的 ABI wrapper / 泛型 shim** 上用尾调用（见 `ssagen/abi.go:323`），**不对用户代码做通用尾调用消除**——因为栈需要增长。调试开关 `-d=tailcall` |
| §10.4.2 叶函数优化 | leaf-call | `ssa/stackalloc.go`、`ssa/regalloc.go`、`abi/abiutils.go` | 叶函数无需栈分裂检查与寄存器保存 |
| §10.4.3 参数提升 | parameter promotion | `abi/abiutils.go`、`ssa/` 的 `OpArg`/`OpStore` | 参数直接进寄存器而非内存 |
| §10.5.1 值同一性 vs 名字同一性 | value numbering | `ssa/cse.go` | 文件头注释给出了精确的 `equivalent(v, w)` 定义 |
| §10.5.2 **基于支配者的值编号** | dominator-based VN | **`ssa/cse.go`** | Go 的 CSE 就是基于支配树的值编号，与书 §10.5.2 直接对应 |
| §10.6.1 超块克隆 | superblock cloning | — | 无 |
| §10.6.2 过程克隆 | procedure cloning | `ssa/branchelim.go`（部分）、`pgoir/` | |
| §10.6.3 循环外提 | loop unswitching | — | 无 |
| §10.6.4 重命名 | renaming | `ssa/regalloc.go`（寄存器重命名）、`ssa/tighten.go`（把值移近使用点，含 `phiTighten`） | |
| §10.7.1 组合优化 | 多优化协同 | `ssa/compile.go` 的 `passes` | |
| §10.7.2 **强度削减** | strength reduction | `ssa/magic.go`（除法→乘法幻数）、`ssa/_gen/generic.rules`、`ssa/decompose.go`、`ssa/rewritegeneric.go` | `magic.go` 是「除法变乘法」的教科书实现，很短很好读 |
| §10.7.3 选择优化序列 | pass ordering | **`ssa/compile.go:458-519` 的 `passes` 数组** | 直接读源码就能看到 Go 的完整优化流水线 |

---

## Ch11 指令选择（Instruction Selection）

**书的核心**：§11.2 代码生成、§11.3 扩展树遍历、§11.4 **树模式匹配**（重写规则 §11.4.1、寻找铺盖 §11.4.2、工具 §11.4.3）、§11.5 **窥孔优化**。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §11.2 代码生成 | 从 IR 到汇编 | `ssa/lower.go`、各架构 `compile/internal/<arch>/ssa.go` | |
| §11.3 扩展树遍历 | treewalk 选择器 | `ssa/rewrite.go`（规则引擎的核心 `rewriteValue`） | |
| §11.4.1 **重写规则** | rewrite rules | **`ssa/_gen/*.rules`**（`AMD64.rules`、`ARM64.rules`、`generic.rules` …） | 这就是 Go 的「重写规则表」，语法为 `(目标) => (替换) when (条件)` |
| §11.4.2 **寻找铺盖** | tiling | `ssa/rewrite.go` 的驱动逻辑 + `_gen/rulegen.go` | Go 用自下而上的贪心重写逼近最优铺盖 |
| §11.4.3 工具（BURG / iburg） | 自动生成选择器 | **`ssa/_gen/rulegen.go`、`ssa/_gen/main.go`** | Go 自研的规则编译器，等价于书里的 BURG |
| — | 规则生成闭环 | `_gen/*Ops.go`（算子定义）→ `main.go` → `rewrite*.go` + `opGen.go` | `cd compile/internal/ssa/_gen && go generate` |
| §11.5.1 / §11.5.2 **窥孔优化** | peephole | `ssa/_gen/*latelower.rules`、`*splitload.rules`（如 `AMD64latelower.rules`）、`ssa/addressingmodes.go`、`ssa/pair.go` | 「late lower」阶段就是窥孔层 |
| §11.6.2 生成指令序列 | 发射机器码 | `cmd/internal/obj/`（含 `x86/`、`arm64/` 等子目录）、各架构 `ggen.go` | |

> 从 `ssa/_gen/generic.rules` 开始读规则最轻松（机器无关），再到 `AMD64.rules` 看架构特化。

---

## Ch12 指令调度（Instruction Scheduling）

**书的核心**：§12.2 调度问题（度量、难点）、§12.3 **局部表调度**（算法 §12.3.1、可变延迟 §12.3.2、优先级打破平局 §12.3.4、前向 vs 后向 §12.3.5、效率优化 §12.3.6）、§12.4 区域调度（EBB、踪迹调度、克隆）、§12.5 软件流水线。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §12.2 调度问题 | 延迟、流水线、度量 | `ssa/schedule.go` 顶部注释 | |
| §12.2.2 调度为何困难 | NP 完全、依赖约束 | 同上 | |
| §12.3.1 **表调度算法** | list scheduling | **`ssa/schedule.go`** | Go 的基本块内表调度，用 `ValHeap` 做优先队列 |
| §12.3.3 扩展算法 | 多周期操作 | `ssa/schedule.go`、各架构 `ssa.go` 的延迟信息 | |
| §12.3.4 **打破平局** | 优先级函数 | `ssa/schedule.go` 的 `Score*` 常量（`ScorePhi`、`ScoreMemory`、`ScoreControl`…） | Go 用一组分层的 score 常量决定次序，非常直观 |
| §12.3.5 前向 vs 后向调度 | forward/backward | `ssa/schedule.go` | |
| §12.3.6 提高表调度效率 | 优先队列、按块划分 | `ssa/schedule.go` 的 `ValHeap`（`container/heap` 实现） | |
| §12.4.1 调度扩展基本块 | EBB | — | Go 只做单基本块 |
| §12.4.2 **踪迹调度** | trace scheduling | — | Go **不做**踪迹调度 |
| §12.4.3 为上下文克隆 | cloning | `ssa/looprotate.go`（部分） | |
| §12.5 软件流水线 | software pipelining | — | Go **不做** |
| — | 基本块排列（书 §8.6.2） | **`ssa/layout.go`**、`ssa/likelyadjust.go` | 属「全局调度」范畴，Go 有实现 |

---

## Ch13 寄存器分配（Register Allocation）

**书的核心**：§13.2 背景（内存 vs 寄存器、分配 vs 指派、寄存器类）、§13.3 局部分配（自顶向下/自底向上）、§13.4 **全局分配与指派**（活跃区间、溢出代价、冲突图、自顶向下着色、自底向上着色、合并拷贝、编码机器约束）、§13.5 高级（着色变体、**基于 SSA 的全局分配**）。

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §13.2.1 内存 vs 寄存器 | 溢出代价 | `ssa/regalloc.go` 的 `Spilling` 注释段 | |
| §13.2.2 分配 vs 指派 | allocation / assignment | `ssa/regalloc.go`（统一处理）、`ssa/location.go` | |
| §13.2.3 寄存器类 | 整数/浮点/标志 | 各架构 `ssa.go` 的 `registers` 表（`GP`/`FP`/`SP` 掩码）、`ssa/flagalloc.go`（标志寄存器） | |
| §13.3.1 / §13.3.2 局部寄存器分配 | top-down / bottom-up local | `ssa/regalloc.go` | Go 是**线性扫描（linear scan）**，按块顺序贪心分配 |
| §13.3.3 超越单基本块 | 跨块传递 | `ssa/regalloc.go`（沿支配树向下传递状态，合并边插入 shuffle） | 文件头注释写得很清楚 |
| §13.4.1 发现全局活跃区间 | live range | `ssa/regalloc.go` 的 `live` 数组与 `getHome` | |
| §13.4.2 **估计溢出代价** | spill cost | **`ssa/regalloc.go`** 的 `spill()` / `desperate` 逻辑；`ssa/stackalloc.go` | 书里用「下次使用最远」启发式，Go 同样如此 |
| §13.4.3 **冲突图** | interference graph | **`ssa/stackalloc.go` 的 `interfere`** | 有趣的反差：Go 把冲突图用在**栈槽分配**上，寄存器分配反而不用 |
| §13.4.4 / §13.4.5 自顶向下 / 自底向上着色 | graph coloring | — | Go 不用图着色做寄存器分配（想读着色实现看 `cmd/compile` 之外的项目，如 LLVM、Go 早期版本） |
| §13.4.6 **合并拷贝以降低度数** | coalescing | `ssa/copyelim.go`、`ssa/regalloc.go` 的同寄存器合并 | |
| §13.4.8 编码机器约束 | 预着色、约束寄存器 | 各架构 `ssa.go` 的 `regInfo`（`inputs`/`clobbers`/`outputs` 掩码）、`ssa/_gen/*Ops.go` | 约束在算子定义阶段就编码好了 |
| §13.5.1 着色变体 | Chaitin-Briggs、George 等 | — | 无 |
| §13.5.2 **基于 SSA 的全局寄存器分配** | SSA-based RA | **`ssa/regalloc.go`** | Go 直接在 SSA 形式上做分配，是书 §13.5.2 的工业实例 |
| — | 栈帧布局与溢出槽 | `ssa/stackalloc.go`（含局部变量合并 `mergelocals`、`liveness/mergelocals.go`） | |

---

## 附录 A：ILOC 三地址码

| 书 § | 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §A.2 命名约定 | 虚拟寄存器、立即数 | `cmd/internal/obj/link.go` 的 `Addr`、`Reg`、`RegTo2` | |
| §A.3.1–§A.3.4 算术/移位/内存/寄存器拷贝 | 指令分类 | `cmd/internal/obj/x86/anames.go` 等各架构指令表；`compile/internal/objw/prog.go`（生成 `Prog`） | |
| §A.4.1 比较与分支 | `cmpxx` + `br` | `obj/pass.go`、各架构 `obj/<arch>/` | |
| §A.4.2 跳转 | label、jump | `obj/plist.go`、`obj/link.go` 的 `Prog.Link` | |
| §A.5 表示 SSA | SSA 的线性编码 | — | Go 的 SSA 只存在于编译器内部，不进入目标文件 |

> `Prog` 结构（`cmd/internal/obj/link.go:304`）的 `From` / `To` / `Reg` / `RegTo2` 四个槽就是 ILOC 式三地址码的工程变体。

---

## 附录 B：数据结构

| 书 § | 算法 / 概念 | 源码位置 | 说明 |
|---|---|---|---|
| §B.2.1 用有序表表示集合 | sorted list | `ssa/`（部分索引结构）、`cmd/internal/obj/` 的排序表 | |
| §B.2.2 **位向量表示集合** | bit vector | **`compile/internal/bitvec/bv.go`**、`ir/bitset.go`、`liveness/bvset.go` | 三个不同层次的位集实现 |
| §B.2.3 **稀疏集合** | sparse set（O(1) 增删查） | **`ssa/sparseset.go`、`ssa/sparsemap.go`、`ssa/sparsemappos.go`、`ssa/sparsetree.go`、`ssa/biasedsparsemap.go`** | Go 是稀疏集合的重度用户；`poset.go` 是偏序集 |
| §B.3.1 实现图式 IR | 节点/边表示 | `ir/node.go`、`ssa/block.go`、`ssa/value.go` | 对比两种实现的取舍 |
| §B.3.2 实现线性 IR | 数组 vs 链表 | `cmd/internal/obj/link.go` 的 `Prog.Link`（链表） | |
| §B.4.1 选择哈希函数 | 散列 | `types2/` 与 `types` 的 map 使用、`ssa/func.go` 的值索引 | Go 主要用语言内置 map，哈希函数在 `src/runtime/map*.go` |
| §B.4.2 / §B.4.3 开放哈希 / 开放寻址 | 冲突处理 | `src/runtime/map.go` + `map_fast32.go` / `map_fast64.go` / `map_faststr.go` | Go 1.24+ 的 map 实现（按 key 类型特化） |
| §B.4.4 存储符号记录 | symbol record | `types2/object.go`、`ir/name.go`、`cmd/internal/goobj/` | |
| §B.4.5 **增加嵌套词法作用域** | scope 栈 | **`types2/scope.go`**（`parent` 链）、`ir/symtab.go` | |
| §B.5 灵活的符号表设计 | 多用途符号表 | `types2/scope.go` + `types2/object.go` + `ir/symtab.go` | |

---

# 2. 反向索引：按源码找章节

## `compile/internal/syntax/` — 前端

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `scanner.go` | 手工编码扫描器、字符前瞻 | §2.2, §2.5.3 |
| `tokens.go` | Token 定义、关键字表与查找 | §2.5.4 |
| `parser.go` | 无回溯递归下降、优先级爬升、错误恢复、上下文歧义 | §3.3.2, §3.5.1, §3.5.2, §3.5.3, §3.5.4 |
| `nodes.go` | 语法树节点（AST） | §3.2.4, §5.2.1 |
| `branches.go` | 语句分支枚举（供常量折叠用） | §5.2.1 |

## `compile/internal/types2/` — 类型检查

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `check.go` | ad hoc 语法制导翻译的驱动器 | §4.4.1 |
| `expr.go` / `stmt.go` / `decl.go` / `call.go` / `builtins.go` | 分派到各语法结构的检查规则 | §4.4.2 |
| `assignments.go` / `conversions.go` / `operand.go` | 可赋值性、转换规则 | §4.2.2 |
| `infer.go` / `instantiate.go` / `mono.go` | 类型参数推断、实例化 | §4.5.1 |
| `resolver.go` / `scope.go` / `object.go` | 名称解析、作用域链、符号表 | §5.5.1–5.5.4, §B.4.5 |
| `cycles.go` | 非法递归类型检测 | §4.3.2（循环性概念） |
| `sizes.go` / `gcsizes.go` | 类型大小与对齐 | §7.2.2 |
| `errors.go` | 错误收集与报告 | §3.5.1 |

## `compile/internal/ir/` — 编译器内部 AST

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `ir.go` / `node.go` / `node_gen.go` | 编译器 AST 节点定义 | §5.2.1 |
| `expr.go` / `stmt.go` | 表达式与语句节点 | §5.2.1 |
| `symtab.go` | 包级符号表 | §5.5.2, §B.5 |
| `name.go` / `type.go` / `const.go` / `val.go` | 名字、类型、常量值 | §5.4.1, §5.5.4 |
| `func.go` | 函数表示、闭包捕获变量 | §6.3.2 |
| `bitset.go` | 位集 | §B.2.2 |
| `scc.go` | 强连通分量（初始化顺序） | §9.4.1 |
| `cfg.go` | 控制流图（ir 层） | §5.3.4 |
| `stmt.go` 的 `TailCallStmt` | 尾调用语句表示（仅供编译器自生成代码） | §10.4.1 |

## `compile/internal/noder/` — Unified IR（noding + 导入导出）

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `irgen.go` | 语法树 → 编译器 AST | §5.2.1, §5.4 |
| `reader.go` / `writer.go` / `unified.go` | IR 序列化 / 反序列化 | §8.7.3 |
| `import.go` / `export.go` | 包的导入导出 | §5.5, §8.7.3 |
| `posmap.go` | 位置信息映射 | §5.2.1（位置信息） |
| `quirks.go` / `codes.go` / `helpers.go` | 格式细节 | — |

## `compile/internal/walk/` — 降糖与定序（对应 Ch07 整章）

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `order.go` | 求值顺序、引入临时变量 | §7.3.1, §7.3.3, §7.9.1 |
| `stmt.go` | 条件执行、语句降糖 | §7.8.1 |
| `switch.go` | case 语句脱糖：二分 / 跳转表决策 | **§7.8.3** |
| `range.go` | range 循环脱糖 | §7.8.2 |
| `assign.go` | 赋值（含复合赋值）降糖 | §7.3.6 |
| `expr.go` | 索引、切片、字符串、取址 | §7.5, §7.6, §7.7.4 |
| `compare.go` | 布尔与关系运算 | §7.4.1 |
| `convert.go` | 混合类型转换 | §7.3.5 |
| `complit.go` | 复合字面量（结构体/数组/切片/map） | §7.7.1, §7.7.2 |
| `closure.go` | 闭包实现（静态链） | §6.3.2 |
| `select.go` | select 语句脱糖 | §7.8.3 |
| `builtin.go` | 内建函数展开（append/copy/len…） | §7.5, §7.6 |
| `temp.go` | 临时变量分配 | §5.4.1 |

## `compile/internal/escape/`

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `escape.go` | 有向加权图上的静态数据流分析，判定栈/堆 | §9.2.4（数据流实例）, §6.6.2 |
| `graph.go` / `solve.go` / `stmt.go` / `expr.go` 等 | 图的构建与求解 | §9.2 |

## `compile/internal/inline/`

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `inl.go` | 两趟内联（判定 + 展开）、内联代价模型 | **§8.7.1** |
| `inlheur/` | 内联启发式（收益模型） | §8.7.1 |
| `interleaved/` | 内联与优化的交错执行 | §10.7.1（组合优化） |

## `compile/internal/ssagen/`

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `ssa.go` | IR → SSA 转换、φ 插入、内建函数识别 | **§9.3.1–9.3.4**, §5.4.2 |
| `abi.go` | ABI wrapper 生成、调用序列 | §6.2, §6.5 |

## `compile/internal/ssa/` — 中后端核心（按书章节分组）

**输入/结构**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `func.go` / `block.go` / `value.go` | 图式 IR：函数、基本块、值 | §5.2.2, §B.3.1 |
| `op.go` / `opGen.go` | 算子定义（含寄存器约束） | §13.4.8 |
| `config.go` / `cpufeatures.go` | 架构配置与 CPU 特性 | §11.2 |
| `compile.go` | **pass 序列**、依赖检查 | §8.3, §10.7.3 |
| `print.go` / `html.go` / `debug.go` | 调试输出（`-d=ssa/...`） | — |

**数据流与分析**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `dom.go` | 支配树（Lengauer-Tarjan + 迭代 intersect） | **§9.2.1, §9.5.2** |
| `lca.go` | 支配树上的 LCA | §9.2.1 |
| `sccp.go` | 稀疏条件常量传播（Wegman-Zadeck） | §9.2.4 |
| `prove.go` | 值域分析、边界证明 | §9.2.4, §7.5.4 |
| `known_bits.go` | 已知位分析 | §9.2.4 |
| `cse.go` | 基于支配树的值编号 | **§10.5.1, §10.5.2** |
| `zcse.go` | 零值 CSE | §10.5.1 |

**优化 pass**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `deadcode.go` / `deadstore.go`(`dse`) / `trim.go` | 死代码、死存储、空块消除 | §10.2.1, §10.2.3 |
| `copyelim.go` | 拷贝与 φ 消除 | §10.2.2 |
| `phiopt.go` | φ 优化 → 条件移动 | §7.8.1, §10.2.2 |
| `branchelim.go` | 分支消除 | §10.2.2 |
| `shortcircuit.go` | 短路求值消除 | §7.4.1 |
| `licm.go` | 循环不变代码外提 | **§10.3.2** |
| `loopbce.go` / `checkbce.go` | 归纳变量范围检查消除 | **§7.5.4** |
| `nilcheck.go` | nil 检查消除 | §10.2.1 |
| `tighten.go` | 把值移近使用点（缩短活跃区间） | §10.6.4 |
| `magic.go` | 除法 → 乘法幻数（强度削减） | **§10.7.2** |
| `decompose.go` | 复合操作拆解 | §10.7.2 |
| `memcombine.go` | 内存操作合并 | §11.5（窥孔） |
| `fuse.go` | 操作融合 | §11.5（窥孔） |
| `pair.go` | 值配对 | §11.5 |
| `addressingmodes.go` | 寻址模式匹配（x86 等） | **§11.5.2** |
| `writebarrier.go` | 写屏障展开（Go 特有） | — |
| `softfloat.go` | 软浮点（无 FPU 架构） | §11.2 |
| `downward_counting_loop.go` | 倒数循环识别 | §7.8.2, §10.7.2 |

**指令选择与调度**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `rewrite.go` | 重写引擎（规则匹配与应用） | **§11.4.1, §11.4.2** |
| `rewritegeneric.go` / `rewrite<ARCH>.go` | 生成的重写规则（机器无关 / 机器相关） | **§11.4** |
| `_gen/*.rules` | **重写规则源文件**（唯一的规则真源） | **§11.4.1** |
| `_gen/*Ops.go` | 算子与寄存器约束定义 | §13.4.8 |
| `_gen/rulegen.go` / `main.go` | 规则编译器（等价 BURG） | **§11.4.3** |
| `lower.go` | 降级到机器相关算子 | §11.2, §11.3 |
| `schedule.go` | 基本块内表调度 | **§12.3.1, §12.3.4, §12.3.6** |
| `layout.go` | 基本块排列 | §8.6.2 |
| `likelyadjust.go` | 分支概率调整 | §8.6.2 |
| `looprotate.go` | 循环旋转（转成 counted loop） | §7.8.2 |
| `loopreschedchecks.go` | 循环内栈调整检查 | §12.4 |

**寄存器分配与栈**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `regalloc.go` | **线性扫描寄存器分配**、溢出、合并边 shuffle、SSA 销毁 | **§13.3, §13.4.1, §13.4.2, §13.5.2, §9.3.5** |
| `stackalloc.go` | 栈槽分配、**冲突图**、局部变量合并 | **§13.4.3**, §7.2.1 |
| `flagalloc.go` | 标志寄存器分配 | §13.2.3 |
| `location.go` | 值的位置（寄存器/栈）抽象 | §13.2.2 |
| `expand_calls.go` | 调用展开、ABI 参数传递、tail call | §6.2, §6.4.1, §10.4.1 |
| `poset.go` | 偏序集（供 `prove.go` 做约束求解，增量维护可达性） | §B.2.3 |

**基础设施**

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `sparseset.go` / `sparsemap.go` / `sparsemappos.go` / `biasedsparsemap.go` | 稀疏集合与稀疏映射 | **§B.2.3** |
| `sparsetree.go` | 稀疏树（循环嵌套） | §B.2.3 |
| `cache.go` / `allocators.go` | 复用分配器 | §B（数据结构工程化） |
| `check.go` | SSA 内部一致性校验（`-d=ssa/check/on`） | — |
| `lower.go` 的 `checkLower` | 降级后校验 | — |

## `compile/internal/liveness/`

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `plive.go` | GC 安全点的指针活性分析（数据流） | **§9.2.2**, §8.6.1 |
| `intervals.go` | 活跃区间计算 | §13.4.1 |
| `bvset.go` | 位集（blocks × vars） | §B.2.2 |
| `mergelocals.go` | 局部变量槽合并 | §13.4.3 |
| `arg.go` | 参数活性 | §6.4.1 |

## `compile/internal/{abi,types,staticdata,reflectdata,rttype,bitvec}/`

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `abi/abiutils.go` | 参数/返回值分类到寄存器与栈 | **§6.4.1, §6.4.2** |
| `types/size.go` / `types/type.go` | 类型布局、大小、对齐 | §7.2.2 |
| `bitvec/bv.go` | 位向量集合 | **§B.2.2** |
| `staticdata/data.go` / `embed.go` | 静态数据对象生成 | §7.2.1 |
| `reflectdata/reflect.go` / `alg.go` / `map.go` | 反射元数据、itab、map 类型描述 | §6.3.3, §7.7.3 |
| `rttype/rttype.go` | 运行时类型描述（`_type` 结构） | §6.3.3 |

## `cmd/internal/obj/` — 汇编器与机器码

| 文件 | 算法 / 概念 | 书章节 |
|---|---|---|
| `link.go` 的 `Prog` | 三地址码指令表示 | **附录 A §A.2–A.4** |
| `link.go` 的 `Addr` / `Sym` | 操作数与符号 | §5.3.3, §B.3.2 |
| `plist.go` | 指令链表管理 | §5.3.3, §B.3.2 |
| `pass.go` | 指令遍历（peephole 遍历器） | §11.5.1 |
| `x86/` `arm64/` `arm/` … | 各架构指令编码 | §11.6.2 |
| `objw/prog.go`（在 `compile/internal/objw/`） | 由 SSA 生成 `Prog` | §11.6.2 |
| `pcln.go` / `line.go` / `dwarf.go` | 行号表、DWARF 调试信息 | §5.2.1（位置信息） |

---

# 3. 差异提醒：书与 Go 不一致的地方

读代码时最容易困惑的几处，提前标注：

| 书里的技术 | Go 的实际情况 | 说明 |
|---|---|---|
| §2.4 RE → NFA → DFA → 最小化 | **完全不用** | Go 扫描器是手写状态机。想练手去 `src/regexp/syntax/` |
| §3.3.3 LL(1) 表驱动 / §3.4 LR(1) 表构造 | **完全不用** | Go 用手写递归下降；想对照可看 `goyacc` |
| §4.3 属性文法框架 | **完全不用** | Go 走 §4.4 的 ad hoc 路线，`types2/check.go` 是实例 |
| §8.4.2 树高平衡 | **没有** | |
| §8.5.2 循环展开 | **没有** | Go 明确不做循环展开 |
| §10.3.1 惰性代码移动 (LCM/PRE) | **没有完整实现** | 只有 `licm.go`（提升，§10.3.2） |
| §10.4.1 尾调用优化 | **不对用户代码做** | 仅用于编译器自生成的 ABI wrapper（`ssagen/abi.go:323`）。因 goroutine 栈需增长、需精确回溯 |
| §10.6.1 超块克隆 / §10.6.3 循环外提 | **没有** | |
| §12.4.2 踪迹调度 / §12.5 软件流水线 | **没有** | Go 只做基本块内表调度 |
| §13.4.4 / §13.4.5 图着色寄存器分配 | **没有** | Go 用**线性扫描**（`ssa/regalloc.go`）。冲突图只用在栈槽分配（`ssa/stackalloc.go`） |
| — | **Go 特有的**：Unified IR（`noder/`）、写屏障（`ssa/writebarrier.go`）、GC 安全点活性（`liveness/plive.go`）、逃逸分析（`escape/`）、PGO（`pgoir/`）、栈分裂检查 | 这些书里没有，但是 Go 编译器最有特色的部分 |

**两点方法论提醒**：
1. 书用 ILOC 抽象机教学，Go 用真实架构（amd64/arm64/…）。读 `_gen/AMD64.rules` 时把书里的 `loadAI`/`storeAI` 心象映射到 `MOVQ`/`LEAQ` 即可。
2. 书的 pass 是「一个算法一个 pass」，Go 的 pass 序列（`ssa/compile.go`）里同一个算法会跑多轮（如 `deadcode` 出现 6 次）。这是工程与教学的区别。

---

# 4. 学习路线

## 路线 A：按书顺序读（理论驱动）

| 步骤 | 书 | 源码 | 预计体量 |
|---|---|---|---|
| 1 | Ch01 | `cmd/compile/README.md` | 200 行 |
| 2 | Ch02 | `syntax/scanner.go` + `tokens.go` | ~1100 行 |
| 3 | Ch03 | `syntax/parser.go` | ~2500 行 |
| 4 | Ch04 | `src/go/types/`（**先读这个**，再回头读 `types2/`） | ~25000 行（可只精读 `expr.go`、`assignments.go`、`infer.go`） |
| 5 | Ch05 | `ir/node.go` → `ssa/block.go` + `value.go` → `obj/link.go` 的 `Prog` | ~3000 行 |
| 6 | Ch06 | `cmd/compile/abi-internal.md` + `abi/abiutils.go` | 文档为主 |
| 7 | Ch07 | **`walk/switch.go`** → `walk/order.go` → `walk/range.go` | ~2500 行 |
| 8 | Ch08 | `ssa/compile.go` 的 `passes` + `inline/inl.go` | ~1500 行 |
| 9 | Ch09 | **`ssa/dom.go`** → `ssagen/ssa.go` → `ssa/sccp.go` | ~4000 行 |
| 10 | Ch10 | `ssa/licm.go` → `ssa/cse.go` → `ssa/magic.go` → `ssa/deadcode.go` | ~2000 行 |
| 11 | Ch11 | `ssa/_gen/generic.rules` → `ssa/rewrite.go` → `ssa/lower.go` | 规则文件很大，挑主题读 |
| 12 | Ch12 | **`ssa/schedule.go`** | ~600 行 |
| 13 | Ch13 | **`ssa/regalloc.go`** + `ssa/stackalloc.go` | ~4000 行 |
| 附 A | — | `obj/link.go` 的 `Prog` | ~100 行 |
| 附 B | — | `ssa/sparseset.go` + `bitvec/bv.go` + `types2/scope.go` | ~600 行 |

## 路线 B：按「最短平路径」切入（推荐）

书里最适合与 Go 源码**逐段对照**的是 Ch07 与 Ch10 —— 因为对应关系最清晰、文件自包含。建议：

1. **`walk/switch.go`**（Ch07 §7.8.3）—— 起点：一个 pass 解决一个书里的问题，代码有完整策略注释
2. **`ssa/dom.go`**（Ch09 §9.2.1 / §9.5.2）—— 一个文件里两种教科书支配算法
3. **`ssa/schedule.go`**（Ch12 §12.3）—— 表调度的工业实现
4. **`ssa/regalloc.go`**（Ch13）—— 对照书里的图着色，看线性扫描如何替代
5. **`ssa/compile.go` 的 `passes`**（Ch08 §8.3 / Ch10 §10.7.3）—— 纵览全局后再回填其它 pass
6. **`ssa/escape/escape.go`** —— 书里没有但极有特色的分析

## 路线 C：用测试反推（验证理解）

每个 pass 都有对应的端到端测试，用 `-d=ssa/<pass>/debug=N` 把内部状态打出来，与书里的算法步骤逐条比对：

```sh
go test cmd/internal/testdir -run='Test/escape_slice.go'   # 逃逸分析（Ch09）
go test cmd/internal/testdir -run='Test/prove.go'          # 值域分析（Ch09 §9.2.4）
go test cmd/internal/testdir -run='Test/tighten.go'        # 值移近使用点（Ch10 §10.6.4）
go test cmd/internal/testdir -run='Test/codegen' -all_codegen -v  # 指令选择（Ch11）
```

详见 [`go_compiler_tests.md`](./go_compiler_tests.md)。

---

## 附：三个「一句话」记忆锚

- **Ch05 找 `ir` 和 `ssa`**：AST 到 SSA 到三地址码，Go 三代 IR 依次是 `syntax` → `ir`/`ssa` → `obj.Prog`。
- **Ch07 找 `walk`**：`walk` 包 = 书里整章「代码形态」，降糖 + 定序两件事。
- **Ch09/13 找 `dom.go` 和 `regalloc.go`**：数据流与寄存器分配是编译器后半程的两大支柱，Go 的实现都集中在 `ssa/`。
