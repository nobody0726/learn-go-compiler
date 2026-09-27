# Rust 重写 Go 1.27.1 编译器实施计划

> 每个里程碑交付合法 Go 源码到原生可执行程序的完整闭环。实施时逐任务先 RED 后 GREEN，并按 [`rust_go_compiler_architecture.md`](rust_go_compiler_architecture.md) 的边界复核。本文是待执行计划，不是完成记录。

**目标：** 用 Rust 实现与 Go 1.27.1 `cmd/compile` 等价的语言、诊断、ABI、对象、导出、优化与目标平台能力，并留下可复现的教学材料。**依据：** [`go_compiler_tests.md`](go_compiler_tests.md) 是测试导航，[`go_book_mapping.md`](go_book_mapping.md) 是理论导航；两者不是语言规范或额外的用户指令。

## 约束和边界

- `go_source_code/VERSION` 固定为 `go1.27.1`；`go_source_code/` 只读，不在其中构建或写测试。差分须使用匹配版本的可运行 Go 工具链；宿主其他版本只可作辅助观察。
- “1:1”按同一源码、选项、依赖和 GOOS/GOARCH 的程序行为、诊断、Go 内部 ABI、对象/export 互操作、调试和优化契约验收；不要求产物逐字节相同。每个未实现项要在覆盖清单留痕。
- 后端**手动用 Rust 实现**指令选择、寄存器分配、Go `ABIInternal`、栈帧/GC 活性、目标编码与 Go 对象输出。M0-M2 可以借宿主 `clang`/汇编器/链接器和极小 shim 跑通原生程序，但不能把宿主 C ABI、LLVM IR 或 shim 当成最终 Go 后端。
- 编译器工程放 `rust_go_compiler/`，教学页在 `rust_go_compiler/docs/teaching/`，设计和追加日志在根 `doc/`。不可改 Go 的生成文件；规则看 `ssa/_gen/*.rules`。
- Go 无 `fn`、`let`、`while`、普通安全指针算术、类和 ADT 模式匹配；Go 编译器不能编译 Rust 编译器。用户示例的语法、三阶段自举和“退出码 42”仅供纵向里程碑形式参考。

## 文件边界与每任务 TDD

初始 Cargo workspace：`crates/{source,syntax,types,typed-ir,lowering,ssa,codegen,targets,object,driver}`，跨包时加 `package` 和 `export-data`；`tests/{fixtures,diff,codegen,cli,runtime}` 对应输入、差分、汇编、命令行和运行。接口依赖按 `source → syntax → types → typed-ir → lowering → ssa → codegen → targets/object` 单向流动；`driver` 编排，诊断/统计横切。每个 M 的功能任务必须显式写出该链上的新增切片。

每张任务卡按同一协议执行：在 `tests/fixtures/mN/` 写最小合法 Go 成功例与失败例；运行匹配版 Go reference 并记录 stdout、stderr、退出码或诊断；先写 Rust unit/golden/E2E 测试并运行精确 `cargo test` 命令保存因缺功能而失败的 RED；做最小实现并重跑为 GREEN；回归 M0..M(N-1)，按 B0.2 清单解锁适用的官方测试。每个功能任务 `Mx.y` 同时派生 `Mx.y-T` 教学子任务：记录本任务原理与教材章节、Go `文件:行号` 与 Rust 符号、最小正反例、RED/GREEN 命令及输出、IR/汇编证据、性能数据、风险和设计取舍；追加 [`devlog/rust-go-compiler.md`](devlog/rust-go-compiler.md) 中独立条目，并在对应 `docs/teaching/mx-*.md` 页面添加可重放小节。`Mx.3`（M7 为 `M7.5`）只负责本门教学页整合与审稿，不代替逐功能子任务。没有真实 RED/GREEN 或锚点的教学子任务不能结项。任务卡的源码锚点均相对 `go_source_code/`，教学页展开成完整路径与行号。未实际执行的命令绝不写成已通过。

| 里程碑 | 语言/语义轴 | IR/后端轴 | ABI/runtime/包轴 | 测试/目标轴 | 性能/教学轴 |
|---|---|---|---|---|---|
| M0 最小闭环 | `main`、常量、`println` | token→AST→IR→手写极简汇编 | 隔离宿主 shim | 一种宿主架构；L1/L4 | 阶段耗时；流水线图 |
| M1 标量 | 变量、算术、比较、常量 | 类型化 IR、栈槽、折叠 | shim 仍隔离 | 表达式差分；L3 | 常量精度/指令数 |
| M2 CFG | `if`、`for`、短路、跳转 | 块/边/phi、分支指令 | 闭环持续可运行 | 循环程序；L1/L4 | 块数、支配关系 |
| M3 函数/ABI | 参数、多返回、递归 | 调用、帧、寄存器分配、对象 | Go `ABIInternal`、Go linker/runtime | `test/abi`、双向调用 | spill、帧大小 |
| M4 内存 | 数组/结构体/指针/切片 | 布局、寻址、nil/bounds | GC 栈图、安全点、屏障 | L1/L2/GC 运行 | 分配、检查数 |
| M5 动态语义 | 接口、闭包、map/chan、defer/go | 降糖、itab、逃逸 | runtime/GC/调度 | `interface`、`chan` | 动态调用/逃逸 |
| M6 泛型/包 | 约束、推断、跨包 | shape/dictionary、真实 export | importcfg、stdlib 互操作 | `typeparam`、多包 | 实例化/解码 |
| M7 全面能力 | 剩余规范特性与选项 | 优化、PGO、DWARF、多目标 | 标准库与工具链 | **T1 amd64/linux 必做、T2 arm64/linux 应做、T3 显式 out-of-scope**；L1-L5 | 编译/运行基准 |
| M8 验收 | 关闭覆盖缺口 | 全量差分/确定性 | 双向互操作 | 官方测试清单审计 | 教学总索引 |

横向检查还包括数据表示（span/AST/typed IR/SSA/machine IR/object）、包边界（单文件/单包/多包/标准库）、诊断、平台、性能、教学。每个任务按行交付完整可运行路径，按列补足对应能力；旧行始终回归。

## 开工前的两份零遗漏基线

当前计划**不能宣称已经枚举 Go 的所有功能或测试**。列举“剩余功能”会遮蔽遗漏。M0 的第一个交付是以下两份可再生清单，此后每个任务更新，M8 仅做最终审计。

**任务 B0.1 / 功能清单（三角模型）：** 单一 ground truth 撑不起“零遗漏”承诺。语言规范欠描述编译器实现的东西（PGO、写屏障、ABIInternal、PCLN、escape 诊断、`-d=ssa/...`），又过描述 runtime 行为（goroutine 调度、map/select 随机化、open-coded defer）。因此维护三套**独立、可机械再生**的真值，漏项只可能由两两差集暴露：

- **A 语言规范集** `coverage/spec_atoms.toml`：脚本 `tools/extract_spec_atoms` 解析 `go_source_code/doc/go_spec.html` 的每个 `<h2>/<h3>` + 锚点为带 ID 的 `spec_atom`（8997 行可机械切分；已核对 `:79/:799/:3104/:5950/:7407/:8002` 为六个 `<h2>` 章节锚点）。spec 是好锚点，但只是三集之一。
- **B 编译器实现集** `coverage/impl_atoms.toml`：脚本 `tools/extract_impl_atoms` 扫描源码树得原子清单 —— 每个 `//go:` pragma 字符串、`base/flag.go` 中 `ParseFlags` 注册的每个 flag、`cmd/compile/internal/` 每个包的每个导出符号、每个 `_gen/*.rules` 的每个 rule 头（**按 pass 分**：主/latelower/splitload/simd 是独立 feature，不是每 arch 一条；共 27 文件/20643 行）、每个 `cmd/internal/obj/<arch>` 文件。B 是 spec 不提的“实现独占契约”的唯一来源。
- **C 测试清单**（B0.2 产物）：可观察行为面。

