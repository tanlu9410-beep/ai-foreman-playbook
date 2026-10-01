# FOR-AI.md — system entry for the builder AI

**Status: 2026-09.** Documentation-first public extract of a private construction process. This repository publishes documents only; build the code yourself following this file.

Your user handed you this repository because they want you to help them build a system like this: a foundation on which a non-coder can have AI construct and maintain their own software. One rule: humans do human work, AI does AI work, and everything that can be given to a machine is given to a machine.

## Operating premise

The human only talks to you through a chat front end; assume they will not run commands, edit files, read logs, or change configuration. You are their only hands. Everything — dispatch, review, bookkeeping, restarts, cross-window handoff — must work without the human touching the machine. Ask the human only about preferences, money, and go-live approval, in plain language, with your recommended choice.

You need a chat shell that can modify model input. Handoff injection, the drawer, and tag stripping all depend on it. A shell that only forwards the user’s last sentence cannot do those three.

The first resident process is built by the AI; the first go-live still needs a human nod. Being able to operate the machine is not authorization.

This repository assumes you already run somewhere you can act (for example a server with a coding agent) and your user already works with you. It is about how to work together, not how to provision a server.

Reference stack (swap freely; the ideas stay): Python backend, SQLite, git repo as source of truth for progress (board, casefiles, standing docs), a process supervisor for the resident process, a tool-using coding agent for the foreman window.

Do not drop “restart needs a human nod” because the human (or you) can type commands. Operating ability is not authorization.

Humans forget. AI forgets and will claim work is done when it is not. So progress and rules live in files and in code. Whoever takes the next window can continue.

Do not invent private names, chat text, secrets, or server paths. Call foreman seats **Seat A / Seat B**. Claims below marked **Does** are implemented in the originating system (2026-09). Claims marked **Does, awaiting live test** are in the code but not yet proven on a real host with two seats boarding the same car. Claims marked **In progress** / **not implemented** are not finished; treat them as design, not as already-enforced behavior. Claims marked **Recommended** are advice, not current hard gates.

**Work-order terminal states** (one list, used everywhere): `completed` | `failed` | `expired` | `blocked` | `cancelled` | `late_rejected`. These are terminal. `blocked` does not return to `running` on the same task id.

Human-facing overview: [`README.md`](README.md). Pipeline detail: [`docs/architecture/overview.md`](docs/architecture/overview.md). If the main AI or the chat service is down, the human hands [`RESCUE.md`](RESCUE.md) to another model.

## 1. System overview

### Roles

| Role | Decides / does | Does not |
|---|---|---|
| **Human** | What they want, what they like, whether to spend money, whether to go live | Remember procedures; read patches unless they want to |
| **Foreman AI** | Understand, plan, split work, choose workers, accept or reject | Do the whole construction in the same turn when a worker exists; close a ticket on a verbal “done” |
| **Worker AI** | Implement inside a written contract | Choose product goals; commit outside the dead list; restart production |
| **Background machine** | Ledger, queue, gates, counters, reminders, patrol, handoff injection | Product judgment; owner authorization |
| **Rescue crew** (another vendor, e.g. GPT) | When the main AI or chat service is down: stop, revive or roll back safely, leave a record | Treat “process died, bring it back” as a go-live restart; change product direction while the house is on fire |

Go-live restart (shipping new code) needs a human nod — [`docs/architecture/restart.md`](docs/architecture/restart.md). Process-down revive is [`RESCUE.md`](RESCUE.md). They are not the same act.

### Parts (index)

1. Ticket board and casefile
2. Dispatch and worker selection by job type
3. Resident queue and claim
4. Isolated copy and land gate
5. Commit contract
6. Restart needs a human nod (carpooling **Does, awaiting live test**)
7. Multi-seat collaboration
8. Cross-window handoff (block, drawer, current mainline, system map, handbook)
9. Prefix changes and per-window freeze (**instruction-file freeze not implemented**; tool-catalog freeze **Does**)
10. Supervision layer
11. Rescue page (when the sitting AI is the one that died)

### Which parts depend on the queue

