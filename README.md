# learn-go-compiler

用 **Go 1.27.1 官方编译器的真实源码**学习编译器原理 —— 把教材理论、工业级实现、和一次完整的重写计划串成一条线。

这个仓库是学习过程的产物：读完的结论、对照索引、以及为"不遗漏地重写一个编译器"而写的工具。

## 仓库内容

| 路径 | 内容 |
|---|---|
| `doc/go_layout.md` | Go 编译器代码目录地图：七个编译阶段 ↔ 目录对应关系 |
| `doc/go_compiler_tests.md` | 测试体系梳理：L1–L5 五层，含 go1.27 已删除 `test/run.go` 这类陷阱 |
| `doc/go_book_mapping.md` | **源码 ↔ 教材章节双向对照手册**（正向索引 + 反向索引 + 书/代码差异提醒）|
| `doc/go_abi.md` | 一次函数调用在编译器眼里被拆成什么：ABI 原理与 Go 实现对照 |
| `doc/rust_go_compiler_architecture.md` | Rust 重写项目的架构约束、阶段门与验收标准 |
| `doc/rust_go_compiler_rewrite_plan.md` | Rust 重写实施计划（里程碑 + 任务卡 + 覆盖模型）|
| `doc/devlog/` | 开发日志，保留失败测试与实际命令 |
| `rust_go_compiler/` | 覆盖度 bootstrap 工具：三套 ground truth + 四道闸校验 + 三角 diff |
| `AGENTS.md` | 面向 AI 编码助手的仓库工作手册 |

## 不包含什么

出于**版权**与**体积**考虑，以下内容不在本仓库中：

| 排除项 | 原因 | 如何获取 |
|---|---|---|
| *Engineering a Compiler* (2nd ed.) 的 PDF、全文 markdown 转换件、章节拆分（`doc/chapters/`）与插图（`doc/images/`） | 受版权保护的出版物，不在公开仓库分发其副本 | 请自行购买原书 |
| `go_source_code/`（Go 1.27.1 源码树，185 MB / 约 16000 文件） | 体积大，且官方可直接下载 | <https://go.dev/dl/> |

> **关于 `doc/chapters/` 与 `doc/images/`**：这两项是原书正文与插图的逐字复制件，曾短暂随仓库私有化而入库（2026-09-27），改回 public 时已移出版本管理，**文件仍保留在本地磁盘**。阅读本仓库文档时它们不存在，但 `doc/go_book_mapping.md` 已提供完整的**章节 ↔ 源码包**对照，足以在不打开原书的情况下导航。

**这意味着**：`doc/` 中指向教材章节的链接、以及形如 `src/cmd/compile/internal/ssa/dom.go:120` 的源码引用，需要在本地补齐上述两项后才能点开。**所有行号锚点都是按 Go 1.27.1 实际核对过的**，补齐源码树即可逐条验证。

补齐后的本地目录应当长这样：

```
learn_compiler/
├── AGENTS.md
├── doc/                     # 本仓库的 doc/（教材原文需自备）
└── go_source_code/          # 从 go.dev 解压的 Go 1.27.1 源码树
```

## 三份核心文档怎么配合

```
想通读编译器           → go_layout.md          建立全局地图
读书时想看对应实现     → go_book_mapping.md §1   章节 → 源码文件
打开源码看不懂         → go_book_mapping.md §2   源码文件 → 章节（回查理论）
想验证自己的理解       → go_compiler_tests.md   找现成测试跑一遍
发现书和代码对不上     → go_book_mapping.md §3   先看是不是已知差异
```

`go_book_mapping.md` §3 列了两类差异，这是读工业编译器最容易被绊住的地方：

- **书上讲了、Go 没做**：RE→DFA 最小化、LL/LR 分析表、属性文法、用户代码尾调用消除、图着色寄存器分配、踪迹调度
- **Go 做了、书上没讲**：Unified IR（`noder/`）、写屏障、GC 安全点活性、逃逸分析、PGO、栈分裂检查

## 覆盖度工具（`rust_go_compiler/`）

"零遗漏"不能靠单一真值来源来声明。这个目录里的工具用**三套独立、可机械再生**的清单做交叉验证：

| 集合 | 来源 | 规模（Go 1.27.1）|
|---|---|---|
| **A** 规范 | 解析 `go_spec.html` 的每个 `<h2>/<h3>` | 125 条 |
| **B** 实现 | 扫源码树：`//go:` pragma / 编译 flag / `_gen/*.rules` / `cmd/internal/obj` | 183 条 |
| **C** 测试 | 按 runner 自身的发现规则枚举测试树 | 2738 条 |

三个集合两两 diff，暴露三个红区——**这正是遗漏藏身的地方**：

- **A-only**：规范写了但无人实现/测试 —— 最隐蔽，因为测试全绿也可能漏语义
- **B-only**：编译器实现的、规范根本没提的契约（PGO、写屏障、`ABIInternal`、PCLN）—— 只能靠 C 兜底
- **C-only**：测试覆盖但规范不定义精确行为（goroutine 调度、map/select 随机化）—— 只能运行时差分

工具还实现了**四道闸**来防止"声明了覆盖其实没覆盖"：机械生成三集、三角 diff、变异注入差分、负测试差分。

```sh
cd rust_go_compiler
PYTHONPATH=tools python3 tools/extract_spec_atoms.py    # 再生 A
PYTHONPATH=tools python3 tools/extract_impl_atoms.py    # 再生 B
PYTHONPATH=tools python3 tools/extract_test_atoms.py    # 再生 C
PYTHONPATH=tools python3 tools/validate_features.py coverage/features.toml
PYTHONPATH=tools python3 tools/triangle_diff.py         # 未认领清单
```

只用 Python 标准库（`tomllib` / `unittest`，需 Python ≥ 3.11），无第三方依赖。详细说明见 [`rust_go_compiler/README.md`](rust_go_compiler/README.md)。

## Rust 重写项目

本仓库的 `doc/rust_go_compiler_*.md` 与 `rust_go_compiler/` 工具服务于一个独立项目：**用 Rust 重写 Go 1.27.1 的 `cmd/compile`**。

编译器实现本体在另一个仓库：**[`nobody0726/go-compiler-rust`](https://github.com/nobody0726/go-compiler-rust)**。

两个仓库分工：本仓库放"读懂了什么、怎么保证不漏"（分析、索引、覆盖工具），实现仓库放"写出了什么"（crates、测试、CI）。

## 基线版本

- Go 源码树：**go1.27.1**
- 教材：*Engineering a Compiler*, 2nd Edition（Keith Cooper, Linda Torczon）
- 覆盖度工具：Python 标准库，实测于 Python 3.13
- 仓库可见性：**public**（不含教材原文，见上文「不包含什么」）