**三角 diff 闭环**：每个 `feature_id` 必须在三集都有归属且有一条通过的 Rust 测试才算 `verified`。三集两两 diff，三个红色危险区即遗漏藏身处：A only（spec 有、impl/测没）= 规范死角，最隐蔽，绿灯全亮却漏语义；B only（impl 有、spec/测没）= 实现独占契约，必须靠 C 兜底；C only（测有、spec/impl ?）= runtime 行为，只能运行时差分。

`features.toml` 逐条记录 `feature_id`、A/B/C 三侧锚点、适用 GOOS/GOARCH、主任务、前端/中端/后端/运行时子能力、正反测试 ID、`relation=rewrite|reference|reuse`、`status=planned|partial|verified`。按语法/类型/运行语义、诊断、优化、对象/export、调试、编译选项、目标平台七类分别与官方基线做差集；优化质量与诊断文案另记可观察契约，不用语言规范覆盖率冒充编译器功能覆盖率。**关键纪律**：A/B 的“源侧”由脚本生成，人只填归属，绝不参与枚举——手抄锚点会漂移（已发现 B0.2 把 `dirs` 抄到 `testdir_test.go:73`，实际在 `:74`，`:73` 是 TODO 注释）。先写校验器 RED：缺主任务、缺负例、缺目标维度、A/B/C 任一侧无锚点、同 ID 重复必须失败；再生成初始清单。`B0.1-T` 教学子任务解释三角模型与一个 `feature_id` 从 spec/impl 到测试与里程碑的完整追踪；日志附三集差集与校验器 RED/GREEN。风险：规范外的 Go 扩展被漏掉（靠 B 集 `//go:` pragma 扫描兜底）；借鉴 rustc feature gate 跟踪。

**任务 B0.2 / 官方测试清单（C 集，与 B0.1 的 C 对应）：** 从 `src/cmd/internal/testdir/testdir_test.go:74` 的 `dirs`（`:72` 是注释、`:73` 是 TODO，别抄错）和 `:170` 的 `goFiles` 发现规则出发，只将列出目录的直属 `.go` 记为 L1 case；`test/codegen` 是其中的 L2 子集，另展开每条架构/正负 asmcheck 断言，不能重复计 case。遍历 `src/cmd/compile/internal/test/`、`src/cmd/compile/internal/**/*_test.go`、`src/cmd/compile/testdata/script/*.txt`，并将 `.dir`、`testdata`、`.out`、txtar 文件及 profile 记为依赖资产，不把资产当独立 case。另建“相邻工具链”库存：`src/cmd/asm/`、`src/cmd/internal/obj/`、`src/cmd/internal/goobj/`、`src/cmd/link/`、`src/internal/pkgbits/`、`src/internal/types/testdata/`、`src/cmd/go/testdata/script/`、runtime 与 reflect 的相关测试；逐项判定编译器契约、集成契约或范围外，范围外需给出边界理由，不得默默排除。保存 `VERSION`、源内容摘要、原路径、runner、测试/子测试/断言 ID、依赖、build tag、GOOS/GOARCH/实验选项、预期、唯一主任务、依赖任务、首次可执行里程碑、最终全量门和执行状态。静态解析不能确认的动态子测试标 `unresolved-discovery`，以后以匹配版本工具链的实际列举/运行日志校验；此状态阻止零遗漏声明。初始执行状态统一 `not-run`。先写完整性 RED：故意删一个测试、辅助资产、架构变体、脚本命令和白盒断言，审计均失败；GREEN：清单与只读源树发现集合双向差集为零。原始清单由工具生成，人工只补归属/原因，不维护易过时的手抄总数。性能看扫描时长；风险是 runner 条件、分片与动态子测试漏枚举；借鉴 Go testdir 和 testscript 的发现/条件规则。`B0.2-T` 教学子任务解释一条 L1、L2、L4、L5 用例如何被发现并复现；日志附枚举命令、源哈希与差集证据。

**功能归属表（初始分桶，最终以 B0.1 清单逐条为准）：**

| 能力族 | 首次闭环任务 | 必须扩展的子能力与 Go 锚点 | 主要原测试族 |
|---|---|---|---|
| 源文本/词法/位置 | M0.1 | Unicode、注释、字面量、分号、`//line`；`src/cmd/compile/internal/syntax/scanner.go:30` | `test/syntax`、syntax 包单测 |
| 常量/标量/表达式 | M1.1-M1.2 | 浮点、复数、rune、字符串、转换、有/无类型常量、运算溢出；`src/cmd/compile/internal/types2/check.go:230` | 顶层 `const*`/`float*`、types2、L3 arithmetic |
| 声明/控制流 | M2.1-M2.2、M5.2 | 声明与作用域、`switch`/type switch、`goto`/标签、`fallthrough`、`select`、所有 `range` 形式（含 range-over-func）；`src/cmd/compile/internal/rangefunc/rewrite.go:1` | `test/syntax`、`switch*`、`range*`、rangefunc 单测 |
| 函数/过程/ABI | M3.1-M3.2 | 闭包在 M5.1；可变参数、命名/多返回、递归、ABI wrappers、栈增长；`src/cmd/compile/abi-internal.md:14` | `test/abi`、`stack*`、ssagen/amd64 单测 |
| 类型/内存/内建 | M4.1-M4.2 | 数组、结构、指针、切片、字符串、`new`/`make`/`append`/`copy`、大小/对齐、nil/bounds、GC；`src/cmd/compile/internal/walk/walk.go:23` | `bounds*`、`slice*`、`writebarrier*`、liveness |
| 动态语义/runtime | M5.1-M5.2 | 接口/方法、反射、map/channel、`go`/`defer`/panic/recover、并发与逃逸；`src/cmd/compile/internal/walk/select.go:1` | `test/interface`、`test/chan`、`escape*` |
| 泛型/包/工具链集成 | M6.1-M6.2 | 类型集/推断、别名和方法集、import/init、Unified IR、`unsafe`、`//go:embed`/`//go:linkname` 与其他受支持指令；`src/cmd/compile/internal/noder/unified.go:156` | `test/typeparam`、import/linkname、L5 |
| 优化/调试/平台 | M7.1-M7.4 | SSA 各 pass、intrinsic/SIMD、PGO、race/coverage、DWARF/PCLN、各目标/驱动参数；`src/cmd/compile/internal/ssa/compile.go:30` | `test/codegen`、`test/dwarf`、L3/L4、L5 |
| 横切回归 | 发现时归最早满足依赖的任务，最迟 M7.3/M7.4 的具名子任务 | `test/fixedbugs`、`test/ken`、`test/stress`、`test/arenas` 与顶层未归类文件逐项分类；禁止用目录整体映射代替逐条 ID | 对应源文件及其平台变体 |

### 不遗漏的四道闸（速查）