Skip the resident queue and you still have a board, a contract, and a land gate. You lose: create-only-enqueues (dispatch no longer dies when the foreman window sleeps), one-transaction claim with path locks and capacity, restart-in-progress pausing new claims, claimed-but-never-spawned returning to the queue, and the overdue sweep. Isolation, commit `--only`, and the restart nod can exist without a queue; they just have no one to pause.

| Part | Needs the queue? | If you skip the queue |
|---|---|---|
| Board + casefile | No | Still works |
| Dispatch contract + routing table | No | Foreman still writes the contract; selection can be a function call |
| Resident claim | **Is** the queue | Dispatch runs inside the foreman turn: timeouts, double-starts, death on sleep |
| Isolated copy + land | No | Workers can still build off-tree; nothing pauses claims during land |
| Commit `--only` | No | Land commit still uses the dead list |
| Restart nod + carpool | Partial | A single-file gate still works; claim-pause during restart does not |
| Multi-seat mutex | No | Create-time scan still works; see gaps below |
| Handoff / drawer / mainline | No | Next window still reads files |
| Prefix freeze | No | — |
| Supervision (pending-review list, salvage) | Partial | Ack still happens; “list running on next turn” needs the queue |

## 2. Parts

Each part answers four questions: problem / owner / minimum / rules the code must enforce.

### 2.1 Ticket board and casefile — **Does**

- **Problem.** If the only record is chat, the next window has no idea what is open, waiting, or already tried.
- **Owner.** Human sets priority and whether to drop a ticket. Foreman writes tickets and keeps status honest. Machine appends a casefile line when a work order reaches any terminal state.
- **Minimum.** One **no-delete** board (do not delete rows; status may be updated in place): id, source, date, category, content, status. One casefile per ticket that records what ran. **Recommended:** the foreman closes a ticket only with a durable evidence pointer (path, test name, or artifact id) — memory does not count.
- **Code must enforce.** Create of a construction order without a ticket id is refused. Worker completion is not ticket close. Terminal work orders append a casefile; a failed append is a visible failure, never a fake success. Duplicate task ids do not double-write.

**Gap (honest):** casefile write failure is fail-open: the terminal row stays, the missing line is visible if someone looks, and there is no alarm. Concurrent two-seat create can race the mutex (scan-then-insert, not one exclusive lock across seats). See §6.

See [`docs/architecture/ticket.md`](docs/architecture/ticket.md).

### 2.2 Dispatch and worker selection by job type — **Does** (routing table); some gates **Recommended** / **In progress**

- **Problem.** “Who should do this?” guessed in the moment sends paid work to a paused pool, or a write job to a read-only private-chat seat.
- **Owner.** Foreman writes the contract: goal, completion criteria, `task_kind`, `allowed_paths`, verify method. Machine picks a pool from a routing table (switchboard). Human authorizes spend when a pool requires it.
- **Minimum.** A validated table of pools and `task_kind` → ordered pool ids. Load with schema check; on a bad table, fall back to a last-good snapshot and warn; if neither is usable, refuse orders that depend on the table. Skip paused / unauthorized / exhausted / near-limit pools. Unknown or stale quota is not “full” and not “free capacity to grab.”
- **Routing table fields (meanings only).** Top-level: `version` (positive integer, bump on every edit); `pools` (list of worker pools); `task_kinds` (job type → ordered pool ids, fallback order). Each pool: `id` (pool name); `backend` (which worker engine); `model` (model id to call); `source_class` (how the pool is obtained); `billing` (how it is paid); `quota_windows` (which quota clocks apply); `needs_owner_ok` (human must authorize spend); `hard_readonly` (never send write jobs — **Recommended / not implemented** in the router today; write bounds currently rely on `mode` and the land gate); `memory_weight` (relative memory cost); `expires_at` (date or null); `status` (`active` / `paused` / `banned`); `reason` (required when status is not `active`).
- **Code must enforce.** Missing ticket id → refuse. `review_required=false` → refuse. Restart-shaped orders without an owner authorization quote → refuse. Paths are repo-relative.
- **In progress** (originating system is changing this): a write order missing a narrow `allowed_paths` **should be refused**. Do not treat empty as “no files.” Until that refuse lands, empty / `.` / `/` still means whole-repo — do not silently start without at least a warning.
- **Recommended:** missing completion criteria currently gets a placeholder; you may choose to refuse instead.

