# 候选开发计划（auto-clustered from A/B/C）

> ⚠️ **这是候选骨架，不是已验证的计划。**
> 每个 atom 的里程碑归属是按关键词自动分配的，未经人工审核。
> 要变成「零遗漏」计划，需要：
> 1. 人工审核每个 atom 的里程碑归属
> 2. 填充 `features.toml`（每条 feature 给出 A/B/C 三侧锚点 + 里程碑 + target_dim）
> 3. 实现闸三（变异注入差分）和闸四（负测试差分）
> 4. 写一个能通过测试的 Rust 编译器

> 基线：go1.27.1  |  A(spec)=125  B(impl)=183  C(test)=2738  features=2  claimed=8

## 里程碑总览

| 里程碑 | 主题 | spec | impl | test | 已认领 | 未认领 |
|---|---|---:|---:|---:|---:|---:|
| M0 | 词法分析 (Lexer / Scanner) | 15 | 2 | 19 | 1 | 35 |
| M1 | 类型与常量 (Types & Constants) | 22 | 0 | 0 | 0 | 22 |
| M2 | 声明与作用域 (Declarations & Scope) | 15 | 2 | 307 | 1 | 323 |
| M3 | 表达式 (Expressions) | 24 | 0 | 0 | 1 | 23 |
| M4 | 语句 (Statements) | 19 | 0 | 19 | 0 | 38 |
| M5 | 内建函数与包 (Built-ins & Packages) | 17 | 9 | 10 | 0 | 36 |
| M6 | 运行时与初始化 (Runtime & Init) | 9 | 0 | 1855 | 0 | 1864 |
| M7 | 中端与驱动 (SSA, Inline, Escape, Driver) | 0 | 75 | 128 | 1 | 202 |
| M7.2-T1 | amd64 后端 (必做) | 0 | 14 | 3 | 2 | 15 |
| M7.2-T2 | arm64 后端 (应做) | 0 | 17 | 0 | 0 | 17 |
| M7.2-T3 | 其余 9 架构 (scope-excluded) | 0 | 64 | 0 | 0 | 64 |
| N/A | 叙述性章节 (非编译器行为, claimable=false 候选) | 4 | 0 | 0 | 0 | 4 |
| M0-M5 | 混合 (test/ 根目录, 需逐文件 triage) | 0 | 0 | 396 | 2 | 394 |
| M? | 未分类 (需 triage) | 0 | 0 | 1 | 0 | 1 |

## 逐里程碑明细

### M0: 词法分析 (Lexer / Scanner)

**spec 条款 (15)**

- ○ `spec:Source_code_representation` — Source code representation
- ○ `spec:Characters` — Characters
- ○ `spec:Letters_and_digits` — Letters and digits
- ○ `spec:Lexical_elements` — Lexical elements
- ✓ `spec:Comments` — Comments
- ○ `spec:Tokens` — Tokens
- ○ `spec:Semicolons` — Semicolons
- ○ `spec:Identifiers` — Identifiers
- ○ `spec:Keywords` — Keywords
- ○ `spec:Operators_and_punctuation` — Operators and punctuation
- ○ `spec:Integer_literals` — Integer literals
- ○ `spec:Floating-point_literals` — Floating-point literals
- ○ `spec:Imaginary_literals` — Imaginary literals
- ○ `spec:Rune_literals` — Rune literals
- ○ `spec:String_literals` — String literals

**impl 原子 (2)**

- pragma (1):
  - ○ `pragma:generate`
- flag (1):
  - ○ `flag:Lang` — Go language version source code expects

**测试 (19)**

- `L?:syntax` — 19 个（已认领 0）

*候选 feature_ids：35 个未认领 atom 待归属（人工填写 `features.toml`）*

### M1: 类型与常量 (Types & Constants)

**spec 条款 (22)**

