# Go 编译器测试用例梳理（go1.27.1）

> 基于 `go_source_code/`（`VERSION` = **go1.27.1**）实测统计。配套阅读：[`go_layout.md`](./go_layout.md)（目录地图）。

---

## 0. 五层测试体系全景

Go 编译器没有单一的测试目录，测试分布在五个层次，**职责互不重叠**：

| 层 | 位置 | 驱动方式 | 规模 |
|---|---|---|---|
| L1 端到端黑盒 | `go_source_code/test/`（即 GOROOT/test） | `go test cmd/internal/testdir` | 3516 文件 / 3400 `.go` |
| L2 汇编断言 | `test/codegen/` | 同一驱动的 `asmcheck` action | 87 `.go` / 1775 条断言 |
| L3 编译器级微测试 | `src/cmd/compile/internal/test/` | 普通 `go test` | 43 文件 / 30805 行 |
| L4 分阶段白盒单测 | `src/cmd/compile/internal/<pkg>/*_test.go` | 普通 `go test` | 约 100 文件 / 2.7 万行 |
| L5 编译器 CLI 脚本测试 | `src/cmd/compile/testdata/script/` | `script_test.go` + testscript | 9 个 `.txt` |

一句话记忆：**L1/L2 测「编译出来的程序对不对」，L3/L4 测「编译器内部各 pass 对不对」，L5 测「编译器命令行界面对不对」。**

---

## 1. L1：端到端测试套件 `test/`

### 1.1 驱动与注册

- 唯一的 runner：`src/cmd/internal/testdir/testdir_test.go`（约 1200 行，并发执行 + 分片）
- 说明文档：`test/README.md`
- 注册位置：`src/cmd/dist/test.go:1060` 把 `../test` 注册为包 `cmd/internal/testdir` 的测试项，CI 上默认分 10 个 shard（`GO_BUILDER_NAME` 时）
- 注意：**go1.27 已没有 `test/run.go`**（旧版本有），网上老资料提到的路径已失效
- 每个测试文件用**第一行特殊注释**声明自己的类型，这是理解全套测试的钥匙

### 1.2 测试指令（directive）速查表

来源：`testdir_test.go` 的 `case` 分支（约 542 行起）。

| 指令 | 含义 | 是否需要 `.out` |
|---|---|---|
| `// run` | 编译并运行，期望正常退出 | 否 |
| `// buildrun` | 只构建后运行（不起完整编译流程） | 否 |
| `// rundir` / `// runindir` | 在目录中编译并运行 | 否 |
| `// runoutput` | 运行并与 `*.out` 比对 stdout | 是 |
| `// compile` | 只编译，期望成功（不运行） | 否 |
| `// compiledir` | 只编译目录 | 否 |
| `// build` / `// builddir` / `// buildrundir` | 只构建 | 否 |
| `// errorcheck` | 编译并比对 `// ERROR "..."` 注释中的报错 | 内嵌注释 |
| `// errorcheckwithauto` | 同上，但期望的 `-m`/`-l` 类诊断信息**自动插入** | 内嵌注释 |
| `// errorcheckdir` | 目录版 errorcheck | 内嵌注释 |
| `// errorcheckandrundir` | errorcheck + 运行 | 内嵌注释 |
| `// errorcheckoutput` | 比对编译器整体输出 | 是 |
| `// asmcheck` | 汇编正则断言（codegen 专用） | 内嵌注释 |
| `// skip` | 跳过 | — |

指令后可带编译参数，常见组合：

| 参数 | 作用 |
|---|---|
| `-0` | 关闭所有优化（考察未优化路径） |
| `-m` | 打印内联 / 逃逸决策 |
| `-l` | 禁用内联；`-l=4` 为 4 层激进内联 |
| `-live` | 打印活性分析结果 |
| `-wb=0` | 关闭写屏障 |
| `-d=ssa/<pass>/debug=N` | **打开某个 SSA pass 的调试输出**（定位 pass 测试的关键） |
| `-gcflags` | 透传编译器标志 |
| `-goexperiment` / `-godebug` | 切换实验特性 / GODEBUG |
| `-t` | 超时秒数 |

### 1.3 顶层指令使用频次（356 个 `.go`）

| 指令 | 文件数 |
|---|---|
| `// run` | 170 |
| `// errorcheck` | 159 |
| `// compile` | 21 |
| `// runoutput` | 14 |
| `// build` | 7 |
| `// skip` | 5 |
| `// rundir` | 4 |
| `// errorcheckoutput` | 3 |
| `// compiledir` | 2 |