See [`docs/architecture/dispatch.md`](docs/architecture/dispatch.md). Example JSON: §5.

### 2.3 Resident queue and claim — **Does**; overdue sweep **Recommended**

- **Problem.** Dispatch that runs inside the foreman’s turn will time out, double-start, or die when the window sleeps.
- **Owner.** Machine. Foreman only creates the queued row and later reads status.
- **Minimum.** Orders land as `queued`. A resident consumer claims the oldest eligible row in one write transaction: count running, check path locks / capacity, then `queued → running`. A supervisor keeps that consumer alive. Claimed-but-never-spawned rows return to the queue; spawned process gone → `failed`.
- **Code must enforce.** Capacity check and status update share the same write transaction. Restart-in-progress pauses new claims. Terminal states are terminal (`blocked` does not return to `running` on the same task id).
- **Does:** a worker hitting its own time limit is marked `expired` by the adapter.
- **Recommended / not implemented:** a resident loop that sweeps overdue queued/running rows (`expire_due`). Do not document that sweep as a live gate.
- **Does, costs money:** auto-continue opens a **new** paid work order (same backend / scope / ticket) when a worker stops on turn or wall-clock limit. A second auto-continue that also exhausts alerts the foreman to split the job; there is no third automatic open. Tell the human it will spend again.

**Gap (honest):** crash after claim and before spawn is recovered (row returns to `queued`). Crash in the window between “eligible” and the write transaction can still double-start. Fail-open paths do not alarm.

See [`docs/architecture/dispatch.md`](docs/architecture/dispatch.md).

### 2.4 Isolated copy and land gate — **Does**

- **Problem.** Building on the live tree overwrites the human’s uncommitted work and mixes two jobs. “Clean the tree first” is how you lose someone else’s patch.
- **Owner.** Machine creates, seals, and lands. Foreman reviews the patch. Human does not clean the main tree to make a worker comfortable.
- **Minimum.** Isolated git worktree from current `HEAD`. Record `base_head` and approved untracked dependency digests. Do not bind runtime data or credential files. Seal added/modified/deleted (including binary) plus a patch digest. Land only from that seal.
- **Code must enforce.** If the main tree already has uncommitted changes on this order’s `allowed_paths`, refuse to create the isolated order. Land: listed files ⊆ `allowed_paths`, else refuse; lock; `git apply --check --index` then apply; Python compile; import of agreed packages (skip process-entry modules); tool-catalog tests when tool-surface paths are hit; secret-shape scan that returns locations only, never matched text. Any miss writes a state and leaves the patch in isolation. If listed files became dirty on the main tree since seal, stop — do not cover someone else’s work.

**Isolated copy is not a sandbox.** The worker and the main tree run as the **same system user**. Land-gate import checks **execute the code being merged**. Isolation protects a dirty tree and parallel jobs; it does not jail the worker, drop privileges, or stop a malicious or buggy import from touching the host. Write that boundary into the worker brief.

See [`docs/architecture/worktree.md`](docs/architecture/worktree.md) and [`docs/architecture/land.md`](docs/architecture/land.md).

### 2.5 Commit contract — **Does** (land `--only`); handshake dead-list refuse **Recommended**

- **Problem.** A long-lived dirty tree is the normal collaboration state. `git add .`, stash, reset, restore, or clean will take or erase other people’s work.
- **Owner.** Machine executes land commits. Foreman may grant worker commit/push only with an explicit handshake plus a dead path list. Human never has to remember git flags.
- **Minimum.** Land record stores the dead list. Land commit is `git commit --only -- <listed paths>`. Worker briefs always say whether commit/push is allowed; mentioning commit appends the dead-list method.
- **Dead list (one definition).** The paths that may be staged or committed. **Listed files ⊆ `allowed_paths`, else refuse.** Same rule at land and at worker commit. Empty or `.` is not “unrestricted” at land time.
- **Code must enforce.** Nothing outside the list is staged or committed. Failure cleans this attempt’s staging and reports; it does not run whole-tree undo. Default briefs deny commit/push/deploy/restart.
- **Recommended / not implemented:** a handshake phrase with no dead list is not a grant — create should refuse that combination. Today the four-word handshake only switches brief wording; land still enforces ⊆ `allowed_paths`. Treat “handshake without a list” as **Recommended**, not as a current hard refuse at create.