- ○ `spec:Constants` — Constants
- ○ `spec:Variables` — Variables
- ○ `spec:Types` — Types
- ○ `spec:Boolean_types` — Boolean types
- ○ `spec:Numeric_types` — Numeric types
- ○ `spec:String_types` — String types
- ○ `spec:Array_types` — Array types
- ○ `spec:Slice_types` — Slice types
- ○ `spec:Struct_types` — Struct types
- ○ `spec:Pointer_types` — Pointer types
- ○ `spec:Function_types` — Function types
- ○ `spec:Interface_types` — Interface types
- ○ `spec:Map_types` — Map types
- ○ `spec:Channel_types` — Channel types
- ○ `spec:Properties_of_types_and_values` — Properties of types and values
- ○ `spec:Representation_of_values` — Representation of values
- ○ `spec:Underlying_types` — Underlying types
- ○ `spec:Type_identity` — Type identity
- ○ `spec:Assignability` — Assignability
- ○ `spec:Representability` — Representability
- ○ `spec:Method_sets` — Method sets
- ○ `spec:Type_unification_rules` — Type unification rules

*候选 feature_ids：22 个未认领 atom 待归属（人工填写 `features.toml`）*

### M2: 声明与作用域 (Declarations & Scope)

**spec 条款 (15)**

- ○ `spec:Blocks` — Blocks
- ○ `spec:Declarations_and_scope` — Declarations and scope
- ○ `spec:Label_scopes` — Label scopes
- ○ `spec:Blank_identifier` — Blank identifier
- ○ `spec:Predeclared_identifiers` — Predeclared identifiers
- ○ `spec:Exported_identifiers` — Exported identifiers
- ○ `spec:Uniqueness_of_identifiers` — Uniqueness of identifiers
- ○ `spec:Constant_declarations` — Constant declarations
- ○ `spec:Iota` — Iota
- ○ `spec:Type_declarations` — Type declarations
- ○ `spec:Type_parameter_declarations` — Type parameter declarations
- ○ `spec:Variable_declarations` — Variable declarations
- ○ `spec:Short_variable_declarations` — Short variable declarations
- ○ `spec:Function_declarations` — Function declarations
- ○ `spec:Method_declarations` — Method declarations

**impl 原子 (2)**

- pragma (2):
  - ✓ `pragma:build`
  - ○ `pragma:nointerface`

**测试 (307)**

- `L?:interface` — 21 个（已认领 0）
- `L?:typeparam` — 266 个（已认领 0）
- `L?:typeparam/mdempsky` — 20 个（已认领 0）

*候选 feature_ids：323 个未认领 atom 待归属（人工填写 `features.toml`）*

### M3: 表达式 (Expressions)

**spec 条款 (24)**

- ✓ `spec:Expressions` — Expressions
- ○ `spec:Operands` — Operands
- ○ `spec:Qualified_identifiers` — Qualified identifiers
- ○ `spec:Composite_literals` — Composite literals
- ○ `spec:Function_literals` — Function literals
- ○ `spec:Primary_expressions` — Primary expressions
- ○ `spec:Selectors` — Selectors
- ○ `spec:Method_expressions` — Method expressions
- ○ `spec:Method_values` — Method values
- ○ `spec:Index_expressions` — Index expressions
- ○ `spec:Slice_expressions` — Slice expressions
- ○ `spec:Type_assertions` — Type assertions
- ○ `spec:Calls` — Calls
- ○ `spec:Instantiations` — Instantiations
- ○ `spec:Type_inference` — Type inference
- ○ `spec:Operators` — Operators
- ○ `spec:Arithmetic_operators` — Arithmetic operators
- ○ `spec:Comparison_operators` — Comparison operators
- ○ `spec:Logical_operators` — Logical operators
- ○ `spec:Address_operators` — Address operators
- ○ `spec:Receive_operator` — Receive operator
- ○ `spec:Conversions` — Conversions
- ○ `spec:Constant_expressions` — Constant expressions
- ○ `spec:Order_of_evaluation` — Order of evaluation

*候选 feature_ids：23 个未认领 atom 待归属（人工填写 `features.toml`）*

### M4: 语句 (Statements)

**spec 条款 (19)**

