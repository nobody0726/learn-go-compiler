# AGENTS.md

> 本文件面向在本仓库中工作的 AI 编码助手（Codex / WorkBuddy 等）。
> 内容说明**这个仓库是什么、目录怎么组织、已有文档承担什么作用**，以及必须遵守的操作约定。

## 1. 仓库定位

这是一个**个人学习仓库**，目标：**通过 Go 语言官方编译器的真实源码，学习编译器原理**。

它本身不是软件项目，没有构建产物、没有测试套件、也没有需要维护的代码。仓库里只有三类东西：

| 类别 | 位置 | 性质 |
|---|---|---|
| 教材 | `doc/` | *Engineering a Compiler* (2nd ed.) 的 PDF + 分章 Markdown + 图片 |
| 工业源码 | `go_source_code/` | Go 1.27.1 官方源码树，**只读参考，禁止修改** |
| 学习辅助文档 | `doc/go_*.md` | 由助手生成的索引与对照手册，是仓库的**核心产出** |

因此：**在这个仓库里"干活"通常等于"读源码 + 写/改 doc 下的 Markdown"**，而不是写代码。

## 2. 目录结构

```
learn_compiler/
├── AGENTS.md                     # 本文件
├── doc/                          # 教材 + 学习辅助文档（主要工作区）
│   ├── Engineering_a_compiler_2nd.pdf        # 教材原书 PDF（7.9 MB）
│   ├── Engineering_a_compiler_2nd.md         # 全书单文件 Markdown（1.6 万行）
│   ├── Engineering_a_compiler_2nd_raw.md     # 转换原始产物，未清洗，一般不读
│   ├── Engineering_a_compiler_2nd copy.md    # 早期副本，已废弃，不要引用
│   ├── chapters/                 # 教材按章拆分（推荐按章读，见 chapters/README.md）
│   │   ├── README.md                         # 全书章节目录索引
│   │   ├── 00-front-matter.md                # 前言 / 目录
│   │   ├── ch01-overview-of-compilation.md   # Ch01 编译概览
│   │   ├── ch02-scanners.md                  # Ch02 词法分析
│   │   ├── ch03-parsers.md                   # Ch03 语法分析
│   │   ├── ch04-context-sensitive-analysis.md# Ch04 上下文相关分析（类型检查）
│   │   ├── ch05-intermediate-representations.md
│   │   ├── ch06-the-procedure-abstraction.md
│   │   ├── ch07-code-shape.md
│   │   ├── ch08-introduction-to-optimization.md
│   │   ├── ch09-data-flow-analysis.md
│   │   ├── ch10-scalar-optimizations.md
│   │   ├── ch11-instruction-selection.md
│   │   ├── ch12-instruction-scheduling.md
│   │   ├── ch13-register-allocation.md
│   │   ├── appendix-a-iloc.md
│   │   ├── appendix-b-data-structures.md
│   │   ├── back-bibliography.md / back-index.md
│   ├── images/                   # 390 张教材插图 PNG，由 chapters/*.md 相对引用
│   ├── go_layout.md              # ★ 文档① 代码目录地图
│   ├── go_compiler_tests.md      # ★ 文档② 测试用例梳理
│   └── go_book_mapping.md        # ★ 文档③ 源码 ↔ 教材章节对照手册
├── go_source_code/               # ★ 只读 ★ Go 1.27.1 官方源码树
│   ├── VERSION                   # 版本号
│   ├── src/cmd/compile/          # 编译器本体（gc）
│   ├── src/cmd/link/             # 链接器
│   ├── src/cmd/asm/              # 汇编器
│   ├── src/cmd/go/               # go 构建驱动
│   ├── src/go/                   # 标准库 Go 前端（工具链用，编译器不依赖）
│   ├── test/                     # 端到端测试用例（fixedbugs / codegen / escape …）
│   └── doc/                      # go 自己的文档（与仓库根的 doc/ 无关，勿混淆）
└── .workbuddy/memory/            # 助手的工作记忆，本仓库的长期上下文
    ├── MEMORY.md                 # 项目长期笔记（目录地图、阅读路线、约定）
    └── YYYY-MM-DD.md             # 每日工作日志（只追加）
```

> **易踩坑点**：仓库根有 `doc/`（教材），源码树里也有 `go_source_code/doc/`（go 官方文档）。
> 两者完全不同，写路径时务必写全。本文件提到的 `doc/xxx.md` 一律指**仓库根的 `doc/`**。

## 3. 已生成文档的作用

`doc/` 下三份 `go_*.md` 是本仓库的核心学习资产，各司其职、互相交叉引用：

### ① `doc/go_layout.md` — 代码目录地图（150 行）

**作用**：回答"Go 编译器代码在哪、哪一块负责什么"。

- 把 `src/cmd/compile/internal/` 的**七个编译阶段**与目录一一对应（syntax → types2 → noder → inline/escape → walk → ssagen/ssa → obj）
- 列出 SSA 目录、11 个架构后端、共享底座（obj / objabi / goobj / pkgbits / abi）
- 澄清两个高频误解：`gc` = Go Compiler（不是垃圾回收）；`src/go/` 是工具链前端，编译器**不用**它
- 给出建议阅读路线

