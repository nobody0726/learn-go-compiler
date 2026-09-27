# Rust 重写 Go 1.27.1 编译器开发日志

本日志服务于 [`rust_go_compiler_rewrite_plan.md`](../rust_go_compiler_rewrite_plan.md)。每次实现任务完成后追加一条，保留失败测试和实际命令，不能只写结论。

## 2026-09-26 / 设计基线

- 目标：建立从 Go 1.27.1 `cmd/compile` 到 Rust 重写项目的架构约束、阶段门、TDD 测试矩阵和教学文档协议。
- 依据：`go_source_code/src/cmd/compile/README.md`、`go_source_code/src/cmd/internal/testdir/testdir_test.go`、`doc/go_compiler_tests.md`、`doc/go_book_mapping.md`、`doc/go_layout.md`。
- 结果：形成 [`rust_go_compiler_architecture.md`](../rust_go_compiler_architecture.md) 和 [`rust_go_compiler_rewrite_plan.md`](../rust_go_compiler_rewrite_plan.md)。
- 关键决策：先重写 `cmd/compile`，以现有 Go assembler/linker/runtime 作为兼容边界；先 amd64 无优化端到端，再扩展优化和目标架构。
- 未解决风险：Go 内部 object/export/ABI contract 需要在实现阶段继续以源码、链接测试和对象检查确认。

## 2026-09-26 / 纵向里程碑重排

- 目标：把原先按前端到后端顺序排的任务，改成 M0-M8 每门都有可执行 Go 程序的纵向闭环，并用横向能力矩阵补足语义、IR/后端、ABI/runtime/包、平台/测试、性能/教学。
- 依据：`go_source_code/src/cmd/compile/README.md`、`go_source_code/src/cmd/compile/abi-internal.md:14`、`doc/go_compiler_tests.md`。
- 关键决策：M0-M2 的 shim 是隔离实验边界；M3 起以 Go ABI 和真实对象格式作为互操作门。后端由 Rust 手写，Go linker/runtime 是验收依赖。Rust 编译器不做 Go 三阶段自举。
- RED/GREEN：本条仅修改设计和计划，尚无 Rust 工程或实现测试，不记录虚构的执行结果。
- 环境观察：本机 `go version` 为 `go1.24.5 darwin/arm64`；与 `go_source_code/VERSION` 的 `go1.27.1` 不符，不能用于本计划的 reference 差分门。
- 未解决风险：Go 1.27.1 参考工具链可用性、对象/export 格式、GC 元数据与多平台执行环境。
- 下一步：按 M0.1/M0.2 建立工程与首个失败测试，然后实现最小可运行闭环。

## 2026-09-26 / 覆盖与教学任务审计

- 目标：回答“是否已覆盖全部 Go 功能和官方测试”，并让每条测试、每个教学记录都有明确任务归属。
- 依据：`go_source_code/src/cmd/internal/testdir/testdir_test.go:74` `dirs`（`:73` 是 TODO 注释，勿抄）、`:170` `goFiles`、`go_source_code/src/cmd/compile/script_test.go:47`、`doc/go_compiler_tests.md` 与只读源码目录盘点。
- 发现：`test/` 约 3400 个 `.go` 是文件数而非独立测试数；`test/codegen/` 约 87 个 `.go` 属其子集。`src/cmd/compile/internal/` 共 177 个 `_test.go`，其中 `internal/test/` 有 75 个（直属 43 个），其他包 102 个；`inline/inlheur/` 的 5 个文件也须纳入。编译器 CLI 脚本有 9 个 `.txt`。这些数只用于检错，实际清单须由 runner 语义和源码摘要生成。
- 决策：B0.1 建功能库存，B0.2 建测试/子测试/断言/依赖资产库存；每条 ID 有主任务和平台，M0-M7 逐步解锁，M8 双向差集与全量执行审计。L1/L2/L5 原样复用 Go 输入并适配 harness；L3/L4 的白盒断言移植意图到 Rust，保留 ID 映射。相邻工具链测试另列边界库存，不把原 Go `go test` 通过计为 Rust 通过。
- 教学拆分：每个功能任务派生 `Mx.y-T`，分别保存原理、代码映射、正反例、真实 RED/GREEN、IR/汇编、性能和风险；里程碑教学页再整合审稿。
- RED/GREEN：此次只有计划与架构文档修订；Rust 工程、官方测试清单和参考版本测试尚未执行，不能记录为已通过。
- 未解决风险：Go 1.27.1 参考工具链、多目标执行环境及动态生成的子测试尚待取得可复验证据；有 `blocked`、`not-run` 或未解析发现项时不得宣布 1:1 完成。
- 下一步：先实现 B0.1/B0.2 的清单生成与故意缺项的失败测试，再开始 M0 的实现任务。

## 2026-09-26 / 里程碑与 Go 源码关系细化

- 目标：把阶段级引用细化为功能任务与官方函数/规则的对应关系，并支持从源码反查任务。
- 依据：`doc/go_book_mapping.md`、`go_source_code/src/cmd/compile/README.md`，以及 syntax/types2/noder/walk/ssagen/ssa/abi/liveness/obj 等包的实际符号定义。
- 结果：在实施计划加入 M0-M8 任务级对照表，逐行列出官方入口、Rust 责任、理论、本门切片及后续深化；另列反向查询表。
- 决策：关系为多对多；不能按整个文件宣布完成。清单新增 Go 符号/分支或规则、Rust 符号、首次/完成任务、测试与证据字段；区分重写、原理参考和工具链复用。编译器调用的 obj/goobj 编码与对象 writer 仍属 Rust 实现范围；linker/runtime 继续复用。
- 验证：检查新增完整路径源码锚点的文件存在性和行号范围，核对 21 个实现/验收任务 ID 均被对照表包含；关键函数通过源码符号搜索核对。文档状态仍为计划，未运行 Rust 编译器测试。
- 未解决风险：泛型字典、目标规则和大函数内分支仍须随 B0.1 逐能力进一步枚举；当前映射是任务级阅读与责任基线，不是全源码已覆盖的证明。
- 下一步：B0.1 将各任务的能力切片固化到清单；实际实现后由每个 `-T` 子任务补真实 Rust 代码位置和测试证据。

## 后续条目模板

```markdown
## YYYY-MM-DD / Task N
- 目标：
- 依据：
- RED：
- GREEN：
- 关键决策：
- 性能数据：
- 未解决风险：
- 下一步：
```
