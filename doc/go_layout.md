# Go 编译器代码目录地图（go1.27.1）

> 基于 `go_source_code/` 实测。配套阅读：[`go_compiler_tests.md`](./go_compiler_tests.md)（测试用例梳理）。
> 权威原文：`go_source_code/src/cmd/compile/README.md`、`src/cmd/compile/abi-internal.md`。

---

## 0. 总体结论

Go 编译器相关代码**不在一个目录里**，分布在四个位置：

| 位置 | 角色 | 规模（非测试 `.go`） |
|---|---|---|
| `src/cmd/compile/` | **编译器本体**（`gc` = Go Compiler） | 551 文件 / 62.6 万行 |
| `src/cmd/internal/` | 汇编器、目标文件格式、编译期配置等共享底座 | obj 相关约 6 万行 |
| `src/go/` | 标准库 Go 前端（ast/parser/types…），**编译器已基本不用** | 约 3.4 万行 |
| `src/cmd/{go,asm,link}` | 构建驱动、汇编器、链接器 | go 7.4 万 / link 4.4 万行 |

> 注意：`gc` 是 "Go Compiler" 的缩写，**与垃圾回收 GC 无关**。

---

## 1. 编译流水线 ↔ 目录对应

依 `src/cmd/compile/README.md` 的阶段划分：

| 阶段 | 目录 | 职责 |
|---|---|---|
| 1 词法/语法 | `internal/syntax/` | 词法分析、语法分析、构造语法树（含位置信息，供报错与调试信息用） |
| 2 类型检查 | `internal/types2/` | `go/types` 的移植版，改用 syntax 的 AST |
| 3 IR 构造 noding | `internal/noder/` + `internal/ir/` + `internal/types/` | **Unified IR**：把 typecheck 结果转成编译器自有 AST；同时承担包导入导出与内联 |
| 4 中端优化 | `internal/inline/` `internal/escape/` `internal/devirtualize/` | 内联、逃逸分析、接口调用去虚拟化；早期死代码消除在 Unified IR 写出阶段完成 |
| 5 Walk | `internal/walk/` | 求值定序（order）+ 语法脱糖（switch → 二分/跳转表，map/chan 操作 → 运行时调用） |
| 6 通用 SSA | `internal/ssagen/` + `internal/ssa/` | IR→SSA、函数 intrinsic 应用、机器无关优化 |
| 7 机器码 | `internal/ssa/`(lower/regalloc) → `src/cmd/internal/obj` | 降级到目标架构、寄存器分配、栈帧布局、指针活性分析 |

---

## 2. `src/cmd/compile/internal/` 全部子包

| 包 | 行数 | 说明 |
|---|---|---|
| `ssa/` | 475575 | SSA 与后端，**体量最大** |
| `types2/` | 23204 | 类型检查 |
| `noder/` | 11196 | Unified IR 读写 |
| `ir/` | 10205 | 编译器 AST 与类型节点 |
| `walk/` | 9451 | 定序与脱糖 |
| `inline/` | 7681 | 内联 |
| `typecheck/` | 6860 | 类型检查辅助 |
| `escape/` | 3515 | 逃逸分析 |
| `reflectdata/` | 2951 | 反射元数据 |
| `gc/` | 1102 | 编译驱动与导出 |
| `staticdata/` | 521 | 静态数据 |
| 其余 | — | `abi` `abt` `base` `bitvec` `bloop` `compare` `coverage` `deadlocals` `devirtualize` `dwarfgen` `importer` `liveness` `logopt` `loopvar` `midway` `objw` `pgo` `pgoir` `pkginit` `rangefunc` `rttype` `slice` `ssagen` `staticinit` `typebits` `types` |

值得单独记住的：

- `pgo/` + `pgoir/` —— PGO 剖析引导优化
- `liveness/` —— GC 安全点的指针活性分析
- `dwarfgen/` —— DWARF 调试信息生成
- `loopvar/` `rangefunc/` —— Go 1.22 循环变量语义与新迭代器语义检查
- `coverage/` + `instrument` —— 覆盖率插桩
- `abi/` —— 内部 ABI（寄存器传参）计算
- `test/` —— 编译器级微测试（见测试文档 §3）

---

## 3. SSA 目录 `cmd/compile/internal/ssa/`

139 文件 / 47.6 万行，两类内容必须分清：