`// errorcheckwithauto` 仅 5 个文件使用，但都是重量级：`inline.go`、`inline_endian.go`、`live.go`、`live_regabi.go`、`newinline.go`。

### 1.4 子目录规模

| 目录 | 文件数 | 内容定位 |
|---|---|---|
| `fixedbugs/` | 2356（2302 `.go`，197 个 `.dir`） | 历史 bug 回归，**最大的一块** |
| `typeparam/` | 482 | 泛型（Go 1.18+），含 `*imp.dir` 跨包实例化 |
| `codegen/` | 88 | 见 §2 |
| `abi/` | 56 | 寄存器 ABI（`ABIInternal`）正确性 |
| `ken/` | 42 | Ken Thompson 经典测试集，验证语义正确性 |
| `interface/` | 29 | 接口 itab / 方法表 |
| `dwarf/` | 23 | DWARF 调试信息（`dwarf.dir` + 行表指令） |
| `chan/` | 19 | channel 语义 |
| `syntax/` | 19 | 语法解析报错（`semi*.go` 自动分号、`typesw`、`vareq`） |
| `simd/` | 3 | SIMD 支持 |
| `stress/` | 3 | `maps.go`、`parsego.go`、`runstress.go` |
| `arenas/` | 1 | `smoke.go`（arena 实验） |
| `internal/runtime/` | 2 | 运行时内部 |

`fixedbugs/` 指令分布：`run` 1473、`compile` 1133、`errorcheck` 1027、`build` 67、`runoutput` 14、`skip` 8。
`typeparam/` 指令分布：`run` 193、`compile` 62、`errorcheck` 10、`build` 2。

### 1.5 按编译器阶段索引顶层文件族

顶层 356 个文件按前缀成族，**前缀即主题**，可直接对照编译器流水线：

| 编译阶段 | 文件族（个数） | 典型指令 | 观察点 |
|---|---|---|---|
| 词法 / 语法 | `syntax/`、`semi*`、`char_lit*`、`float_lit*`、`string_lit`、`int_lit`、`ddd*`、`funcdup*`、`eof*` | `// errorcheck` | 报错信息与位置 |
| 类型检查 | `typecheck*`、`assign*`、`cannotassign`、`convert*`、`convlit*`、`const*`(9)、`method*`、`named*`、`initloop`、`undef`、`used`、`varerr`、`parentype` | `// errorcheck` | 类型错误、不可赋值 |
| 泛型 | `typeparam/` | `// run` `// compile` | 实例化、类型推断 |
| IR 构造 noding | `import*`、`initialize`、`initexp`、`initcomma`、`typecheckloop` | `// compile` | Unified IR 导入导出 |
| **逃逸分析** | `escape*.go`（33） | `// errorcheck -0 -m -l` | `escapes to heap` / `moved to heap` |
| **内联** | `inline*.go` + `newinline.go`（10） | `// errorcheckwithauto -0 -m`；`inline_caller.go` 用 `// run -gcflags -l=4` | inline cost、`cannot inline` 原因 |
| **去虚拟化** | `devirt.go`、`devirtualization*.go`（4） | `// errorcheck -0 -m` | 接口调用是否去虚 |
| **活性 / GC 安全点** | `live*.go`（5） | `// errorcheckwithauto -0 -l -live -wb=0 -d=ssa/insert_resched_checks/off` | 活跃栈槽、安全点 |
| **nil 检查消除** | `nilptr*.go`（8） | `// run` / `// errorcheck` | 误报 nil panic、检查消除 |
| **边界检查消除** | `checkbce.go`、`loopbce.go`、`bounds.go`、`index*`(4)、`slice*`(4)、`slicecap`、`sliceopt` | `-d=ssa/check_bce/debug=3` | BCE 是否生效 |
| **prove / 范围分析** | `prove*.go`(4)、`known_bits.go`、`tighten.go` | `-d=ssa/prove/debug=1`、`-d=ssa/tighten/debug=1` | 值域推导、常量折叠 |
| **phiopt** | `phiopt.go` | `-d=ssa/phiopt/debug=3` | 条件移动生成 |
| 写屏障 | `writebarrier.go`、`nowritebarrier.go`、`gc*`、`gcstring` | `// run` / `// errorcheck` | 屏障插入正确性 |
| 栈与帧布局 | `stack.go`、`stackobj*`(3)、`clearfat`、`zerosize`、`align`、`sizeof` | `// run` | 栈对象归零、对齐 |
| Walk 定序 / 脱糖 | `reorder*`、`switch*`(7)、`range*`(5)、`defer*`(5)、`closure*`(8)、`append*`、`copy*`、`make*`、`map*`、`chan*`、`select` | `// run` | 求值顺序、降糖语义 |
| 常量 / 算术 | `const*`(9)、`rotate*`(5)、`shift*`(3)、`mergemul`、`strength`、`divmod`、`divide`、`zerodivide`、`floatcmp`、`bigalg` | `// run` | 强度削减、常量传播 |
| 内建 / intrinsic | `intrinsic.go`、`intrinsic.dir/`、`intrinsic_atomic.go`、`atomicload`、`unsafebuiltins`、`simd*` | `// run` | 内建函数被识别为指令 |
| 反射 / 元数据 | `reflectmethod*`(8)、`convT2X`、`genmeth*` | `// run` | 方法集、itab |
| 链接 / 符号 | `linkname*`(8)、`linkobj`、`linkx*`、`linkmain*`、`asmhdr*` | `// rundir` | `//go:linkname` 等 |
| 调用约定 / ABI | `abi/`、`mainsig`、`nosplit`、`maymorestack`、`tailcall` | `// run` | 参数传递、栈分裂 |
| 调试信息 | `dwarf/` | `// run` | DWARF / 行号表 |
| PGO / 覆盖率 | `finprofiled.go`、`preprofile` | `// run` | 剖析引导优化 |

