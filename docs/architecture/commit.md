# 提交规约（commit contract）

长期脏树是正常协作状态。提交只许按死清单路径走 `git commit --only`。合入门执行机器提交；工头可以用一句固定握手把有限的 commit/push 写进小工 brief。合入闸见 [`land.md`](land.md)；派单自动追加条款见 [`dispatch.md`](dispatch.md)。

状态标签见 [`FOR-AI.md`](../../FOR-AI.md)。合入 `--only` **Does**。创建侧「握手无死清单即拒」**Recommended / not implemented**。

**死清单（一份定义，与合入门相同）：** 允许暂存或提交的路径。**清单 ⊆ `allowed_paths`，否则拒。** 空或 `.` 在合入侧不是「不限制」。

## 解决什么问题

`git add .`、`git commit -a`、stash、整树 checkout/reset/restore/clean 会把别人还没提交的改动带走或抹掉。口头「可以提交」没有路径边界，下一窗也无法复核。提交后若用活的 `HEAD` 当「我刚写下的 sha」，别人一提交，你的核对就指到别人的 commit。

## 交给谁（人 / AI / 机器）

| 谁 | 做什么 | 不做什么 |
|---|---|---|
| 人 | 不必记 git 旗标 | 自己在主树 stash/reset 给小工腾地方 |
| 工头 AI | 默认不授权提交；要授权必须写握手四字 **加** 死清单（通常即本单 `allowed_paths`） | 只写「可以 commit」不写路径；授权部署/重启 |
| 工人 AI | 仅当 brief 放行且清单非空时，按死清单提交/推当前分支 | 整树命令；`git pull --rebase`；远端领先仍硬推 |
| 机器 | 合入提交只用记录里的路径；失败只清本单暂存 | 整树 undo「试一下再恢复」 |

## 最小版怎么做

1. 合入记录保存死清单（来自封存文件集，且必须 ⊆ 工单 `allowed_paths`）。
2. 合入提交：`git commit --only -m <msg> -- <清单路径...>`。清单外不暂存、不提交。
3. 小工 brief **默认禁止** commit/push/deploy/restart。只有工单出现固定握手句、并且带死清单，才把禁止改成「只许清单」。
4. 工单正文一旦提到提交，机器再追加死清单做法和整树禁令，不靠小工记手册。
5. 失败：只恢复本单路径的暂存/工作区，报原因。不要 `reset --hard`、不要 stash。
6. 远端已领先：停工报告，不要 `git pull --rebase`。
7. 核对用**自己那次 commit 的 sha**（命令刚成功时记下的），不要过一会儿再读 `HEAD`。

## 我们现在的版本（2026-09）

### 死清单提交（机器合入）— **Does**

- 合入在所有闸通过后执行：
  `git commit --only -m "<ticket> <task_id> …" -- <files>`
  空暂存（全是 no-op）才加 `--allow-empty`。
- `--only` 的作用：主树其它已暂存/未暂存文件进不了这次提交。
- 死清单来自封存记录的 added/modified/deleted，并已与 `allowed_paths` 比对：**不是子集即拒**。
- 暂存集必须正好等于清单，否则当冲突并清理。

### 禁整树命令 — **Does**

合入失败清理是清单级的：reset 清单路径，对已有路径 checkout 清单内，对新增路径 unlink。明确不是整树 checkout。

小工侧同一套禁令写进工单，靠合入门而不是自觉守主树。测试里禁止用 stash/checkout/reset/restore/clean 做反例，改拷到临时目录或 monkeypatch。

### 远端领先就停工

- **Does。** 追加到工单的固定条款：不许 `git pull --rebase`，远端领先就报告停工。
- 合入后的 push 失败只记失败，**不回滚**已合入提交，也不 rebase。
- 合入前是否先 fetch 比较远端：**Recommended** 做成硬闸（合入路径未做「领先则拒 commit」）。

### 用自己的 sha 核对，不是活 HEAD — **Does**（合入侧）

- 合入成功立刻记下这次提交的 sha，写入记录。
- 再次合入发现已是已合入：返回**记录里的** sha，不再读当前 `HEAD`。
- 小工自己提交时：brief 尚未把「记下 commit 输出的 sha」写成硬条款。**Recommended** 提交脚本把返回的 sha 写进报告，禁止事后用 `HEAD` 冒充。

### 提交握手

- 固定四字（必须这八个汉字+英文，不能意译）：`本批允许 commit/push`。
- **Does。** 默认 brief 禁止 commit/push/deploy/restart。有握手才换成「只许死清单路径；仍禁止部署/重启」。
- 英文允许句且同句无否定、全文无禁止标记时，创建时在完成条件前面补上中文握手，给后续检测用。已有中文握手则不动。
- **Recommended / not implemented。** 握手四字只切换 brief 措辞。代码不检查「四字旁边有没有路径列表」。合入死清单始终来自 `allowed_paths` + 封存文件。无死清单的握手不是授权——创建侧尚未硬拒这种组合。建议补闸：出现握手且范围整仓则拒。
- 无握手：deny 措辞与加握手功能之前字节级相同，避免无故改前缀。
- 部署/重启永不在握手范围内。操作能力不是授权。

### 条款自动追加 — **Does**

工单 goal/criteria 出现 `commit` 或 `提交`（大小写不敏感）时，若尚未有标记，把整段提交规约接到 goal 末尾：

只许 `git commit --only -m <msg> -- <清单路径...>`，清单就是本单 `allowed_paths`，且必须 ⊆ `allowed_paths`；禁止 `git add -A`、`git add .`、`git commit -a`、`git stash`、`git checkout -- .`、`git reset --hard`；不许 `git pull --rebase`，远端领先就报告停工。

系统自己追加的这段里的 `git commit --only` **不算**工头下的提交令（避免误触发「某沙箱后端不许提交」等规则）。

每份小工 brief 末尾还有是否允许 commit/push 的句子，以及报告必须写在哪（最终回复里，或不另建报告文件）。

写不了 `.git` 的沙箱后端：工单若像在要求 `git commit`，创建即拒，改派能写 git 的后端。

## 必须由代码强制的规矩

1. 清单 ⊆ `allowed_paths`，否则拒。清单外的文件不暂存、不提交。
2. 失败只清理**这一次**清单路径的暂存/残留，不跑整树 undo。
3. 默认 brief 禁止 commit/push/deploy/restart。
4. 工单提到提交，必须由代码追加死清单做法，不靠记忆。

**Recommended / not implemented：** 握手句没有死清单，不应视为授权（创建侧尚未硬拒；合入侧靠 ⊆ `allowed_paths`）。

## 常见坑与我们怎么补的

1. **脏树是常态，整树 add 会吞别人的文件。** 补：合入只用 `--only` + 记录路径；brief 点名禁止 `add -A` / `commit -a` / stash / 整树 reset。
2. **「可以提交」没有路径。** 补：固定握手句；合入仍按 `allowed_paths`。**Recommended** 握手+整仓范围在创建硬拒。
3. **提交失败后 `reset --hard` 试恢复。** 别人的未提交改动没了。补：只 reset/checkout 清单路径；测试禁令写进所有后端 brief。
4. **用 HEAD 当「我刚提交的 sha」。** 并行提交后 HEAD 已变。补：合入把 sha 写进记录，幂等重入读记录。小工侧建议同样记下命令返回的 sha。
5. **合入页把空清单当不限制，提交页要求子集。** 补：两页同一句——清单 ⊆ `allowed_paths`，否则拒。