> 完整定义见 B0.1（三角模型）与文末“零遗漏门槛”。本节是速查与目标切档。

1. **机械生成三集 ground truth**——spec/impl/test 三套清单的“源侧”由脚本再生，人只填归属。手抄锚点会漂移（实证：`dirs` 实在 `testdir_test.go:74`，曾被抄到 `:73` 的 TODO 注释）。
2. **三角 diff**——A(spec)∩B(impl)∩C(test) + 通过的 Rust 测试 = `verified`；三个红色危险区（规范死角 / 实现独占契约 / runtime 行为）各自需要兜底。
3. **变异注入差分**——故意改 reference 一个行为（翻转 loop var capture、改一条 escape 结果、关一个 bounds check），验证 harness 能抓到；抓不到注入 bug 的 harness 禁止用来声明覆盖。
4. **负测试差分**——reference 拒绝的代码 Rust 也必须拒绝；“不该编译的代码竟然编译过”是遗漏的典型表现，从 M0 起即跑，不等 M8。

四道闸全开才允许声明“零遗漏”；任一闸未开 = 仅“进度报告”，非“完成”。

**目标平台切档（防蔓延）：**

| 档 | GOARCH/GOOS | 要求 | 状态字段 |
|---|---|---|---|
| T1 必须 | amd64/linux | 端到端 + asmcheck + ABI 双向互操作全过 | `must` |
| T2 应做 | arm64/linux | 交叉编译 + 真机运行 | `should` |
| T3 范围外 | 386/arm/loong64/mips/mips64/ppc64/riscv64/s390x/wasm | 显式声明，不进 M7.2 任务卡 | `scope-excluded`（带理由） |

理由：单 `cmd/internal/obj/arm64`=35612 行、`obj/x86`=15992 行，全做不可完成且对学习项目零边际价值。`not-applicable` 仅用于原 runner 条件不适用的平台；本切档的 T3 用 `scope-excluded` 承载“主动不做”，二者不混。

同一功能可以在多个里程碑深化：表中“首次闭环”不是最终完成声明。若单条官方测试同时涉及若干功能，记录一个主任务与若干依赖任务；所有依赖 GREEN 后该条才可标 `pass`。

## 里程碑与官方源码的任务级对照

本节回答“这一门做的是官方编译器的哪一部分”。下表源码路径统一相对 `go_source_code/`；`文件:行号` 指向已核对的函数或数据定义。Rust 栏相对将来建立的 `rust_go_compiler/crates/`，目前只是责任归属，不能称为已存在的实现。完整的源码与原理导航仍使用 [`go_book_mapping.md`](go_book_mapping.md)，此处只增加实施任务归属，不另建平行源码地图。

关系为 **功能切片 ↔ 多个 Go 函数 ↔ 一个主任务及若干依赖任务**，不是“一个 Go 文件对应一个里程碑”。“重写”指等价能力由 Rust 实现，允许采用不同算法；“参考”指用于理解原理但本门没有实现完整契约；“复用”指继续调用官方工具链。一个大函数内部不同语法分支须在 B0.1 清单中进一步标出 `feature_id` 和分支条件。

### M0-M2：语义与可执行骨架

| 任务 / 功能切片 | 官方源码与关键符号 | Rust 责任 / 原理 | 本门边界与后续深化 |
|---|---|---|---|
| M0.1 最小源文件、token、函数 AST | `src/cmd/compile/internal/syntax/syntax.go:66` `Parse`；`syntax/scanner.go:88` `scanner.next`；`syntax/parser.go:406` `fileOrNil`、`:799` `funcDeclOrNil` | `source/syntax`；手写扫描状态机、递归下降、位置保存 | 重写最小 token/分号/函数切片；完整词法与语法按 M1-M7 扩充，不宣称整个 parser 完成。 |
| M0.1 最小语义到编译器 IR | `src/cmd/compile/internal/types2/call.go:171` `callExpr`；`noder/writer.go:1880` `writer.expr`；`noder/reader.go:2200` `reader.expr` | `types/typed-ir`；名称解析、类型化表示 | 重写常量和 `println` 调用的等价语义；Unified IR 序列化仅参考，正式格式到 M6.2。 |
| M0.2 `println`、最小发码与驱动 | `src/cmd/compile/internal/walk/builtin.go:626` `walkPrint`；`ssagen/ssa.go:294` `buildssa`、`:6980` `genssa`；`gc/main.go:65` `Main` | `lowering/codegen/targets/driver`；lowering 与目标输出 | 官方函数是行为/流程参考；本门由隔离 shim 实现 stderr 路径，尚未重写 Go runtime 调用与对象契约，M3 替换兼容边界。 |
| M1.1 表达式优先级、局部声明和赋值 | `src/cmd/compile/internal/syntax/parser.go:873` `binaryExpr`、`:893` `unaryExpr`；`types2/assignments.go:21` `assignment`、`:529` `shortVarDecl`；`types2/decl.go:311` `constDecl` | `syntax/types`；优先级爬升、作用域、常量与可赋值规则 | 重写整数/布尔、`var/const/:=` 切片；浮点/复数、完整转换等独立能力最迟 M7.3 关闭。 |
| M1.2 求值顺序、标量 SSA 与规则 | `src/cmd/compile/internal/walk/order.go:51` `order`；`ssagen/ssa.go:3024` `state.expr`；`ssa/compile.go:30` `Compile`；`ssa/_gen/AMD64.rules:1` | `typed-ir/lowering/ssa/codegen`；副作用排序、常量折叠、目标降低 | 重写标量路径与最小 pass；规则从 `.rules` 阅读，不抄生成的 rewrite 文件；全 pass/目标扩展到 M7.1/M7.2。 |
| M2.1 条件、循环、分支与 CFG | `src/cmd/compile/internal/syntax/parser.go:2338` `forStmt`、`:2466` `ifStmt`；`types2/stmt.go:410` `Checker.stmt`；`ssagen/ssa.go:1663` `state.stmt` | `syntax/types/typed-ir/ssa`；基本块、terminator、控制边与短路求值 | 重写 `if/for/break/continue` 切片；同一 `stmt` 的 switch/select/go/defer 分支分别到 M5/M7，不能按整函数结项。 |
| M2.2 phi、验证、支配与死块 | `src/cmd/compile/internal/ssagen/phi.go:42` `state.insertPhis`；`ssa/check.go:15` `checkFunc`；`ssa/dom.go:58` `dominators`；`ssa/deadcode.go:161` `deadcode` | `ssa/codegen/targets`；SSA 合并、支配、CFG 验证与分支发码 | Rust 可用块参数表达等价合并；基础 verifier/死块本门完成，完整优化条件到 M7.1。 |

### M3-M4：调用、对象与内存契约

