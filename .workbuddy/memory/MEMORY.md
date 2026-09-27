# learn_compiler — 项目长期笔记

## 项目目标
学习编译器实现。两条线索：
1. `doc/`：*Engineering a Compiler* (2nd ed.) 中英文/PDF + `chapters/` 分章 markdown + `images/`。
2. `go_source_code/`：Go 官方源码（**go1.27.1**），重点看真实工业级编译器。

## Go 源码阅读地图（编译器相关）

| 阶段 | 目录 |
|---|---|
| 词法/语法 | `src/cmd/compile/internal/syntax` |
| 类型检查 | `src/cmd/compile/internal/types2` |
| IR 构造 noding | `internal/noder` + `internal/ir` + `internal/types` |
| 中端优化 | `internal/inline` / `escape` / `devirtualize` |
| Walk 降糖定序 | `internal/walk` |
| 通用 SSA | `internal/ssagen` + `internal/ssa` |
| 机器码 | `internal/ssa`(lower) → `src/cmd/internal/obj` |
| 链接 | `src/cmd/link` |

- 架构后端：`internal/{amd64,arm,arm64,loong64,mips,mips64,ppc64,riscv64,s390x,wasm,x86}`
- SSA 规则生成物：`internal/ssa/_gen/*.rules` + `*Ops.go` → `go generate` → `rewrite*.go`
- 共享底层：`cmd/internal/{obj,objabi,goobj}`、`src/internal/{pkgbits,abi}`
- 标准库前端（编译器基本不用，供工具链用）：`src/go/{ast,parser,scanner,token,types}`
- 必读文档：`src/cmd/compile/README.md`、`src/cmd/compile/abi-internal.md`

## 文档产出（`doc/`）

| 文档 | 内容 |
|---|---|
| `go_layout.md` | 编译器代码目录地图 |
| `go_compiler_tests.md` | 测试用例梳理（五层体系） |
| `go_book_mapping.md` | **源码 ↔ 书章节对照手册（正向 + 反向索引）** |
| `chapters/` | 书的分章 markdown（ch01–ch13 + 附录 A/B）|

## 书章 ↔ 源码速查（详见 `doc/go_book_mapping.md`）

| 书章 | 源码 |
|---|---|
| Ch02 扫描器 | `syntax/{scanner,tokens}.go`（手写状态机，非 DFA 表） |
| Ch03 解析器 | `syntax/parser.go`（无回溯递归下降 + 优先级爬升，非 LL/LR） |
| Ch04 类型 | `types2/`（ad hoc 语法制导翻译，非属性文法）；入门先读 `src/go/types/` |
| Ch05 IR | `syntax`(AST) → `ir`(AST) → `ssa`(图) → `obj.Prog`(三地址码) |
| Ch06 过程抽象 | `abi/abiutils.go`、`abi-internal.md`、闭包=静态链 `walk/closure.go` |
| Ch07 代码形态 | **`walk/` 整个包**（order=定序、switch/range=脱糖） |
| Ch08 优化导论 | `ssa/compile.go` 的 `passes` 数组 + `inline/inl.go` |
| Ch09 数据流 | **`ssa/dom.go`**（含 Lengauer-Tarjan 与迭代 intersect 两种实现）、`sccp.go`、`prove.go` |
| Ch10 标量优化 | `licm.go`(提升)、`cse.go`(支配树值编号)、`magic.go`(强度削减)、`deadcode.go` | 
| Ch11 指令选择 | `ssa/_gen/*.rules` → `rewrite*.go`、`lower.go`、`_gen/rulegen.go`(≈BURG) |
| Ch12 调度 | **`ssa/schedule.go`**（块内表调度 + Score 优先级）、`layout.go`(块排列) |
| Ch13 寄存器分配 | **`ssa/regalloc.go`（线性扫描，非图着色）**、`stackalloc.go`(冲突图用在栈槽) |
| 附录 A ILOC | `cmd/internal/obj/link.go` 的 `Prog`（From/To/Reg） |
| 附录 B 数据结构 | `ssa/sparse*.go`、`bitvec/bv.go`、`ir/bitset.go`、`types2/scope.go` |

## 书讲了但 Go 没做的（读代码别找）