- ○ `spec:Statements` — Statements
- ○ `spec:Terminating_statements` — Terminating statements
- ○ `spec:Empty_statements` — Empty statements
- ○ `spec:Labeled_statements` — Labeled statements
- ○ `spec:Expression_statements` — Expression statements
- ○ `spec:Send_statements` — Send statements
- ○ `spec:IncDec_statements` — IncDec statements
- ○ `spec:Assignment_statements` — Assignment statements
- ○ `spec:If_statements` — If statements
- ○ `spec:Switch_statements` — Switch statements
- ○ `spec:For_statements` — For statements
- ○ `spec:Go_statements` — Go statements
- ○ `spec:Select_statements` — Select statements
- ○ `spec:Return_statements` — Return statements
- ○ `spec:Break_statements` — Break statements
- ○ `spec:Continue_statements` — Continue statements
- ○ `spec:Goto_statements` — Goto statements
- ○ `spec:Fallthrough_statements` — Fallthrough statements
- ○ `spec:Defer_statements` — Defer statements

**测试 (19)**

- `L?:chan` — 19 个（已认领 0）

*候选 feature_ids：38 个未认领 atom 待归属（人工填写 `features.toml`）*

### M5: 内建函数与包 (Built-ins & Packages)

**spec 条款 (17)**

- ○ `spec:Built-in_functions` — Built-in functions
- ○ `spec:Appending_and_copying_slices` — Appending to and copying slices
- ○ `spec:Clear` — Clear
- ○ `spec:Close` — Close
- ○ `spec:Complex_numbers` — Manipulating complex numbers
- ○ `spec:Deletion_of_map_elements` — Deletion of map elements
- ○ `spec:Length_and_capacity` — Length and capacity
- ○ `spec:Making_slices_maps_and_channels` — Making slices, maps and channels
- ○ `spec:Min_and_max` — Min and max
- ○ `spec:Allocation` — Allocation
- ○ `spec:Handling_panics` — Handling panics
- ○ `spec:Bootstrapping` — Bootstrapping
- ○ `spec:Packages` — Packages
- ○ `spec:Source_file_organization` — Source file organization
- ○ `spec:Package_clause` — Package clause
- ○ `spec:Import_declarations` — Import declarations
- ○ `spec:An_example_package` — An example package

**impl 原子 (9)**

- pragma (9):
  - ○ `pragma:cgo_`
  - ○ `pragma:cgo_dynamic_linker`
  - ○ `pragma:cgo_import_dynamic`
  - ○ `pragma:cgo_import_static`
  - ○ `pragma:cgo_ldflag`
  - ○ `pragma:cgo_unsafe_args`
  - ○ `pragma:embed`
  - ○ `pragma:linkname`
  - ○ `pragma:linknamestd`

**测试 (10)**

- `L?:arenas` — 1 个（已认领 0）
- `L?:closure_name.txt` — 1 个（已认领 0）
- `L?:dwarf5_gen_assembly_and_go.txt` — 1 个（已认领 0）
- `L?:embedbad.txt` — 1 个（已认领 0）
- `L?:issue70173.txt` — 1 个（已认领 0）
- `L?:issue73947.txt` — 1 个（已认领 0）
- `L?:issue75461.txt` — 1 个（已认领 0）
- `L?:issue77033.txt` — 1 个（已认领 0）
- `L?:issue80258.txt` — 1 个（已认领 0）
- `L?:script_test_basics.txt` — 1 个（已认领 0）

*候选 feature_ids：36 个未认领 atom 待归属（人工填写 `features.toml`）*

### M6: 运行时与初始化 (Runtime & Init)

**spec 条款 (9)**

- ○ `spec:Program_initialization_and_execution` — Program initialization and execution
- ○ `spec:The_zero_value` — The zero value
- ○ `spec:Package_initialization` — Package initialization
- ○ `spec:Program_initialization` — Program initialization
- ○ `spec:Program_execution` — Program execution
- ○ `spec:Errors` — Errors
- ○ `spec:Run_time_panics` — Run-time panics
- ○ `spec:System_considerations` — System considerations
- ○ `spec:Size_and_alignment_guarantees` — Size and alignment guarantees

**测试 (1855)**

- `L?:fixedbugs` — 1854 个（已认领 0）
- `L?:internal/runtime/sys` — 1 个（已认领 0）

*候选 feature_ids：1864 个未认领 atom 待归属（人工填写 `features.toml`）*