**什么时候用**：想找某个功能在哪个目录；第一次进入源码树时建立全局观。

### ② `doc/go_compiler_tests.md` — 测试用例梳理（321 行）

**作用**：回答"这些代码怎么被测试、验证手段是什么"。

- 把测试分成五层：L1 `test/` 端到端黑盒 → L2 `test/codegen/` 汇编断言 → L3 `compile/internal/test/` 编译器级微测试 → L4 各包单元测试 → L5 `compile/testdata/script/` CLI 脚本
- 记录关键陷阱：go1.27 已删除 `test/run.go`，入口改为 `src/cmd/internal/testdir/testdir_test.go`
- 解释测试首行的 14 种指令（`run` / `errorcheck` / `asmcheck` …）
- 指出哪些关键 pass（escape / inline / walk / gc）**故意没有单元测试**及其原因
- 附「按编译阶段索引测试文件族」与「新增测试该放哪」对照表，以及常用命令

**什么时候用**：写一个小例子验证某条优化是否生效；确认某个行为是规范还是实现细节；改源码后知道该跑哪些测试。

### ③ `doc/go_book_mapping.md` — 源码 ↔ 教材对照手册（650 行）

**作用**：回答"读这本书的某一节，该去看哪段代码"。这是**三份文档里最核心的一份**。

- **§1 正向索引**：按 Ch01–Ch13 + 附录 A/B 逐节列出 → 对应源码文件 → 一句话说明
- **§2 反向索引**：按源码目录分组 → 每个文件标注对应章节号（读代码时反查书）
- **§3 差异提醒**：书里有、Go 里没有的技术（RE→DFA、LL/LR 表、属性文法、尾调用优化、图着色分配、踪迹调度），以及 Go 有、书里没讲的（Unified IR、写屏障、GC 安全点、逃逸分析、PGO）
- **§4 建议切入顺序**：给出几条不同时间预算的阅读路线

**什么时候用**：任何"书 ↔ 代码"的跳转。**读源码前先查这张表**，能省掉大量盲找时间。

### 三份文档的配合方式

```
想通读编译器           → go_layout.md（建立地图）
读书时想看对应实现     → go_book_mapping.md §1（章节 → 文件）
打开某个源码文件看不懂 → go_book_mapping.md §2（文件 → 章节，回查理论）
想验证自己的理解       → go_compiler_tests.md（找现成测试跑一遍）
发现书和代码对不上     → go_book_mapping.md §3（先看是不是已知差异）
```

三者均为**生成物**：内容来自实际读取源码与书籍得到的事实。若后续源码树更新或发现错误，应**直接修改对应文档**，而不是新建第四份平行文档。修改后请同步更新 `doc/chapters/README.md` 之外的交叉引用链接。

## 4. 操作约定（重要）

1. **`go_source_code/` 是只读参考**。不要在其中新建、修改、删除任何文件；不要 `go build` / `go test` 整个源码树。需要验证行为时，在仓库外另建临时目录写小程序。
2. **统计代码量必须排除测试**，否则数字虚高：
   ```sh
   find <dir> -name '*.go' ! -name '*_test.go' -exec cat {} + | wc -l
   ```
3. **不要手改生成文件**。`ssa/rewrite*.go`、`ssa/opGen.go` 由 `ssa/_gen/*.rules` 经 `go generate` 生成。要讨论优化规则，看 `.rules`；`.go` 是产物。
4. **引用源码时给出 `文件:行号`**，例如 `src/cmd/compile/internal/ssa/dom.go:120`，方便跳转核对。
5. **区分教材版本**：`doc/Engineering_a_compiler_2nd copy.md` 是废弃副本，`_raw.md` 是未清洗的转换产物。引用教材原文一律用 `doc/chapters/*.md` 或 `Engineering_a_compiler_2nd.md`。
6. **新生成的文档放 `doc/` 下，使用 `.md` 格式**，并保持与现有三份文档的交叉引用关系。
7. **语言**：文档与回复使用简体中文；源码路径、符号名、代码保持原文。
8. **不要臆造章节号或文件路径**。本仓库的价值全在"可核对"，写完后应实际校验文件是否存在。

## 5. 相关外部资料（在源码树内，只读）

| 文件 | 用途 |
|---|---|
| `go_source_code/src/cmd/compile/README.md` | 编译器权威导览，最应先读 |
| `go_source_code/src/cmd/compile/abi-internal.md` | 内部 ABI 规范（栈帧、寄存器、调用约定） |
| `go_source_code/test/README.md` | 测试体系说明 |
| `go_source_code/test/codegen/README` | 汇编断言测试写法 |
| `go_source_code/src/cmd/internal/testdir/testdir_test.go` | 测试驱动，了解测试指令用法的权威来源 |

## 6. 当前状态

- 源码树版本：**Go 1.27.1**（`go_source_code/VERSION`）
- 已完成：代码目录地图、测试用例梳理、源码↔教材对照手册三份文档
- 工作记忆位于 `.workbuddy/memory/`，记录项目约定与阅读进度，续接工作前可先读 `MEMORY.md`