**手写 pass**：`regalloc.go` `schedule.go` `stackalloc.go` `prove.go` `cse.go` `deadcode.go` `deadstore.go` `phiopt.go` `licm.go` `nilcheck.go` `branchelim.go` `copyelim.go` `looprotate.go` `loopbce.go` `checkbce.go` `lower.go` `writebarrier.go` `memcombine.go` `shortcircuit.go` `fuse*.go` `softfloat.go` `trim.go` `split*.go`

**生成物**：`_gen/` 下是源规则唯一真源：

```
_gen/
  generic.rules  386.rules  AMD64.rules  ARM.rules  ARM64.rules
  LOONG64.rules  MIPS.rules  MIPS64.rules  PPC64.rules
  RISCV64.rules  S390X.rules  Wasm.rules
  *Ops.go          # 算子定义
  *splitload.rules  *latelower.rules  # 特定 pass 的规则
```

经 `go generate` 生成同目录的 `rewriteAMD64.go`、`rewritegeneric.go`、`opGen.go`、`rewritedec.go` 等。

> **改优化规则要改 `.rules`，不要碰 `rewrite*.go`**（会被覆盖）。

---

## 4. 架构后端

`internal/` 下 11 个后端目录：

```
amd64  arm  arm64  loong64  mips  mips64  ppc64  riscv64  s390x  wasm  x86
```

每个目录只放三类文件：`ssa.go`（lower 与寄存器约束）、`ggen.go`（函数序言/尾声）、`galign.go`（栈对齐）。`amd64` 等个别架构另有 `simdssa.go`。

---

## 5. 机器码与共享底座

| 目录 | 作用 |
|---|---|
| `src/cmd/internal/obj/` | 实际发射机器码，含 `arm/ arm64/ loong64/ mips/ ppc64/ riscv/ s390x/ wasm/ x86/` 子目录 |
| `src/cmd/internal/objabi/` | 编译期常量与配置（GOOS/GOARCH、栈帧约定等） |
| `src/cmd/internal/goobj/` | 目标文件（.o）读写格式 |
| `src/cmd/internal/src/` | 位置信息（`Pos`）跨工具链共享 |
| `src/internal/pkgbits/` | Unified IR 的序列化编解码（编译单元间交换 IR） |
| `src/internal/abi/` | 编译器与运行时共享的 ABI 定义 |
| `src/internal/exportdata/` | 编译好的包数据读取 |
| `src/internal/goarch/` `goos/` `goexperiment/` `buildcfg/` `goversion/` | 平台与实验特性开关 |

---

## 6. `src/go/` 家族（易误解点）

```
src/go/
  ast/  parser/  scanner/  token/  types/  constant/  importer/  format/  printer/  doc/  build/  version/
```

这些包是**给工具链用的**（gofmt、vet、gopls、godoc），编译器不依赖它们。

关键关系：**`types2` 是 `go/types` 移植到 syntax AST 的产物**，二者长期保持功能对齐。读 `go/types` 远比读 `types2` 友好，适合先打基础。

---

## 7. 外围工具链

| 工具 | 位置 | 说明 |
|---|---|---|
| `go build` 驱动 | `src/cmd/go/` | 227 文件 / 7.4 万行，负责依赖图、构建缓存、调度 compile/link |
| 汇编器入口 | `src/cmd/asm/` | 内部复用 `cmd/internal/obj` |
| 链接器 | `src/cmd/link/` | 140 文件 / 4.4 万行，含 `internal/ld/` 与各架构文件 |
| 构建分发包 | `src/cmd/dist/` | `build.go` + `test.go`（测试调度总入口） |

---

## 8. 建议阅读路线

1. 先读 `src/cmd/compile/README.md` + `abi-internal.md`（权威导览）
2. `syntax/` → `types2/`（或先读更友好的 `src/go/types`）
3. `noder/` + `ir/`（Unified IR，现代 Go 编译器最独特之处）
4. `walk/` → `ssagen/` → `ssa/` 的 pass 执行顺序
5. `ssa/_gen/*.rules` 配合 `prove.go`、`regalloc.go` 深入后端

与 `doc/` 下的 *Engineering a Compiler* 对照读：理论看扫描 / 语法 / 类型三章，工程实现看 Go 源码的 `walk` 之后各阶段。