### M7: 中端与驱动 (SSA, Inline, Escape, Driver)

**impl 原子 (75)**

- pragma (5):
  - ○ `pragma:noescape`
  - ○ `pragma:noinline`
  - ○ `pragma:uintptr`
  - ○ `pragma:uintptrescapes`
  - ○ `pragma:uintptrkeepalive`
- flag (65):
  - ○ `flag:B` — disable bounds checking
  - ○ `flag:C` — disable printing of columns in error messages
  - ○ `flag:D` — set relative `path` for local imports
  - ○ `flag:E` — debug symbol export
  - ○ `flag:I` — add `directory` to import search path
  - ○ `flag:K` — debug missing line numbers
  - ○ `flag:L` — also show actual source file names in error messages for pos
  - ○ `flag:N` — disable optimizations
  - ○ `flag:S` — print assembly listing
  - ○ `flag:W` — debug parse tree after type checking
  - ○ `flag:LowerC` — concurrency during compilation (1 means no concurrency)
  - ○ `flag:LowerD` — enable debugging settings; try -d help
  - ○ `flag:LowerE` — no limit on number of errors reported
  - ○ `flag:LowerH` — halt on error
  - ○ `flag:LowerJ` — debug runtime-initialized variables
  - ○ `flag:LowerL` — disable inlining
  - ○ `flag:LowerM` — print optimization decisions
  - ○ `flag:LowerO` — write output to `file`
  - ○ `flag:LowerP` — set expected package import `path`
  - ○ `flag:LowerR` — debug generated wrappers
  - ○ `flag:LowerT` — enable tracing for debugging the compiler
  - ○ `flag:LowerW` — debug type checking
  - ○ `flag:LowerU` — emit unsorted warnings/errors
  - ○ `flag:LowerV` — increase debug verbosity
  - ○ `flag:AsmHdr` — write assembly header to `file`
  - ○ `flag:ASan` — build code compatible with C/C++ address sanitizer
  - ○ `flag:Bench` — append benchmark times to `file`
  - ○ `flag:BlockProfile` — write block profile to `file`
  - ○ `flag:BuildID` — record `id` as the build id in the export metadata
  - ○ `flag:CPUProfile` — write cpu profile to `file`
  - ○ `flag:Complete` — compiling complete package (no C or assembly)
  - ○ `flag:ClobberDead` — clobber dead stack slots (for debugging)
  - ○ `flag:ClobberDeadReg` — clobber dead registers (for debugging)
  - ○ `flag:Dwarf` — generate DWARF symbols
  - ○ `flag:DwarfBASEntries` — use base address selection entries in DWARF
  - ○ `flag:DwarfLocationLists` — add location lists to DWARF in optimized mode
  - ○ `flag:Dynlink` — support references to Go symbols defined in other shared lib
  - ○ `flag:EmbedCfg` — read go:embed configuration from `file`
  - ○ `flag:Env` — add `definition` of the form key=value to environment
  - ○ `flag:GenDwarfInl` — generate DWARF inline info records
  - ○ `flag:GoVersion` — required version of the runtime
  - ○ `flag:ImportCfg` — read import configuration from `file`
  - ○ `flag:InstallSuffix` — set pkg directory `suffix`
  - ○ `flag:JSON` — version,file for JSON compiler/optimizer detail output
  - ○ `flag:LinkObj` — write linker-specific object to `file`
  - ○ `flag:LinkShared` — generate code that will be linked against Go shared librarie
  - ○ `flag:Live` — debug liveness analysis
  - ○ `flag:MSan` — build code compatible with C/C++ memory sanitizer
  - ○ `flag:MemProfile` — write memory profile to `file`
  - ○ `flag:MemProfileRate` — set runtime.MemProfileRate to `rate`
  - ○ `flag:MutexProfile` — write mutex profile to `file`
  - ○ `flag:NoLocalImports` — reject local (relative) imports
  - ○ `flag:CoverageCfg` — read coverage configuration from `file`
  - ○ `flag:Pack` — write to file.a instead of file.o
  - ○ `flag:Race` — enable race detector
  - ○ `flag:Shared` — generate code that can be linked into a shared library
  - ○ `flag:SmallFrames` — reduce the size limit for stack allocated objects
  - ○ `flag:Spectre` — enable spectre mitigations in `list` (all, index, ret)
  - ○ `flag:Std` — compiling standard library
  - ○ `flag:SymABIs` — read symbol ABIs from `file`
  - ○ `flag:TraceProfile` — write an execution trace to `file`
  - ○ `flag:TrimPath` — remove `prefix` from recorded source file paths
  - ○ `flag:WB` — enable write barrier
  - ○ `flag:PgoProfile` — read profile or pre-process profile from `file`
  - ○ `flag:ErrorURL` — print explanatory URL with error message if applicable