See [`docs/architecture/commit.md`](docs/architecture/commit.md).

### 2.6 Restart needs a human nod — carpooling **Does, awaiting live test**

- **Problem.** Restart changes running code. Verbal “just restart it” in an old window is not authorization. Stacking restarts one-by-one burns the human’s attention and can ship extra commits silently.
- **Owner.** Human nods. Foreman requests. Machine queues, waits for idle, executes, writes a receipt.
- **Minimum that already Does:** enqueue requires an owner quote checked against a recent authorization window (default suggestion: **30 minutes**; older quotes are not authorization). Missing / mismatch / negation → refuse. Execution waits for idle. Receipt lists commits that actually went live, including piggybacked ones. Public text records whether authorization was checked, not the quote body. A pending/restarting gate pauses new construction claims. Multiple independent restart requests board one “car,” departing only when every passenger is ready; overflow goes to the next car.
- **Awaiting live test (do not claim as proven):** two seats boarding the same car at once on a real host. Unit tests exist; do not tell the user the two-seat live path is proven.
- **Code must enforce (the Does subset).** No owner quote → no enqueue. Quote outside the authorization window → refuse. Receipt is computed from the actual `HEAD` delta at execute time, not guessed at enqueue.

**Quote check is substring match, not understanding.** The originating system looks for the quote as a literal substring in user messages inside the window, refuses quotes shorter than 2 characters, and looks for negation words in a small radius around the hit. Limits: a coincidental substring counts; paraphrase does not; the window is elapsed time, not “this conversation”; the matcher does not know who the quote was answering. Ask again in plain language when unsure.

This is **go-live restart** (new code). **Process-down revive** is the rescue crew — [`RESCUE.md`](RESCUE.md).

See [`docs/architecture/restart.md`](docs/architecture/restart.md). Gate-file example: §5.

### 2.7 Multi-seat collaboration — **Does**; third seat **In progress**

- **Problem.** Two foreman windows on the same board will double-dispatch the same ticket, or talk past each other in chat that the human never approved.
- **Owner.** Human approves cross-seat messages. Machine keeps seats from claiming the same live ticket. Each seat sees its own pending-review list by default.
- **Minimum.** Seat registry. Inbox between seats (best-effort; a broken inbox must not fail a board write). Cross-seat messages go to a pending queue the human releases. One live construction claim per ticket across foreman seats.
- **Code must enforce.** Private-chat / non-foreman seats may only dispatch read-only research orders. Create is refused while another foreman seat holds the ticket. Cross-seat content has a size cap and is not silently truncated.

Cross-seat messages are released by a human by default. Strictly, that step could be given to a machine; the author prefers to glance at every item and know what the two tables are talking about.

See [`docs/architecture/seats.md`](docs/architecture/seats.md).

### 2.8 Cross-window handoff — **Does**; “refuse every stale” **Recommended**

Five pieces, one job: the next window is a stranger. Chat memory is not a record.

| Piece | Problem | Owner | Minimum | Code must enforce |
|---|---|---|---|---|
| **Handoff block** | First turn of a new session has no local memory | Machine injects once | Short protocol + pointers to files; never a visible chat bubble | Bootstrap at most once per window; failure is not marked success |
| **Drawer** | “What was I to this person?” dies with the window | The sitting AI writes; machine stores | Whole-document replace for the next self of this window; cap length | Hidden from the human; do not paste the whole drawer into every later turn |
| **Current mainline** | Nobody can answer “what are we doing right now?” | Foreman updates the file | One file: doing / how far / next / who is blocked. No parameters | Fingerprint gate: the mainline page carries the progress-page hash. Stale → refuse create **at least once per window**; a second stale in the **same** window fail-opens so the foreman is not stuck. **Recommended:** refuse every time |
| **System map** | Features accumulate until nobody can say what exists | Foreman updates when structure changes | One file: parts and live/stopped/half | Not a hard gate; **Recommended** that closing a ticket names which map line changed |
| **Handbook** | Standing rules reread from chat will drift | Human + foreman | Standing rules in a handbook the worker is told to read | Worker briefs carry commit/report clauses from code, not from memory |