| 任务 / 功能切片 | 官方源码与关键符号 | Rust 责任 / 原理 | 本门边界与后续深化 |
|---|---|---|---|
| M3.1 函数声明、参数、多返回与调用 | `src/cmd/compile/internal/types2/decl.go:675` `funcDecl`；`types2/call.go:472` `arguments`；`types2/assignments.go:384` `initVars`；`ssa/expand_calls.go:21` `expandCalls` | `types/typed-ir/ssa/codegen`；签名、调用图、参数/结果 lowering | 重写普通函数切片；闭包/接口调用到 M5，泛型调用到 M6；多返回在 `initVars` 的返回上下文核对。 |
| M3.2 Go ABI 参数与栈帧 | `src/cmd/compile/internal/abi/abiutils.go:397` `ABIConfig.ABIAnalyze`；`ssagen/abi.go:1`；`ssa/regalloc.go:148` `regalloc`；`ssa/stackalloc.go:93` `stackalloc` | `targets/ssa`；ABIInternal、寄存器/栈落位、spill、帧布局 | 本门重写首目标必要 ABI 与基础分配器；完整寄存器分配策略/其他目标在 M7.2，不套用宿主 C ABI。 |
| M3.2 Go 对象与机器码 | `src/cmd/compile/internal/ssagen/pgen.go:303` `Compile`；`gc/obj.go:44` `dumpobj`、`:133` `dumpLinkerObj`；`src/cmd/internal/obj/objfile.go:1`、`goobj/objfile.go:1`；`obj/x86/asm6.go:1` | `object/targets`；符号、重定位、机器编码、对象序列化 | 编译器使用的 obj/goobj/首目标编码能力也须由 Rust 重写，即使官方代码在 `cmd/compile` 目录外；Go linker/runtime 仍复用。 |
| M3.2 基础 GC 元数据 | `src/cmd/compile/internal/liveness/plive.go:1395` `Compute`、`:1330` `Liveness.emit` | `object/codegen`；安全点、参数与局部指针位图 | 必须满足 M3 双向调用的安全要求；聚合、分配与屏障组合在 M4.2 扩充，不能把 GC 元数据全部延期。 |
| M4.1 大小、对齐、字段与寻址 | `src/cmd/compile/internal/types/size.go:211` `CalcSize`；`types2/lookup.go:85` `LookupFieldOrMethod`；`ssagen/ssa.go:3024` `state.expr` | `types/typed-ir/ssa`；目标尺寸、地址和值、索引/字段 lowering | 重写数组/结构体/切片/字符串/指针相关分支和检查；同一个 lookup 的接口方法能力仍属 M5.1。 |
| M4.2 分配、append/copy 与逃逸 | `src/cmd/compile/internal/walk/builtin.go:603` `walkNew`、`:425` `walkMakeSlice`、`:44` `walkAppend`、`:170` `walkCopy`；`escape/solve.go:19` `batch.walkAll` | `lowering/middle-end`；runtime 调用、逃逸约束传播 | 重写本门所需分配与逃逸安全语义；更精细逃逸结果/诊断与成本到 M7.1。runtime 分配器本身复用。 |
| M4.2 屏障与 GC 活性 | `src/cmd/compile/internal/ssa/writebarrier.go:164` `writebarrier`；`liveness/plive.go:689` `Liveness.solve`、`:1395` `Compute` | `ssa/codegen/object`；指针存活的数据流、写屏障插入、栈图输出 | 重写编译器侧插入与元数据；runtime GC/栈增长继续复用，以强制 GC 与跨栈增长测试验证契约。 |

### M5-M6：动态构造、泛型与包

| 任务 / 功能切片 | 官方源码与关键符号 | Rust 责任 / 原理 | 本门边界与后续深化 |
|---|---|---|---|
| M5.1 方法集、接口转换与类型元数据 | `src/cmd/compile/internal/types2/lookup.go:365` `MissingMethod`；`types2/instantiate.go:240` `Checker.implements`；`walk/convert.go:40` `walkConvInterface`；`reflectdata/reflect.go:995` `WriteRuntimeTypes` | `types/lowering/object`；方法集、类型身份、itab/反射描述与动态调用 | 重写普通接口及反射元数据切片；`implements` 的类型集约束还会在 M6.1 使用。runtime/reflect 的消费端复用。 |
| M5.1 闭包与捕获 | `src/cmd/compile/internal/noder/writer.go:2608` `funcLit`；`walk/closure.go:94` `walkClosure`；`escape/expr.go:15` `escape.expr` | `typed-ir/lowering/middle-end`；捕获环境、间接调用、逃逸 | 重写环境表示及调用 lowering；闭包捕获和逃逸一起验收，不能只实现 parser。 |
| M5.2 range/map/chan/select | `src/cmd/compile/internal/walk/range.go:41` `walkRange`；`walk/select.go:15` `walkSelect`；`walk/builtin.go:315` `walkMakeMap`、`:296` `walkMakeChan`；`rangefunc/rewrite.go:603` `Rewrite` | `lowering/ssa`；迭代降糖、runtime 操作、函数迭代器改写 | 逐种 range 类型创建子任务；range-over-func 另依赖闭包和类型检查。map/channel/scheduler 实现仍复用 runtime。 |
| M5.2 go/defer/panic/recover | `src/cmd/compile/internal/types2/stmt.go:166` `suspendedCall`；`ssagen/ssa.go:1663` `state.stmt`；`walk/builtin.go:771` `walkRecover` | `types/lowering/ssa/codegen`；延迟调用、panic/recover 与 runtime 交互 | 核对 state.stmt 内对应 opcode 分支；重写编译器侧降糖、开放编码 defer 等所需路径，runtime 行为通过组合运行测试验收。 |
| M6.1 类型推断、约束与实例化 | `src/cmd/compile/internal/types2/infer.go:32` `Checker.infer`；`types2/instantiate.go:51` `Instantiate`、`:216` `Checker.verify`；`types2/call.go:131` `instantiateSignature` | `types/typed-ir`；统一/约束求解、实例化缓存、类型集 | 重写泛型语义；不把纯 C++ 式模板单态化视为 Go 泛型后端。 |
| M6.1 shape/dictionary 与泛型体 | `src/cmd/compile/internal/noder/unified.go:192` `unified`、`:242` `readBodies`；`noder/reader.go:1`、`noder/writer.go:1` | `typed-ir/export-data/ssa`；泛型体重建、shape 共享与字典参数 | reader/writer 是跨功能大文件，B0.1 需逐类型参数/字典读写点继续细分；本行不代表整文件完成。 |
| M6.2 import/export 与包初始化 | `src/cmd/compile/internal/noder/import.go:173` `readImportFile`；`noder/export.go:16` `WriteExports`；`noder/unified.go:469` `writeUnifiedExport`；`pkginit/init.go:26` `MakeTask`；`src/internal/pkgbits/decoder.go:71` `NewPkgDecoder`、`encoder.go:1` | `package/export-data/object/driver`；依赖与 init 顺序、Unified IR 格式、版本/摘要校验 | 重写包读写和编译器侧初始化任务；Go 构建驱动与 linker 的包排序/装载继续复用，靠双向导入测试证明兼容。 |

### M7-M8：覆盖关闭与验收