- rules (5):
  - ○ `rules:dec.rules` [pass=decompose-builtin, rules=47]
  - ○ `rules:dec64.rules` [pass=decompose-builtin, rules=118]
  - ○ `rules:divisible.rules` [pass=divisible, rules=20]
  - ○ `rules:divmod.rules` [pass=divmod, rules=29]
  - ○ `rules:generic.rules` [pass=opt, rules=1013]

**测试 (128)**

- `L?:abi` — 39 个（已认领 0）
- `L?:codegen` — 87 个（已认领 1）
- `L?:dwarf` — 2 个（已认领 0）

*候选 feature_ids：202 个未认领 atom 待归属（人工填写 `features.toml`）*

### M7.2-T1: amd64 后端 (必做)

**impl 原子 (14)**

- rules (4):
  - ✓ `rules:AMD64.rules` [pass=lower, rules=1154]
  - ○ `rules:AMD64latelower.rules` [pass=latelower, rules=6]
  - ○ `rules:AMD64splitload.rules` [pass=splitload, rules=21]
  - ○ `rules:simdAMD64.rules` [pass=simd-lower, rules=3619]
- obj (10):
  - ○ `obj:x86:a.out.go` [arch=x86, loc=426]
  - ○ `obj:x86:aenum.go` [arch=x86, loc=1611]
  - ○ `obj:x86:anames.go` [arch=x86, loc=1609]
  - ✓ `obj:x86:asm6.go` [arch=x86, loc=5431]
  - ○ `obj:x86:avx_optabs.go` [arch=x86, loc=4628]
  - ○ `obj:x86:evex.go` [arch=x86, loc=383]
  - ○ `obj:x86:list6.go` [arch=x86, loc=264]
  - ○ `obj:x86:obj6.go` [arch=x86, loc=1430]
  - ○ `obj:x86:seh.go` [arch=x86, loc=166]
  - ○ `obj:x86:ytab.go` [arch=x86, loc=44]

**测试 (3)**

- `L?:simd` — 3 个（已认领 0）

*候选 feature_ids：15 个未认领 atom 待归属（人工填写 `features.toml`）*

### M7.2-T2: arm64 后端 (应做)

**impl 原子 (17)**

- rules (3):
  - ○ `rules:ARM64.rules` [pass=lower, rules=1223]
  - ○ `rules:ARM64latelower.rules` [pass=latelower, rules=69]
  - ○ `rules:simdARM64.rules` [pass=simd-lower, rules=435]
- obj (14):
  - ○ `obj:arm64:a.out.go` [arch=arm64, loc=1513]
  - ○ `obj:arm64:anames.go` [arch=arm64, loc=653]
  - ○ `obj:arm64:anames7.go` [arch=arm64, loc=125]
  - ○ `obj:arm64:anames_gen.go` [arch=arm64, loc=708]
  - ○ `obj:arm64:asm7.go` [arch=arm64, loc=8795]
  - ○ `obj:arm64:doc.go` [arch=arm64, loc=296]
  - ○ `obj:arm64:encoding_gen.go` [arch=arm64, loc=3476]
  - ○ `obj:arm64:goops_gen.go` [arch=arm64, loc=705]
  - ○ `obj:arm64:inst.go` [arch=arm64, loc=896]
  - ○ `obj:arm64:inst_gen.go` [arch=arm64, loc=16111]
  - ○ `obj:arm64:list7.go` [arch=arm64, loc=329]
  - ○ `obj:arm64:obj7.go` [arch=arm64, loc=934]
  - ○ `obj:arm64:specialoperand_string.go` [arch=arm64, loc=176]
  - ○ `obj:arm64:sysRegEnc.go` [arch=arm64, loc=895]

