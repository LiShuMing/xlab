# SP4 — 删除 / TTL / 级联 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** DeleteContext cascade, asset delete, TTL cleanup, privacy gate at delete.

**Architecture:** Extend Repository with 7 Delete* methods; rewrite DeleteContext for cascade; add TTL service + CLI; add asset delete CLI.

**Tech Stack:** Go 1.25, file backend (JSON), postgres backend.

---

### Task 1: Extend Repository interface + file backend Delete* methods

**Files:**
- Modify: `internal/repository/store.go` (interface + file Store methods)
- Modify: `internal/repository/entity_store.go` (file backend impls)

- [ ] **Step 1: Add 7 Delete* methods to Repository interface**

```go
// Soft-delete context vector by contextID (sets state=deleted)
DeleteContextVector(contextID string) error
// Remove matches referencing a contextID
DeleteMatchesByContextID(contextID string) error
// Soft-delete summaries referencing a contextID
DeleteSummariesBySourceContextID(contextID string) error
// Soft-delete extraction jobs referencing a contextID
DeleteJobsByContextID(contextID string) error
// Delete contexts that originated from an asset (returns them for cascade)
DeleteContextsByAssetID(assetID string) ([]domain.ContextItem, error)
// Hard-delete an asset by id (returns the deleted asset)
DeleteAsset(id string) (*domain.SourceAsset, error)
// Find contexts where ExpiresAt <= now and state is still active
FindExpiredContexts(now time.Time) ([]domain.ContextItem, error)
```

- [ ] **Step 2: Implement for file backend (Store)**

In `internal/repository/store.go`, add methods on `*Store`:

- `DeleteContextVector`: find by contextID in State.Vectors, remove from slice, save
- `DeleteMatchesByContextID`: filter out matches where ContextIDs contains the target, save
- `DeleteSummariesBySourceContextID`: filter out summaries where SourceContextIDs contains the target, save
- `DeleteJobsByContextID`: filter out jobs where Input["context_id"] matches, save
- `DeleteContextsByAssetID`: collect contexts where SourceAssetID matches, return before deleting
- `DeleteAsset`: find by ID in State.Assets, remove from slice, save, return deleted
- `FindExpiredContexts`: iterate contexts, return those with ExpiresAt != nil && <= now && State == StateActive

- [ ] **Step 3: Implement for postgres backend (entity_postgres.go)**

Add postgres implementations for all 7 methods using DELETE/UPDATE SQL.

- [ ] **Step 4: Verify**

```bash
go build ./...
go test ./... -count=1
```

- [ ] **Step 5: Commit**

```bash
git add internal/repository/
git commit -m "feat(repo): add Delete* methods to Repository interface + backends"
```

---

### Task 2: Rewrite DeleteContext for cascade

**Files:**
- Modify: `internal/service/services.go`

- [ ] **Step 1: Rewrite DeleteContext**

Replace the current soft-delete-only implementation:

```go
func (a *App) DeleteContext(id string) (*domain.ContextItem, error) {
    ctx, err := a.Store.ContextByID(id)
    if err != nil {
        return nil, err
    }
    // Cascade: delete vector
    _ = a.Store.DeleteContextVector(ctx.ID)
    // Cascade: delete matches referencing this context
    _ = a.Store.DeleteMatchesByContextID(ctx.ID)
    // Cascade: delete summaries referencing this context
    _ = a.Store.DeleteSummariesBySourceContextID(ctx.ID)
    // Cascade: delete extraction jobs referencing this context
    _ = a.Store.DeleteJobsByContextID(ctx.ID)
    // Mark context as deleted
    return a.Store.UpdateContext(id, func(c *domain.ContextItem) error {
        now := time.Now()
        c.State = domain.StateDeleted
        c.DeletedAt = &now
        c.UpdatedAt = now
        return nil
    })
}
```