| 任务 / 功能切片 | 官方源码与关键符号 | Rust 责任 / 原理 | 本门边界与后续深化 |
|---|---|---|---|
| M7.1 inline/devirtualize/escape/PGO | `src/cmd/compile/internal/inline/inl.go:1`；`inline/inlheur/funcprops_test.go:1`；`devirtualize/devirtualize.go:25` `StaticCall`；`escape/solve.go:19` `walkAll`；`pgoir/irgraph.go:122` `New` | `middle-end`；调用图、成本模型、数据流、热度引导 | 在 M4/M5 安全语义上补完整优化及诊断；每个成本/启发式规则另有 feature ID 与测试。 |
| M7.1 SSA 优化全集 | `src/cmd/compile/internal/ssa/compile.go:457` `passes`；`ssa/_gen/generic.rules:1`；`ssagen/intrinsics.go:1` | `ssa/codegen`；DCE/CSE/prove/BCE、intrinsic、pass 次序与开关 | 从 passes、规则与 intrinsic 注册表逐条拆任务；不是只实现几个教材算法就关闭官方优化全集。 |
| M7.2 目标、调度、分配与调试 | `src/cmd/compile/internal/ssa/config.go:1`；`ssa/regalloc.go:148`；`ssagen/ssa.go:6980` `genssa`；`dwarfgen/dwarf.go:1`；各目标 `ssa/_gen/*.rules` 和 `src/cmd/internal/obj/<arch>/` | `targets/ssa/object`；目标降低、调度、寄存器分配、指令编码、DWARF | 按 T1/T2/T3 切档执行（见“不遗漏的四道闸”与 B0.1 目标集）；T3 架构（386/arm/loong64/mips/mips64/ppc64/riscv64/s390x/wasm）标 `scope-excluded` 不进本门。`_gen/*.rules` 按 pass 分（主/latelower/splitload/simd 独立 feature，共 27 文件/20643 行），不是每 arch 一条；PCLN 相关 linker/runtime 消费端仅作集成依赖。 |
| M7.3 语义剩余项 | `src/cmd/compile/internal/syntax/parser.go:2492` `switchStmt`；`walk/switch.go:32` `walkSwitch`；`walk/builtin.go:776` `walkUnsafeData`；B0.1 每项对应的 types2/noder/walk 分支 | `syntax/types/typed-ir/lowering`；规范未闭合项逐条实现 | 本行仅是清单关闭入口；每个尚未覆盖的具体能力必须新建具名子任务，并填写具体函数/分支，不能用整目录作锚点。 |
| M7.4 flags/插桩/指令/集成模式 | `src/cmd/compile/internal/base/flag.go:158` `ParseFlags`；`coverage/cover.go:41` `Fixup`；`staticdata/embed.go:1`；`gc/main.go:65` `Main`；`src/cmd/compile/script_test.go:44` `TestScript` | `driver/lowering/object/targets`；模式编排、插桩、指令与 CLI 契约 | 按 flags、pragma、插桩路径与脚本逐条拆任务；cgo/Go assembler/linker 本身不重写，编译生成的 Go 与互操作须验收。 |
| M8.1 官方测试与归属审计 | `src/cmd/internal/testdir/testdir_test.go:74` `dirs`、`:170` `goFiles`；`src/cmd/compile/script_test.go:44` `TestScript`；所有原测试的逐条 ID | `coverage/tests`；runner 语义复现、清单差集、平台与白盒映射审计 | 对应官方测试驱动，不对应一个新编译算法；必须检查所有适用项的 Rust 执行证据。 |
| M8.2 确定性、M8.3 教学复现 | 上述对象/export/pass 输出入口与所有教学页引用的源码；理论映射见 `doc/go_book_mapping.md` | `driver/object/export-data/docs`；稳定输出、复现实验 | 是横切验证和教学任务，不虚构对应的 Go “教学模块”；逐功能 `-T` 子任务继承其父任务源码锚点。 |

### 反向查询与完成记录

| 从 Go 源码出发 | 首次切片 → 后续深化任务 |
|---|---|
| `syntax` / `types2` | M0.1 → M1.1/M2.1/M3.1/M4.1/M5.1/M6.1/M7.3；一个包横跨所有语言切片。 |
| `ir` / `types` / `noder` | M0/M1 建等价内部表示 → M4 布局、M5 动态表示 → M6 真实 Unified IR/export → M7 关闭剩余分支。 |
| `walk` / `rangefunc` | M0.2 println → M1.2 order → M4.2 分配 → M5.1/M5.2 动态构造 → M7.3 剩余语义。 |
| `ssagen` / `ssa` | M0.2 最小发码 → M1 标量 → M2 CFG/phi → M3 调用 → M4 屏障 → M7.1 优化与 M7.2 全目标。 |
| `abi` / `liveness` / `objw` / `gc/obj` / `cmd/internal/obj` / `goobj` | M3.2 真实 ABI/对象与基础安全点 → M4.2 完整内存切片 → M7.2 多目标/调试。 |
| `reflectdata` / `escape` / `inline` / `devirtualize` / `pgoir` | M4.2 逃逸安全 → M5 接口/闭包 → M7.1 全优化与性能契约。 |
| `pkginit` / `internal/pkgbits` | M6.2 包/格式互操作 → M7 跨标准库与模式回归。 |
| `base` / `gc/main` / `coverage` / 测试驱动 | M0 最小 driver → M7.4 完整选项/模式 → M8 全量审计。 |

**里程碑结项必须提交一份能力对照快照。** B0.1 每项追加 `go_path`、`go_symbol`、`go_branch_or_rule`、`relation = rewrite|reference|reuse`、`introduced_task`、`completion_task`、`rust_symbol`、`test_ids` 和 `evidence`。状态区分 `planned/partial/verified`；本门只覆盖的子分支标 `partial`，只有其列出的契约与测试通过才标 `verified`，不得仅凭“读过该文件”结项。源码文件哈希锁定在当前 Go 基线，行号漂移时重新解析符号并核对。Go 同一符号允许关联多个 feature ID，但每个 feature ID 必须有唯一主任务和最终完成门。

例如 `shortVarDecl` 的整数短声明属于 M1.1，而泛型返回值推断关联 M6.1；二者共用官方代码也要独立列项。Rust 符号在实现前保持 `planned`，实现后在对应 `-T` 教学子任务中填写真实位置，完成页同时展示“本门新增、以前继承、仍待后续”的能力列表。

## M0：从合法 Go 程序到原生可执行文件

**闭环：** `package main; func main() { println(42) }`。`println` 输出到 stderr，见 `src/builtin/builtin.go:308`；验收 `stdout = ""`、`stderr = "42\n"`、退出码 0；另测空 `main` 和非法 token。不能用 `func main() int { return 42 }`。

**M0.1 输入与语义切片：** `source/syntax/types/typed-ir` 只识别上述 token、分号插入、函数声明/调用、整数常量和源位置。Go 源码 `src/cmd/compile/internal/syntax/syntax.go:66`、`syntax/scanner.go:30`、`syntax/parser.go:430`、`types2/check.go:230`；原理为有限自动机、递归下降和基本符号表（教材 Ch02-Ch04）。RED 为 token/AST/错误位置 golden；GREEN 为结构化 IR 与稳定错误输出。性能看扫描字节/秒；风险是换行分号插入；借鉴 Go syntax 的 token 位置保留。

**M0.2 发码切片：** `lowering/codegen/targets/driver` 手写最少目标汇编，由明确标记的 C/汇编 shim 提供进程入口和 stderr 写入，再由宿主工具链接。Go 源码 `src/cmd/compile/internal/ssagen/ssa.go:294`、`ssagen/pgen.go:303`；原理是 lowering、调用边界、机器指令（Ch05/Ch11）。RED 为编译-链接-运行失败；GREEN 为三路差分。性能看端到端时间/产物大小；风险是宿主 ABI 被误称 Go ABI；借鉴 Cranelift 的可 dump/可验证中间表示。本门只证明隔离闭环，Go linker 互操作仍未通过。