*候选 feature_ids：17 个未认领 atom 待归属（人工填写 `features.toml`）*

### M7.2-T3: 其余 9 架构 (scope-excluded)

**impl 原子 (64)**

- pragma (2):
  - ○ `pragma:wasmexport`
  - ○ `pragma:wasmimport`
- rules (15):
  - ○ `rules:386.rules` [pass=lower, rules=577]
  - ○ `rules:386splitload.rules` [pass=splitload, rules=4]
  - ○ `rules:ARM.rules` [pass=lower, rules=1174]
  - ○ `rules:LOONG64.rules` [pass=lower, rules=665]
  - ○ `rules:LOONG64latelower.rules` [pass=latelower, rules=4]
  - ○ `rules:MIPS.rules` [pass=lower, rules=439]
  - ○ `rules:MIPS64.rules` [pass=lower, rules=467]
  - ○ `rules:MIPS64latelower.rules` [pass=latelower, rules=1]
  - ○ `rules:PPC64.rules` [pass=lower, rules=655]
  - ○ `rules:PPC64latelower.rules` [pass=latelower, rules=21]
  - ○ `rules:RISCV64.rules` [pass=lower, rules=530]
  - ○ `rules:RISCV64latelower.rules` [pass=latelower, rules=16]
  - ○ `rules:S390X.rules` [pass=lower, rules=703]
  - ○ `rules:Wasm.rules` [pass=lower, rules=288]
  - ○ `rules:simdWasm.rules` [pass=simd-lower, rules=296]
- obj (47):
  - ○ `obj:arm:a.out.go` [arch=arm, loc=412]
  - ○ `obj:arm:anames.go` [arch=arm, loc=146]
  - ○ `obj:arm:anames5.go` [arch=arm, loc=77]
  - ○ `obj:arm:asm5.go` [arch=arm, loc=3142]
  - ○ `obj:arm:list5.go` [arch=arm, loc=124]
  - ○ `obj:arm:obj5.go` [arch=arm, loc=748]
  - ○ `obj:loong64:anames.go` [arch=loong64, loc=817]
  - ○ `obj:loong64:asm.go` [arch=loong64, loc=3327]
  - ○ `obj:loong64:cnames.go` [arch=loong64, loc=79]
  - ○ `obj:loong64:cpu.go` [arch=loong64, loc=449]
  - ○ `obj:loong64:doc.go` [arch=loong64, loc=398]
  - ○ `obj:loong64:inst.go` [arch=loong64, loc=953]
  - ○ `obj:loong64:instOp.go` [arch=loong64, loc=1222]
  - ○ `obj:loong64:list.go` [arch=loong64, loc=113]
  - ○ `obj:loong64:obj.go` [arch=loong64, loc=738]
  - ○ `obj:mips:a.out.go` [arch=mips, loc=489]
  - ○ `obj:mips:anames.go` [arch=mips, loc=142]
  - ○ `obj:mips:anames0.go` [arch=mips, loc=44]
  - ○ `obj:mips:asm0.go` [arch=mips, loc=2139]
  - ○ `obj:mips:list0.go` [arch=mips, loc=83]
  - ○ `obj:mips:obj0.go` [arch=mips, loc=1455]
  - ○ `obj:ppc64:a.out.go` [arch=ppc64, loc=1098]
  - ○ `obj:ppc64:anames.go` [arch=ppc64, loc=628]
  - ○ `obj:ppc64:anames9.go` [arch=ppc64, loc=55]
  - ○ `obj:ppc64:asm9.go` [arch=ppc64, loc=5480]
  - ○ `obj:ppc64:asm9_gtables.go` [arch=ppc64, loc=1660]
  - ○ `obj:ppc64:doc.go` [arch=ppc64, loc=290]
  - ○ `obj:ppc64:list9.go` [arch=ppc64, loc=117]
  - ○ `obj:ppc64:obj9.go` [arch=ppc64, loc=1524]
  - ○ `obj:riscv:anames.go` [arch=riscv, loc=1001]
  - ○ `obj:riscv:cpu.go` [arch=riscv, loc=1804]
  - ○ `obj:riscv:doc.go` [arch=riscv, loc=344]
  - ○ `obj:riscv:inst.go` [arch=riscv, loc=2191]
  - ○ `obj:riscv:list.go` [arch=riscv, loc=68]
  - ○ `obj:riscv:obj.go` [arch=riscv, loc=5160]
  - ○ `obj:s390x:a.out.go` [arch=s390x, loc=1027]
  - ○ `obj:s390x:anames.go` [arch=s390x, loc=739]
  - ○ `obj:s390x:anamesz.go` [arch=s390x, loc=38]
  - ○ `obj:s390x:asmz.go` [arch=s390x, loc=5109]
  - ○ `obj:s390x:condition_code.go` [arch=s390x, loc=128]
  - ○ `obj:s390x:listz.go` [arch=s390x, loc=73]
  - ○ `obj:s390x:objz.go` [arch=s390x, loc=730]
  - ○ `obj:s390x:rotate.go` [arch=s390x, loc=117]
  - ○ `obj:s390x:vector.go` [arch=s390x, loc=1091]
  - ○ `obj:wasm:a.out.go` [arch=wasm, loc=643]
  - ○ `obj:wasm:anames.go` [arch=wasm, loc=493]
  - ○ `obj:wasm:wasmobj.go` [arch=wasm, loc=1529]