- [ ] **Step 2: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/service/services.go
git commit -m "feat(service): cascade delete context to vectors/matches/summaries/jobs"
```

---

### Task 3: Add privacy gate at delete point

**Files:**
- Modify: `internal/service/services.go`

- [ ] **Step 1: Add DeleteContextByUser**

Add a new method that takes user handle + contextID and verifies ownership before deleting:

```go
func (a *App) DeleteContextByUser(handle, contextID string) (*domain.ContextItem, error) {
    user, err := a.Store.UserByHandle(handle)
    if err != nil {
        return nil, fmt.Errorf("user lookup: %w", err)
    }
    ctx, err := a.Store.ContextByID(contextID)
    if err != nil {
        return nil, err
    }
    if ctx.UserID != user.ID {
        _ = a.Store.AddAudit(domain.UsageAudit{
            ID: domain.NewID("audit"), Event: "delete_context_blocked",
            UserID: user.ID, ContextID: contextID,
            Info: map[string]any{"reason": "ownership_mismatch", "context_owner": ctx.UserID},
            CreatedAt: time.Now(),
        })
        return nil, fmt.Errorf("context %q does not belong to user %q", contextID, handle)
    }
    return a.DeleteContext(contextID)
}
```

- [ ] **Step 2: Update CLI to use DeleteContextByUser**

In `internal/cli/cli.go`, update the `context delete` handler to pass user handle instead of calling DeleteContext directly. Read `--user` flag (same as other context subcommands).

- [ ] **Step 3: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/service/services.go internal/cli/cli.go
git commit -m "feat(service): add privacy gate at context delete with ownership check"
```

---

### Task 4: Add asset delete CLI + cascade

**Files:**
- Modify: `internal/cli/cli.go`
- Modify: `internal/service/services.go`

- [ ] **Step 1: Add DeleteAsset service method**

```go
func (a *App) DeleteAsset(assetID string, cascadeContexts bool) (*domain.SourceAsset, error) {
    asset, err := a.Store.DeleteAsset(assetID)
    if err != nil {
        return nil, err
    }
    if cascadeContexts {
        contexts, _ := a.Store.DeleteContextsByAssetID(assetID)
        for _, ctx := range contexts {
            _ = a.DeleteContext(ctx.ID)
        }
    }
    return asset, nil
}
```

- [ ] **Step 2: Add CLI subcommand**

```go
case "delete":
    fs := flag.NewFlagSet("asset delete", flag.ExitOnError)
    cascade := fs.Bool("cascade-contexts", false, "also delete contexts from this asset")
    fs.Parse(args[1:])
    if fs.NArg() < 1 {
        return fmt.Errorf("usage: ctx asset delete ASSET_ID [--cascade-contexts]")
    }
    asset, err := app.DeleteAsset(fs.Arg(0), *cascade)
    ...
```

- [ ] **Step 3: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/cli/cli.go internal/service/services.go
git commit -m "feat(cli): add ctx asset delete --cascade-contexts"
```

---

### Task 5: Add TTL cleanup service + CLI

**Files:**
- Create: `internal/service/ttl.go`
- Modify: `internal/cli/cli.go`

- [ ] **Step 1: Create ttl.go**

```go
func (a *App) ExpireTTL() (int, error) {
    now := time.Now()
    expired, err := a.Store.FindExpiredContexts(now)
    if err != nil {
        return 0, err
    }
    count := 0
    for _, ctx := range expired {
        // Use full cascade delete
        if _, err := a.DeleteContext(ctx.ID); err != nil {
            continue
        }
        count++
    }
    return count, nil
}
```

- [ ] **Step 2: Add CLI command `ctx process --expire-ttl`**

Add a `process` subcommand with `--expire-ttl` flag. Or a simpler `ctx ttl clean` subcommand.

- [ ] **Step 3: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/service/ttl.go internal/cli/cli.go
git commit -m "feat(service): add TTL expiration cleanup + CLI command"
```

---

### Task 6: Full regression

- [ ] **Step 1: All tests**

```bash
go test ./... -count=1 -v 2>&1 | tail -30
```

- [ ] **Step 2: Demo flows**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | head -10
go run ./cmd/ctx --data $(mktemp -d) --provider golden demo run 2>&1 | head -10
```

- [ ] **Step 3: Build both binaries**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/ && echo "both build ok"
```

---

### 验收标准

1. `ctx context delete CTX_ID` cascades to vector + match + summary + job
2. `ctx asset delete ASSET_ID --cascade-contexts` works end to end
3. `ctx process --expire-ttl` cleans expired contexts
4. Non-owner context delete is rejected with audit record
5. `go test ./...` passes
6. `ctx demo run` no regression