**M0.3 教学与日志：** 建 `rust_go_compiler/docs/teaching/m0-walking-skeleton.md`，画输入/token/AST/IR/汇编/可执行路径，逐段解释最小 Rust 类型和 shim 限制；日志各记 M0.1、M0.2 的真实 RED/GREEN 命令、stderr 差分与耗时。门禁：教学页链接的 fixture、dump 和源码锚点都可打开，不能把 shim 称为 Go ABI。

## M1：标量、表达式和局部作用域

**闭环：** `package main; func main() { x := 10; println((x+3)*2) }`；扩充 `var`、`const`、布尔、整数宽度、有/无类型常量、算术/位运算、比较。Go 没有 `let` 和普遍的隐式数值提升。

**M1.1 表达式/类型：** `syntax/types` 用 precedence climbing 处理优先级、作用域、常量精度和转换；对照 `syntax/parser.go:430`、`types2/check.go:230`（Ch03/Ch04）。RED：结合性、溢出、遮蔽和非法转换；GREEN：type/diagnostic golden 与 reference。性能：长表达式解析耗时；风险：任意精度常量过早截断；借鉴 Go 的 untyped constant 规则。

**M1.2 标量发码：** `typed-ir/lowering/codegen` 加栈槽、求值顺序、算术和可关闭的常量折叠；对照 `src/cmd/compile/internal/ssa/compile.go:30`、`ssa/_gen/AMD64.rules:1`（Ch05/Ch10/Ch11）。RED：边界整数、除零、带副作用表达式；GREEN：运行差分且优化开/关语义一致。性能：指令数/运行时间；风险：宿主 C 的溢出和除零语义并非 Go 语义；借鉴 Go 声明式 rewrite 规则。

**M1.3 教学与日志：** `docs/teaching/m1-expressions-types.md` 解释 Go untyped constants、优先级、作用域和标量发码，包含一例故意溢出的 RED 与 IR/汇编前后对照；日志分别记录 M1.1、M1.2 的测试和折叠前后指标。门禁：示例可重放、代码符号和 Go 参考行号可定位。

## M2：控制流和 CFG

**闭环：** 用 Go 的 `for` 写欧几里得算法、有限规模质数筛；覆盖 `if/else`、`for`、`break/continue`、`&&/||` 短路。Go 无 `while`。

**M2.1 CFG：** `syntax/types/typed-ir/ssa` 引入 terminator、前驱/后继、作用域与 CFG verifier；对照 `src/cmd/compile/internal/walk/walk.go:23`、`ssagen/ssa.go:294`（Ch05/Ch07/Ch09）。RED：短路副作用、非法跳转、坏 CFG；GREEN：CFG golden 和两个运行程序差分。性能：块/边数；风险：不可达代码不能擅自发出 reference 不会发的错误；借鉴 Go SSA Block/Value。

**M2.2 分支机器路径：** `ssa/codegen/targets` 加 phi/块参数、支配检查、分支指令与死块清理；对照 `src/cmd/compile/internal/ssa/compile.go:30`、`ssa/dom.go:1`（Ch08/Ch09）。RED：破坏 phi/predecessor 的 verifier 反例；GREEN：关优化也可运行。性能：phi/分支数；风险：CFG 改写后的边缓存失效；借鉴 Cranelift verifier 和逐 pass dump。

**M2.3 教学与日志：** `docs/teaching/m2-control-flow-ssa.md` 用欧几里得程序画 CFG、支配关系和 phi，附短路副作用反例及 pass 前后 dump；日志分别记录 M2.1、M2.2 的 RED/GREEN 与块/边/phi 数据。门禁：图中每条边可对到实际 dump，运行结果可复现。

## M3：函数、Go ABI 与 Go 对象

**闭环：** 多参数/多结果、直接/间接调用、适度递归；Rust 编译包调用 reference 编译包，反方向也成立。递归深度按平台和栈增长能力验收，不能要求深度十万的 Fibonacci/Ackermann 必不溢出。

**M3.1 过程语义：** `types/typed-ir/ssa/codegen` 加全局符号、参数、结果、调用图和返回；对照 `src/cmd/compile/internal/types2/check.go:230`、`ssagen/ssa.go:294`（Ch06）。RED：参数个数、多返回/递归反例；GREEN：同包运行差分。性能：调用开销；风险：求值和多返回落位；借鉴 Go ABI 参数分配实验。

**M3.2 兼容边界：** `targets/object` 实现 Go `ABIInternal` 寄存器/栈、帧、GC 栈图/安全点、重定位和真实 Go 对象；交给 Go linker/runtime。对照 `src/cmd/compile/abi-internal.md:14`、`:109`、`src/cmd/compile/internal/ssagen/abi.go:1`、`objw/objw.go:1`（Ch06/Ch11-Ch13）。RED：跨寄存器/栈参数、GC 与双向链接；GREEN：`test/abi` 适用子集和双向调用。性能：spill/帧/对象大小；风险：`ABIInternal` 不是 SysV/AAPCS，Go 内部调用也不能套用 C 的 callee-save 假设；借鉴 Go ABI 规范与对象 writer。若互操作未通，M3 保持未通过。

**M3.3 教学与日志：** `docs/teaching/m3-go-abi-object.md` 逐项展示参数/结果落位、调用图、Go 对象中的符号/重定位和跨编译器链接命令；日志分别记录 M3.1、M3.2 的失败与通过证据、spill/帧大小。门禁：至少一条双向调用的可复现实验，明确 Go ABI 与宿主 shim 边界。

## M4：聚合、内存与 GC

**闭环：** 数组、结构体、切片、字符串与指针组成链表式数据和矩阵计算；比较值、nil/bounds panic 以及 `unsafe.Sizeof/Alignof/Offsetof`。普通 Go 不支持指针算术。

**M4.1 布局/寻址：** `types/typed-ir/ssa` 算对齐、偏移、填充，区分地址和值；对照 `src/cmd/compile/internal/types2/check.go:230`、`ssagen/ssa.go:294`（Ch04/Ch05/Ch07）。RED：布局、二维索引和越界；GREEN：运行/诊断差分。性能：bounds check 数；风险：目标相关宽度；借鉴 Go 目标尺寸模型。

**M4.2 分配/GC：** `lowering/codegen/object` 加 runtime 分配、写屏障、活性与安全点；对照 `src/cmd/compile/internal/escape/solve.go:19`、`liveness/plive.go:1`（Ch06/Ch09）。RED：强制 GC 后对象存活、指针跨栈增长、屏障；GREEN：runtime 差分和对应 `test/abi`/writebarrier。性能：分配量/屏障数；风险：ASan 不能证明 Go GC 正确；借鉴 Go liveness 测试。

**M4.3 教学与日志：** `docs/teaching/m4-layout-gc.md` 逐字段算偏移/填充，展示 nil/bounds、栈图、安全点、写屏障的 Rust 代码及反例；日志分别记录 M4.1、M4.2 的 RED/GREEN 和分配数据。门禁：布局表与机器对象一致，GC 实验在文档命令下重放。

## M5：Go 特有的动态语义

**闭环：** 方法、接口/type switch、闭包捕获、`defer/panic/recover`、map、channel、goroutine 的独立与组合程序。目标不是类、ADT 或模式匹配。

**M5.1 接口/闭包：** `types/typed-ir/lowering/object` 实现方法集、itab/反射元数据、捕获环境和间接调用；对照 `src/cmd/compile/internal/types2/check.go:230`、`reflectdata/reflect.go:1`（Ch04/Ch06）。RED：typed nil、断言失败、捕获逃逸；GREEN：`test/interface` 差分。性能：动态调用/分配；风险：类型身份和布局；借鉴 Go reflectdata 路径。