Fail-open on the second stale does not alarm.

See [`docs/architecture/handoff.md`](docs/architecture/handoff.md). Mainline fields: §5.

### 2.9 Prefix changes and per-window freeze — instruction-file freeze **not implemented**

- **Problem.** Tool schemas and standing instructions sit in the model prefix. Changing them mid-window silently changes the world the model thinks it is in, and can force an expensive cache cold-start.
- **Owner.** Human approves prefix batches. Foreman accumulates changes. Machine freezes what a window already bound.
- **Does:** each window binds provider + tool catalog at first claim; later turns reuse that binding; a new window loads the new catalog. One capability per tool (`action` distinguishes verbs). Land runs catalog tests when tool-surface files change.
- **Not implemented:** freezing the *instruction files* (handbook / project instructions) for the life of a window, so an edit on disk does not mutate a live window. Until that gate exists, treat prefix edits as “install between windows,” and do not change prefix files unless the human asked for that batch.
- **Code must enforce (the Does subset).** Do not rebind catalog because wake/kill/permissions flipped. Tool-surface land without passing catalog tests is refused.

**Frozen compatibility contract.** After bind, the old window keeps the **old** catalog description even if the implementation on disk has changed. If a frozen name cannot be resolved, **fail-closed** (do not silently pick a new tool). Explicit provider/manifest change in a live window fails closed.

See [`docs/architecture/tools.md`](docs/architecture/tools.md) and [`docs/architecture/prefix.md`](docs/architecture/prefix.md).

### 2.10 Supervision layer — **Does**; machine nag of unacked tickets is a full-system benefit, not week 1

This is not a second personality in the chat. It is a layer that checks whether the foreman and workers actually moved.

- **Problem.** Foremen promise the next step and call no tool. Workers say “done.” Services die between visits. Failures leave no scene.
- **Owner.** Machine nags and refuses. Foreman still accepts patches. **Recommended:** a separate-vendor read-only reviewer on queue/identity/backup/security changes.
- **Minimum.** (1) Completed work enters pending-review until the foreman acks. (2) Unacked and still-running orders are listed on the next foreman turn. (3) Promise language with zero tool calls gets a bounded nudge. (4) Workers who cannot continue emit a fenced blocker and the task becomes terminal `blocked`; resume is a new task id. (5) Non-success terminals stamp a salvage snapshot (scope status + whether the report file exists). (6) Periodic read-only patrol of host health, process, disk/memory, log errors, event backlog — not a substitute for ack.
- **Code must enforce.** `review_required` cannot be turned off. Blocker fence is tail-only structured JSON. Salvage never reads file contents. Patrol uses explicit colors (green/yellow/red) and must not claim to inspect the construction queue.

See [`docs/architecture/review.md`](docs/architecture/review.md).

### 2.11 Rescue crew — **Does** (the page); the sitting AI cannot be the one who uses it

When the main AI or the chat service is down, the human gives this repository to another model (a different vendor). That model is the rescue crew, not a second foreman. Read [`RESCUE.md`](RESCUE.md) first: what to look at, how to stop, how to revive vs how to roll back, red lines, leave a record. Do not spend money or ship new code while rescuing unless the human said so in this conversation.

## 3. Build order

Architecture pages in `docs/architecture/` are written (13 pages, plus the rescue page). This repository publishes documents only; build src/, config/, scripts/ and tests/ yourself following this file.

### Minimum on-disk formats (fields only; invent your own paths)

**Ticket board** — one **no-delete** markdown table (do not delete rows; status may be updated in place). Columns: `id`, `source`, `date`, `category`, `content`, `status`. Status lives only here. Use a small vocabulary you actually mean (open / in progress / waiting review / done / dropped).

**Casefile** — one markdown file per ticket. Header: ticket id, one-line goal, “status is on the board.” Then append-only records, one per terminal work order:

```text
## <timestamp> · autolog
- work order: <id> (<pool>)
- terminal: completed | failed | blocked | cancelled | expired | late_rejected
- conclusion: <short>
- receipt: <path, test name, or none>
```

Duplicate work-order ids do not double-write. Never copy private chat.

### Week 1 — smallest useful system (do these 4–5)

1. **Ticket board + casefile.** If it is not on the board, it does not exist. Close only with an evidence pointer.
2. **Dispatch contract + queue.** Every write order has ticket, goal, criteria, `allowed_paths`. Create only enqueues; a resident claimer starts work. Write orders without a narrow `allowed_paths` should be refused (**In progress** in the originating system).
3. **Isolated copy + land gate + `git commit --only`.** Workers never need a clean main tree. Out-of-list files cannot land. Listed files ⊆ `allowed_paths`, else refuse.
4. **Handoff minimum:** current-mainline file, handbook, first-turn handoff block. Next window can start without the previous chat.
5. **Restart needs a human nod** as soon as anything is actually running — even if that is a single-file gate plus a receipt. Carpooling can wait for a second seat. Drop the rescue page in the repo the same week; you will need it the first time the sitting AI dies.

Do not start week 1 with multi-seat, prefix freeze, patrol, or a supervisor model. Machine nag of unacked tickets is a full-system benefit, not part of the smallest useful system. Those are pain-triggered.

### After week 1 — which pain adds which part

| Pain you just hit | Add |
|---|---|
| Two windows dispatched the same ticket, or talked behind the human’s back | Multi-seat + human-gated cross-seat queue |
| “I did it” but the diff is empty / wrong | Supervision: pending-review, ack, drop-catcher, blocker fence |
| Worker died and you cannot see what hit disk | Salvage + report rescue |
| Host was unhealthy until someone happened to look | Patrol (host only; keep queue nag on the foreman path) |
| Prefix/tool change mid-window scrambled the model | Catalog freeze (**Does** pattern); instruction-file freeze (**not implemented**) |
| Restarts stacked, extra commits went live unnoticed | Receipt of actual commits (**Does**); carpooling (**Does, awaiting live test**) |
| Tool surface forked into five similar names | One capability per tool + land tests |
| The sitting AI or the chat service died | Rescue crew + [`RESCUE.md`](RESCUE.md) |

## 4. Meta-rules

1. **The same lesson written twice becomes code.** A third reminder in the handbook is a failure to gate.
2. **AI verbal guarantees do not count.** Only evidence: diff, test name, artifact, casefile line. The foreman checks evidence in person: open the file, the commit, or the report and compare. Do not auto-declare acceptance from a worker “done” or from a green test suite alone.
3. **Acceptance reads the diff, not the report.** Green tests prove mechanical rules. The foreman still opens the patch. Worker `completed` means the worker process ended, nothing more.
4. **Standing instructions hold only what every turn needs.** Situational patches live next to the incident (ticket, casefile, land reason) — not in the prefix.
5. **Ask the human only what only a human can decide:** want, taste, spend, go-live (including restart). Do not dump plans, command logs, or half-finished design questions on them.
6. **Dirty trees are normal.** Never stash/reset/clean the main tree to create a “clean” workspace.
7. **Refuse with a reason, or leave a terminal state.** Silence is the bug.
8. **Human authorization quotes expire.** Default suggestion: **30 minutes**. An older quote is not authorization; ask again in plain language. Matching is literal substring — see §2.6.
9. **Operating ability is not authorization.** A local shell does not skip the restart nod.

## 5. Minimal format examples

Fields only; paths are yours. Do not add keys that are not already named in this document.

**Routing table (JSON)**

```json
{
  "version": 1,
  "pools": [
    {
      "id": "pool-a",
      "backend": "worker-engine",
      "model": "model-id",
      "source_class": "how-obtained",
      "billing": "how-paid",
      "quota_windows": ["daily"],
      "needs_owner_ok": true,
      "hard_readonly": false,
      "memory_weight": 1,
      "expires_at": null,
      "status": "active",
      "reason": ""
    }
  ],
  "task_kinds": {
    "build": ["pool-a"]
  }
}
```

`hard_readonly` is a table field. Router skip of write jobs against it is **Recommended / not implemented**.