扫描器 DFA/最小化、LL(1)/LR 表、属性文法、树高平衡、循环展开、LCM/PRE、用户代码的尾调用消除、超块克隆、循环外提、踪迹调度、软件流水线、图着色寄存器分配。

## Go 有但书没讲的

Unified IR(`noder/`)、写屏障(`ssa/writebarrier.go`)、GC 安全点活性(`liveness/plive.go`)、逃逸分析(`escape/`)、PGO(`pgoir/` + `cmd/preprofile`)、栈分裂检查。

## 约定
- 统计代码量时排除 `*_test.go`，用 `find <dir> -name '*.go' ! -name '*_test.go' -exec cat {} + | wc -l`。
- 分析大目录时优先用 `ls -d */` + 分批 `ls`，避免一次性读取上万文件。

## Rust 重写计划：不遗漏模型（2026-09-26 固化）

计划文档 `doc/rust_go_compiler_{architecture,rewrite_plan}.md` 已采用以下决策，后续工作须遵守：

- **三角 ground truth**：A=spec_atoms（机械解析 `doc/go_spec.html` 的 h2/h3）、B=impl_atoms（机械扫源码树：pragma/flag/符号/rules 按 pass 分）、C=official-tests。feature `verified` = 三集都有归属 + 一条通过的 Rust 测试。
- **三红区**：A only=规范死角、B only=实现独占契约（PGO/写屏障/ABIInternal/PCLN/escape，spec 不提）、C only=runtime 行为（goroutine/map 随机化）。
- **四道闸**：机械生成三集 / 三角 diff / 变异注入差分 / 负测试差分（reference 拒绝的 Rust 也须拒绝）。全开才许声明"零遗漏"。
- **目标切档**：T1=amd64/linux（必做）、T2=arm64/linux（应做）、T3=其余 9 架构（`scope-excluded`，不进 M7.2）。理由：obj/arm64=35612 行、obj/x86=15992 行，全做不可完成且对学习项目零边际价值。
- **`_gen/*.rules` 按 pass 分**（主/latelower/splitload/simd 独立 feature，27 文件/20643 行），不是每 arch 一条。
- **锚点教训**：`dirs` 实在 `testdir_test.go:74`（`:73` 是 TODO 注释），曾长期被抄成 `:73`。

## bootstrap 工具现状（2026-09-26 落盘 + 三角 diff 完成）

`rust_go_compiler/`（Python，stdlib-only，零 PyPI）是这套模型的落地实现，**编译器本体尚不存在**。

| 文件 | 作用 |
|---|---|
| `tools/models.py` | dataclass + 手写 TOML emit + `tomllib` load；含 `load_atom_ids()` 共享入口 |
| `tools/extract_spec_atoms.py` | A 集：`go_spec.html` 的 `<h2/h3 id="...">` → **125** atom（19 h2 + 106 h3）|
| `tools/extract_impl_atoms.py` | B 集 → **183**（pragma 19 + flag 66 + rules 27 + obj 71）|
| `tools/extract_test_atoms.py` | C 集 → **2738**（L1 2728 + L3 计数存根 1 + L5 9）|
| `tools/validate_features.py` | 四道闸校验器，9 错误码，exit 1 = 违规 |
| `tools/triangle_diff.py` | A×B×C×features → 三红区 + 悬空引用；exit 1 = 悬空 |

- **C 集是 2738 不是 2825**：`dirs` 含 `"codegen"`，早期版本又单独遍历 `test/codegen`，87 个文件被数两遍。现 L2 降为 L1 原子的属性 `also_in=["L2"]` + `asmcheck_assertions`。**一物理文件 = 一原子**。
- **红区基线**（go1.27.1，seed 2 feature）：A 2/125、B 3/183、C 3/2738，红区 3038，悬空 0。报告在 `coverage/triangle-diff.txt`。
- **exit code 语义**：悬空引用 = 数据错误（exit 1）；红区 = 未认领待办（exit 0）。
- 跑法统一：`PYTHONPATH=tools <py> tools/xxx.py`；单测 `PYTHONPATH=tools <py> -m unittest discover -s tests -v`（34 个用例）。
- **已知未修**：A 集的 `Introduction`/`Notation` 是叙述性章节（非编译器行为），会永久留在 A-only，候选加 `claimable=false`；A-only 123 条里噪声约 2%。