---

## 2. L2：`test/codegen/` 汇编断言测试

最贴近「优化是否真的生效」的一层，**改编译器优化后必跑**。

- 驱动：同属 testdir 的 `asmcheck` action（`testdir_test.go:723`）
- 说明：`test/codegen/README`
- 规模：87 个 `.go`，共 **1775 条架构断言**
- 架构分布（断言条数）：`arm64` 1275、`amd64` 1250、`386` 527、`ppc64x` 433、`loong64` 326、`riscv64` 278、`s390x` 230、`arm` 134、`wasm` 121、`ppc64le` 64、`ppc64` 61、`mips64` 27、`mips` 23

**断言语法**（写在注释里，正则匹配 `go tool compile -S` 的输出）：

```go
func Sqrt(x float64) float64 {
	// amd64:"SQRTSD"
	// arm64:"FSQRTD"
	return math.Sqrt(x)
}
```

规则：独占一行的注释匹配**紧随其后的第一条非注释语句**；行内注释匹配**本行**；同行可写多架构；`// arm64:` 与 `// arm64/bug1:` 等带后缀形式可指定变体。

**默认行为**：只跑宿主 `GOARCH` 且仅 `GOOS=linux`。全架构需加 `-all_codegen`。

**文件主题族**：`arithmetic` `atomics` `bitfield` `bits` `bmi` `bool` `clobberdead` `comparisons` `condmove` `constants` `copy` `deadstore` `divmod` `floats` `fuse` `generics` `ifaces` `known_bits` `logic` `mapaccess` `maps` `math` `mathbits` `memcombine` `memcse` `memops` `moveload` `multiply` `noextend` `race` `reflect_type` `regabi_regalloc` `retpoline` `rotate` `schedule` `select` `shift` `shortcircuit` `simd` `simd_arm64` `slices` `spills` `stack` `strings` `structs` `switch` `typeswitch` `unique` `unsafe` `writebarrier` `zerosize`，以及 20+ 个 `issue<N>.go` 回归。

---

## 3. L3：编译器级微测试 `src/cmd/compile/internal/test/`

- 43 个 `_test.go`，共 **30805 行**（编译器测试中最密的）
- 定位（`README` 原文）：*small tests and benchmarks of code generated by the compiler* —— 直接调用编译器 API 编译小片段，验证特定优化被应用且结果正确
- 基础设施：`test.go`（编译辅助函数）、`race.go`、`ssa_test.go`

按主题分类：

| 主题 | 文件 |
|---|---|
| 算术 / 常量折叠 | `arith_test.go`、`arithBoundary_test.go`、`arithConst_test.go`、`cmpConst_test.go`、`constFold_test.go`、`divconst_test.go`、`mulconst_test.go`、`truncconst_test.go`、`logic_test.go`、`shift_test.go`、`eq_test.go`、`compare_a*` |
| 内联 / intrinsic | `inl_test.go`、`inst_test.go`、`intrinsics_test.go`、`conditionalCmpConst_test.go` |
| PGO 专项 | `pgo_devirtualize_test.go`、`pgo_inl_test.go` |
| ABI | `abiutils_test.go`、`abiutilsaux_test.go`、`iface_test.go` |
| 内存操作 | `memcombine_test.go`、`memoverlap_test.go`、`moveload_test.go`、`move_test.go`、`zerorange_test.go` |
| 栈 / 局部变量 | `stack_test.go`、`locals_test.go`、`mergelocals_test.go`、`global_test.go`、`align_test.go` |
| 控制流 | `switch_test.go`、`float_test.go`、`math_test.go`、`value_test.go` |
| 构建 / 可复现 | `reproduciblebuilds_test.go`、`dep_test.go`、`lang_test.go`、`clobberdead_test.go` |
| issue 回归 | `issue50182`、`issue53888`、`issue57434`、`issue62407`、`issue71943` |
| 基准 | `bench_test.go` |
| 其他 | `free_test.go`、`fixedbugs_test.go`、`testdata/`（约 40 个 `_test.go` + `flowgraph_generator1.go`） |