**Restart gate file (JSON)** — one car; missing file means empty; file present but unreadable must refuse, not become an empty car.

```json
{
  "state": "boarding",
  "passengers": [
    {"seat": "A", "ready": false}
  ]
}
```

States named in the originating system: `boarding` → `departing` → `pending` → `restarting` → `done` / `failed`. One execute order per car.

**Mainline page (fields)** — short file, no history, no parameters. Last line is the fingerprint: first 12 hex chars of the progress-page content hash.

```text
doing: <what this window is for>
how far: <one line>
next: <one line>
blocked on: <who or none>
done when: <completion bar>
wip-rev: <12-hex of progress page>
```

## 6. Gaps to label honestly

Do not sell these as sealed.

- **Concurrent occupy.** Ticket mutex is a create-time scan. Two seats creating in the same moment can both pass the scan. Not a single exclusive lock across seats.
- **Crash before spawn.** Claimed-but-never-spawned **Does** return to `queued`. The gap is the moment between “this row looks eligible” and the write that marks `running`.
- **Casefile write failure.** Fail-open: terminal state is kept, the missing line is a visible failure if inspected, main flow is not rolled back, **no alarm**.
- **Fail-open without alarm.** Second stale fingerprint in the same window; claim-pause path on an unreadable restart gate (so the queue does not freeze forever); casefile append failure. None of these page the human.
- **Auto-continue spends again.** A new work order, same pool, billed again.

## 7. Terms

| 中文 | English | Meaning here |
|---|---|---|
| 拍 | turn | One model round (one reply, with or without tools) |
| 认领 | claim | Resident process takes `queued → running` in one write transaction |
| 病历 | casefile | Per-ticket log; one record per terminal work order |
| 抽屉 | drawer | Whole-document note for the next self of this window; not the board |
| 拼车 | carpool | Independent restart requests board one car; all ready, then one execute |
| 死清单 | dead list | Paths that may be committed; must be ⊆ `allowed_paths` or refuse |
| 席 | seat | A foreman (or private-chat) window’s role on the board |
| 票板 | board | No-delete table of product tickets; status lives only here |
| 工头 | foreman | The sitting AI that plans, dispatches, and accepts |
| 小工 | worker | The AI that implements inside the contract |
| 救火队 | rescue crew | Another vendor’s model, used when the sitting AI or the chat service is down |

Private-chat window = the non-foreman seat that may only dispatch read-only research. Not a third “advisor” seat (that seat is **In progress**).

## 8. Part docs

| File | Part |
|---|---|
| [`docs/architecture/overview.md`](docs/architecture/overview.md) | End-to-end chain |
| [`docs/architecture/ticket.md`](docs/architecture/ticket.md) | Board + casefile |
| [`docs/architecture/dispatch.md`](docs/architecture/dispatch.md) | Switchboard, queue, claim |
| [`docs/architecture/worktree.md`](docs/architecture/worktree.md) | Isolated copy |
| [`docs/architecture/land.md`](docs/architecture/land.md) | Land gate |
| [`docs/architecture/commit.md`](docs/architecture/commit.md) | Dead-list commit |
| [`docs/architecture/restart.md`](docs/architecture/restart.md) | Human-gated go-live restart |
| [`docs/architecture/seats.md`](docs/architecture/seats.md) | Multi-seat |
| [`docs/architecture/handoff.md`](docs/architecture/handoff.md) | Block, drawer, mainline, map, handbook |
| [`docs/architecture/docs-upkeep.md`](docs/architecture/docs-upkeep.md) | One file one job; lessons become code; standing-doc ledger |
| [`docs/architecture/tools.md`](docs/architecture/tools.md) | Catalog, one-capability-per-tool |
| [`docs/architecture/prefix.md`](docs/architecture/prefix.md) | Prefix batch + freeze |
| [`docs/architecture/review.md`](docs/architecture/review.md) | Supervision, ack, salvage, patrol |
| [`docs/tips-from-the-human.md`](docs/tips-from-the-human.md) | Tips the human partner wrote down |
| [`RESCUE.md`](RESCUE.md) | Rescue crew: stop, revive, roll back, red lines |