**M5.2 runtime 降糖：** `lowering/ssa/codegen` 加 `range`、map/chan、`select`、`go`、`defer/panic/recover` 和逃逸；对照 `src/cmd/compile/internal/walk/range.go:1`、`walk/select.go:1`、`escape/solve.go:19`（Ch05/Ch07/Ch09）。RED：求值次序、关闭 channel、panic 与并发反例；GREEN：`test/chan` 和适用 `fixedbugs`。性能：goroutine 启动/逃逸率；风险：runtime ABI、GC、调度耦合；借鉴 Go walk 逐构造降糖。

**M5.3 教学与日志：** `docs/teaching/m5-dynamic-runtime.md` 对照接口表示、闭包环境、`select` 与 defer 降糖前后 IR，解释逃逸和 runtime 调用；日志分别记录 M5.1、M5.2 的 RED/GREEN、分配/调用数据。门禁：每种动态构造有最小可运行例和一个失败案例。

## M6：泛型与跨包互操作

**闭环：** 泛型函数/类型/约束/推断，多包调用与初始化；两种编译器互相导入、链接、运行；加入带 `fmt` 的标准库程序。

**M6.1 泛型语义：** `syntax/types/typed-ir/ssa` 实现类型集、推断、实例化及 Go 的 shape/dictionary 机制；对照 `src/cmd/compile/internal/types2/infer.go:1`、`instantiate.go:1`、`noder/unified.go:156`（Ch04/Ch05 加教材外 Go 泛型）。RED：嵌套泛型/错误约束；GREEN：`test/typeparam` 单包差分。性能：实例化数/缓存命中；风险：以纯单态化或自创 mangling 假装兼容；借鉴 Go Unified IR 泛型体。

**M6.2 包/export：** `package/export-data/object/driver` 实现 importcfg、依赖图、init 顺序以及匹配 Go 1.27.1 的 Unified IR/export 格式；对照 `src/cmd/compile/internal/noder/import.go:125`、`noder/export.go:16`、`pkginit/init.go:1`。RED：坏版本/截断、多包泛型、循环导入；GREEN：`typeparam/*imp.dir` 适用子集与双向混合编译。性能：export 字节/解码时间；风险：私有 magic/version 格式只可做实验 round-trip，**不能**证明与 Go `.a` 互操作；借鉴 Go reader/writer 的真实格式。

**M6.3 教学与日志：** `docs/teaching/m6-generics-export.md` 展示约束/推断、shape/dictionary、包图、真实 Unified IR 导入导出和 init 顺序；日志分别记录 M6.1、M6.2 的 RED/GREEN、实例化缓存和 export 大小。门禁：文档的双向混合编译可重放，私有格式实验明确标注为不兼容。

## M7：覆盖面、优化、多目标和标准库

**闭环：** 无修改的 Go Hello World、HTTP 客户端及官方跨阶段用例。逐项补完剩余规范特性、`unsafe`、指令、选项、coverage/race/PGO、调试和所有适用 GOOS/GOARCH；交叉编译成功不等于运行通过。

**M7.1 中端优化：** `middle-end/lowering/ssa` 加 inline、devirtualize、escape、DCE/CSE/prove/BCE、PGO；对照 `src/cmd/compile/internal/inline/inl.go:163`、`escape/solve.go:19`、`ssa/compile.go:30`（Ch08-Ch10）。RED：每 pass 最小反例与开关对照；GREEN：运行差分、`-m` 和适用 asmcheck。性能：每 pass 耗时/代码大小/运行时间；风险：静默误编译；借鉴 Go rules 和 LLVM FileCheck。

**M7.2 目标/调试/CLI：** `targets/object/driver` 逐目标加规则、寄存器分配、ABI、重定位、DWARF/PCLN、`-S/-m/-d/-importcfg`；对照 `src/cmd/compile/internal/ssa/regalloc.go:148`、`ssagen/pgen.go:303`、`dwarfgen/dwarf.go:1`（Ch11-Ch13）。RED：各目标 asmcheck/ABI/链接/运行与 CLI 错误路径；GREEN：独立 capability 报告。性能：spill/峰值 RSS/产物大小；风险：无执行环境的目标不能报 runtime pass；借鉴 Go codegen 架构注释与 rustc-perf。

**M7.3 规范剩余项逐条关闭：** `syntax/types/typed-ir/lowering` 以 B0.1 的未通过 `feature_id` 为输入，按正/负测试、运行差分和源码锚点逐条拆为任务；优先检查 M0-M6 未闭合的浮点/复数、全部 switch/标签/range、所有内建、别名/方法集、`unsafe` 和受支持的指令。对照 `go_source_code/doc/go_spec.html:3104`、`:5950`、`src/cmd/compile/internal/rangefunc/rewrite.go:1`。RED：每个 ID 的最小失败例；GREEN：该 ID 的前后端和适用官方用例同时过门。性能：每项记录编译成本；风险：用一个 M7 pass 掩盖不同功能缺口；借鉴规范目录逐节验收。

**M7.4 工具链模式逐项关闭：** `driver/object/targets` 以 B0.1 的编译器选项/平台 ID 为输入，分别验收 `//go:` 指令、coverage、race/sanitizer、PGO、DWARF/PCLN、链接模式和 cgo 生成源码的编译边界；与 `src/cmd/compile/testdata/script/` 的原脚本逐条关联。RED：选项/平台不兼容脚本；GREEN：匹配 GOOS/GOARCH 的 compile/link/run 或明确的编译专用证据。性能：各模式额外编译/运行开销；风险：assembler/linker/runtime 的责任不能误算为 compiler 实现；借鉴 Go 官方 CLI 测试指令。

**M7.5 教学与日志：** `docs/teaching/m7-optimization-targets.md` 逐 pass/目标列规则、dump、asmcheck 和基准前后数据；另建 `docs/teaching/m7-language-modes.md` 记录 M7.3/M7.4 每个能力 ID 的 Rust 代码、Go 对照和实验。日志分别记录 M7.1-M7.4 的 RED/GREEN；门禁：清单中无只有“其他功能”描述的条目，平台未运行项明确标注。

## M8：全量验收与教学交付

**闭环：** 官方适用测试的最后一条也可走 Rust compile → Go link → run/诊断/asmcheck。Rust 项目无法由 Go 编译器自举；逐字节一致也不能证明语义正确。

**M8.1 覆盖审计：** `coverage/official-tests.toml` 的每条 case、断言、白盒移植映射和适用平台均有 `pass|fail|blocked|not-applicable|not-run|scope-excluded`、参考版本、命令、日志摘要和负责人。RED：缺行、未知 testdir 指令、遗漏动态子测试、测试 ID 无任务或把 `blocked` 计为通过均使审计失败；GREEN：A/B/C 三集三角 diff 全绿（无 A only/B only/C only 红区未兜底）、四道闸全开、全部适用平台的记录为 `pass`、白盒映射逐条有 Rust 侧失败/通过证据、相邻工具链边界已裁定。`not-applicable` 仅用于 Go 原 runner 条件明确不适用的平台或经审计确属编译器边界外的测试，保留理由；`scope-excluded` 用于主动不做的 T3 架构（见“不遗漏的四道闸”切档表），与 `not-applicable` 不混；`blocked`/`not-run` 允许进度报告但不允许“1:1 已完成”。性能：全套运行时间；风险：harness 错解指令；借鉴 `src/cmd/internal/testdir/testdir_test.go:74`。