---

## 4. L4：分阶段包的单元测试 `src/cmd/compile/internal/<pkg>/`

| 包（编译阶段） | 测试文件数 | 测试代码行数 |
|---|---|---|
| `ssa/`（通用 SSA + 后端） | 36 | 8728 |
| `types2/`（类型检查） | 28 | 8548 |
| `syntax/`（词法/语法） | 8 | 2131 |
| `rangefunc/` | 1 | 2206 |
| `ssagen/`（IR→SSA） | 1 | 1436 |
| `importer/` | 1 | 790 |
| `abt/` | 1 | 700 |
| `dwarfgen/`（调试信息） | 2 | 633 |
| `liveness/`（活性分析） | 1 | 527 |
| `amd64/`（后端） | 3 | 504 |
| `loopvar/` | 1 | 443 |
| `ir/`（编译器 AST） | 4 | 269 |
| `logopt/` | 1 | 250 |
| `devirtualize/` | 1 | 219 |
| `types/`（编译器类型） | 3 | 187 |
| `reflectdata/` | 1 | 147 |
| `base/` | 1 | 140 |
| `noder/`（noding） | 1 | 122 |
| `compare/` | 1 | 101 |
| `typecheck/` | 1 | 31 |

> 大部分包（`escape/` `inline/` `walk/` `gc/` 等）**没有单元测试**——它们的正确性靠 L1/L2 的端到端测试覆盖。这是有意设计：这些 pass 的输出很难在小范围内断言，必须看完整编译结果。

`ssa/testdata/` 是独立的一类，用于**调试器源码级步进验证**：

- 程序：`hist.go`、`scopes.go`、`i22558.go`、`infloop.go`、`convertline.go`、`pushback.go`、`fma.go`、`sayhi.go`、`i74576a/b/c.go`、`b53456.go`、`inline-dump.go`
- 期望输出：14 个 `.nexts` 文件，命名规则 `*.gdb-dbg.nexts` / `*.dlv-opt.nexts`（GDB / Delve × 调试版 / 优化版）
- 验证点：优化后行号映射仍然正确 —— **这是优化 pass 与调试信息交叉验证的独有手段**

---

## 5. L5：编译器 CLI 脚本测试

`src/cmd/compile/testdata/script/`，testscript（`.txt`）格式，由 `src/cmd/compile/script_test.go` 驱动：

`README`、`script_test_basics.txt`、`closure_name.txt`、`dwarf5_gen_assembly_and_go.txt`、`embedbad.txt`、`issue70173.txt`、`issue73947.txt`、`issue75461.txt`、`issue77033.txt`、`issue80258.txt`

适合测「编译器命令行的行为」——标志解析、`-d` 输出、错误退出码、生成汇编与 Go 文件等。

---

## 6. 相邻组件的测试

| 组件 | 位置 | 规模 / 内容 |
|---|---|---|
| 汇编器 | `src/cmd/asm/internal/asm/testdata/*.s` | 33 个 `.s`，按架构（`amd64enc.s`、`arm64.s`、`riscv64.s`…）+ 期望输出 |
| 机器码后端 | `src/cmd/internal/obj/*_test.go` | `line_test.go`、`objfile_test.go`、`sizeof_test.go` |
| 目标文件格式 | `src/cmd/internal/goobj/` | `objfile` 编解码 |
| 链接器 | `src/cmd/link/internal/ld/*_test.go` | 13 个：`deadcode`、`dwarf`、`elf`、`macho`、`stackcheck`、`issue33808`、`nooptcgolink`… |
| 标准库类型检查器 | `src/go/types/*_test.go` | **35 个**，是 `types2` 的对齐参照，也最适合入门 |
| 标准库语法 | `src/go/parser/`、`src/go/scanner/` | 与 `syntax` 包对照 |
| SSA 规则生成 | `src/cmd/compile/internal/ssa/_gen/` | `*.rules` 变更后需 `go generate` |
| IR 编解码 | `src/internal/pkgbits/` | Unified IR 序列化 |