*候选 feature_ids：64 个未认领 atom 待归属（人工填写 `features.toml`）*

### N/A: 叙述性章节 (非编译器行为, claimable=false 候选)

**spec 条款 (4)**

- ○ `spec:Introduction` — Introduction
- ○ `spec:Notation` — Notation
- ○ `spec:Appendix` — Appendix
- ○ `spec:Language_versions` — Language versions

*候选 feature_ids：4 个未认领 atom 待归属（人工填写 `features.toml`）*

### M0-M5: 混合 (test/ 根目录, 需逐文件 triage)

**测试 (396)**

- `L?:.` — 356 个（已认领 2）
- `L?:ken` — 40 个（已认领 0）

*候选 feature_ids：394 个未认领 atom 待归属（人工填写 `features.toml`）*

### M?: 未分类 (需 triage)

**测试 (1)**

- `L?:internal/test` — 1 个（已认领 0）

*候选 feature_ids：1 个未认领 atom 待归属（人工填写 `features.toml`）*

## 当前认领状态（features.toml）

| feature_id | 里程碑 | target | status | spec | impl | test | neg | mut |
|---|---|---|---|---:|---:|---:|---:|:---:|
| `comments` | M0.1 | generic | partial | 1 | 1 | 1 | 1 | ✗ |
| `amd64-lower` | M7.2 | amd64/linux | verified | 1 | 2 | 1 | 1 | ✓ |

## 缺口分析（到「已验证计划」还差什么）

| 项 | 状态 |
|---|---|
| 闸一：机械生成三集 | ✅ 已实现（A=125, B=183, C=2738）|
| 闸二：三角 diff | ✅ 已实现（`triangle_diff.py`，3038 个未认领）|
| 闸三：变异注入差分 | ❌ 未实现（需写 harness：故意改 reference 一个行为，验证 harness 能抓到）|
| 闸四：负测试差分 | ❌ 未实现（需写 harness：reference 拒绝的代码 Rust 也必须拒绝）|
| features.toml 归属 | ⏳ 2 条（需人工填写到覆盖全部 atom）|
| Rust 编译器 | ❌ 不存在（`nobody0726/go-compiler-rust` 有 13 个 crate 骨架）|

**下一步建议**：
1. 从 M0（词法）开始逐条人工审核本骨架的 spec 归属，填写 `features.toml`
2. 对 M0 的每条 spec clause，找到对应的 B 集 impl atom（pragma/flag/包）和 C 集测试
3. 用 `validate_features.py` 校验每条 feature 四道闸（静态半边）
4. 扩 B 集加导出符号（当前只有 pragma/flag/rules/obj，缺 `defer`/`range` 改写等纯源码实现）