**M8.2 确定性/教学：** 固定环境重复构建，对比规范化 IR、export/符号摘要和适用产物；修复差异但不以 bit-for-bit 作为正确性证明。教学总索引只链接已存在的页面，每页解释 Rust 代码、Go 源码 `文件:行号`、教材章节、最小实验、RED/GREEN、性能与风险；借鉴 Go reproducible builds 测试与 rustc-dev-guide。

**M8.3 教学审稿与复现实验：** `docs/teaching/README.md` 按 [`go_book_mapping.md`](go_book_mapping.md) 的章节顺序索引 M0-M7 页面，逐页复跑命令并校验代码符号、Go 锚点、图/dump 和日志证据。日志记录最终全量覆盖差集、环境、确定性数据和未解决风险；门禁：不存在断链、空白章节或无实际测试证据的“已完成”教学页。

## 测试覆盖与交付证据

| 层 | 官方输入如何复用 | 首次解锁与最终执行门 |
|---|---|---|
| L1 `test/` | 原 `.go`、预期注释和 `.dir` 资产保持原样；Rust harness 实现 `run`、`compile`、`errorcheck`、`build`、`link` 等 testdir action，替换被测 compiler，依原规则保留预期失败、跳过、分片和条件。不能只执行官方 `go test` 后记为 Rust 通过。 | M0.1/M0.2 起解锁最小用例；M1-M7 随能力归属解锁；M8.1 全量逐 case 重跑。 |
| L2 `test/codegen/` | 属于 L1 子集；直接复用 Go 源和 asmcheck 注释，Rust 产出目标汇编，按架构逐条核对正/负断言；不把只在宿主平台运行的结果当全目标通过。 | M3.2 先验 ABI/对象，M4.1/M7.1 优化断言，M7.2 所有目标，M8.1 全矩阵。 |
| L3 `src/cmd/compile/internal/test/` | 将可独立编译的 Go 程序/数据作为黑盒原样复用；调用原 `cmd/compile` 内部 API 或依赖其测试框架的断言，逐条移植意图为 Rust unit/golden，记录 `go_test_id -> rust_test_id` 与等价判据。原 Go 白盒运行只能作参考。 | M1.1/M1.2 起按表达式和 codegen 解锁，M3-M7 补齐，M8.1 审计映射。 |
| L4 `src/cmd/compile/internal/**/*_test.go` | 按测试函数/子测试清点，能变为输入 fixture 的部分直接复用；白盒测试逐条移植断言，包括 `inline/inlheur`；`testdata` 作为依赖单列。 | M0.1 syntax，M1.1 types2，M2.1 SSA，M3.2 ABI/object，M4.2 liveness，M5.2 rangefunc，M6.1 noder，M7.1 inline/escape，M7.2 后端，M8.1 全量。 |
| L5 `src/cmd/compile/testdata/script/` | 原 `.txt` 及 txtar 文件直接复用；适配 `src/cmd/compile/script_test.go:47` 的脚本命令、条件、环境和输出断言，使被测路径调用 Rust compiler。 | M0.2 驱动雏形，M3.2 对象，M6.2 导入，M7.4 全部 CLI 模式，M8.1 九份脚本全量。 |
| 相邻工具链 | 对 obj/goobj/asm/link/pkgbits、`cmd/go/testdata/script`、`internal/types/testdata`、runtime/reflect 建关联库存。可通过替换 compiler 测得的集成测试直接运行；纯工具自身单测标边界外并说明。 | M3.2 链接与对象，M4.2 runtime，M6.2 包格式，M7.4 驱动与标准库，M8.1 逐项审计。 |

**逐项归属算法（B0.2 验收的一部分）：** 每个测试 ID 先指向唯一最早具备全部依赖的主任务；同时列出所有先决 `feature_id` 与任务。`fixedbugs`、顶层文件、平台专用 case 以及多功能 case 均按 ID 处理，不能以目录整体映射代替。若现有任务无法接收某个 ID，就在 M7.3/M7.4 下创建具名子任务，并补其正反例、原理、源码锚点、性能、风险和 `-T` 教学子任务；M8.1 不应成为新功能的默认主任务。每个任务 GREEN 时执行本任务新解锁 ID 和既往已解锁 ID 的回归，记录执行/通过/失败/未运行四个独立计数及平台维度。测试“已归属”与“已通过”两项指标分别计算，均不能由单一总数替代。

**零遗漏门槛（四道闸）：** “零遗漏”不是单一 diff=空，而是四道闸全开：
(1) **机械生成三集**——A(spec_atoms)/B(impl_atoms)/C(official-tests) 的“源侧”由 `tools/extract_*` 脚本再生（用固定 `VERSION` + 文件摘要锁定基线），人只填归属，绝不参与枚举；
(2) **三角 diff**——A∩B∩C + 通过的 Rust 测试 = `verified`；A only/B only/C only 三个红色危险区分别对应规范死角/实现独占契约/runtime 行为，必须各自有兜底测试；
(3) **变异注入差分**——故意改 reference 编译器一个行为（翻转 loop var capture、改一条 escape 结果、关一个 bounds check），验证 harness 能报出差异；抓不到注入 bug 的 harness 不算有效，禁止用它声明覆盖；
(4) **负测试差分**——reference 拒绝/报错的用例（`errorcheck`/预期失败 `run`），Rust 也必须拒绝；“不该编译的代码竟然编译过”是遗漏的典型表现，从 M0 起即跑，不等 M8。
动态子测试与匹配版本 runner 的发现/执行日志交叉校验，未能枚举则 `unresolved-discovery` 阻断完成声明。按官方 GOOS/GOARCH 与实验条件建适用矩阵；交叉编译产物无目标执行环境时保持 `blocked`，编译专用证据不能替代运行证据。最终声明完整覆盖还要求全部适用记录 `pass`、白盒移植有逐条 Rust 侧证据；T3 范围外架构与明确范围外的相邻工具测试只声明边界，不称已由 Rust 编译器通过。

测试指令与目录族见 [`go_compiler_tests.md`](go_compiler_tests.md)。Go 1.27.1 入口是 `src/cmd/internal/testdir/testdir_test.go`，不是已删除的 `test/run.go`。当前五层目录表只提供导航，尚未生成逐条库存，因此本计划目前**无法证明**功能或官方测试已零遗漏。每门提交新增通过项、旧门回归、阻塞原因、性能基线和教学链接。缺匹配参考工具链或目标执行环境时标记 `blocked`，不可把宿主其他版本的结果充作基线。Rust 项目建立后的质量门为 `cargo fmt --check`、`cargo clippy --workspace --all-targets -- -D warnings`、`cargo test --workspace`。

业界资料仅作设计/测试借鉴：[Go compiler overview](https://github.com/golang/go/blob/master/src/cmd/compile/README.md)、[Cranelift IR](https://github.com/bytecodealliance/wasmtime/tree/main/cranelift/docs)、[LLVM Testing Guide](https://llvm.org/docs/TestingGuide.html)、[rustc-dev-guide](https://rustc-dev-guide.rust-lang.org/)、[rustc-perf](https://github.com/rust-lang/rustc-perf)。外链主分支会变，源码行号以本地版本为准。