---

## 7. 运行方式

```sh
# 全部端到端测试（all.bash 的一部分）
../bin/go test cmd/internal/testdir

# 单个文件
../bin/go test cmd/internal/testdir -run='Test/escape_slice.go'

# 一组文件（正则）
../bin/go test cmd/internal/testdir -run='Test/(inline|escape)'

# 全架构 codegen（改编译器优化后强烈推荐）
../bin/go test cmd/internal/testdir -run='Test/codegen' -all_codegen -v

# 只跑 codegen 中的某主题
../bin/go test cmd/internal/testdir -run='Test/codegen/math' -all_codegen

# 忽略 skip 列表与 build tag，强跑一切
../bin/go test cmd/internal/testdir -run_skips -f

# 用编译器实际输出更新 // ERROR 期望文本
../bin/go test cmd/internal/testdir -update_errors

# 交叉编译目标平台测试
../bin/go test cmd/internal/testdir -target=linux/arm64

# 编译器包内测试
../bin/go test cmd/compile/internal/test
../bin/go test cmd/compile/internal/ssa
../bin/go test cmd/compile/internal/types2
```

`testdir` 支持的完整标志（`testdir_test.go` 顶部）：`-all_codegen`、`-run_skips`、`-linkshared`、`-update_errors`、`-l`（runoutput 并发数）、`-f`（忽略 expected-failure 列表）、`-target`、`-shard`、`-shards`。

---

## 8. 定位技巧：想找某个 feature 的测试

| 目标 | 命令 |
|---|---|
| 某个 SSA pass 的测试 | `grep -rn 'd=ssa/<passname>' go_source_code/test/` |
| 某个架构的代码生成 | `grep -rn '// <arch>:"' go_source_code/test/codegen/` |
| 某条报错信息的来源 | `grep -rn 'ERROR ".*<片段>' go_source_code/test/` |
| 某个 issue 的回归 | `ls go_source_code/test/fixedbugs/issue<N>*.go` |
| 某内建函数是否被 intrinsic | `grep -rn '<builtin>(' go_source_code/test/codegen/ go_source_code/test/intrinsic*` |
| 某包的单元测试 | `ls go_source_code/src/cmd/compile/internal/<pkg>/*_test.go` |

---

## 9. 新增测试应该放哪

| 改了什么 | 测试落点 | 用什么指令 |
|---|---|---|
| 词法/语法/类型检查的报错 | `test/*.go` | `// errorcheck` |
| 编译能过但生成的代码行为错 | `test/<主题>.go` | `// run` |
| 运行时输出可预测的行为 | `test/*.go` + `*.out` | `// runoutput` |
| 优化 pass 的**决策**（内联/逃逸/devirt） | `test/<主题>.go` | `// errorcheck -m` / `// errorcheckwithauto` |
| 某个 SSA pass 的内部效果 | `test/<passname>.go` | `// errorcheck -d=ssa/<pass>/debug=N` |
| 生成的**汇编指令** | `test/codegen/<主题>.go` | `// <arch>:"<regexp>"` |
| 函数级正确性 + 基准 | `src/cmd/compile/internal/test/` | 普通 Go test |
| 某 pass 的数据结构/算法 | `src/cmd/compile/internal/<pkg>/` | 普通 Go test |
| 编译器命令行行为 | `src/cmd/compile/testdata/script/*.txt` | testscript |
| 优化后的调试器步进 | `src/cmd/compile/internal/ssa/testdata/` | `*.gdb/dlv-*.nexts` |

---

## 10. 学习路径建议

1. **`src/go/types/*_test.go`**（35 个）—— 类型检查器测试最易读，先建立手感
2. **`test/escape*.go` + `test/inline*.go`** —— 用 `-m` 诊断理解优化决策，配合 `escape_param.go`、`inline.go` 逐行读 `// ERROR` 注释
3. **`test/prove*.go`、`checkbce.go`、`phiopt.go`** —— 学会用 `-d=ssa/<pass>/debug=N` 观察 pass 内部
4. **`test/codegen/`** —— 从 `arithmetic.go`、`bits.go` 开始，看优化如何落到具体指令
5. **`src/cmd/compile/internal/ssa/*_test.go` + `ssa/testdata/`** —— 进入 SSA 内部
6. **`test/fixedbugs/`** —— 需要具体案例时按 issue 号检索，是最真实的 bug 素材库
