# Go Lab (go)

## Overview
Go language laboratory focusing on cloud-native, concurrency, and systems programming. Idiomatic Go patterns with module-based dependency management.

## Build System
- **Module Management**: Go modules (`go.mod`)
- **Build Tool**: `go build`
- **Test Tool**: `go test`
- **Linter**: `golangci-lint`
- **Dependency**: `go get` or `go mod tidy`

## Project Structure

```text
go/
├── SKILL.md         # This file
└── k8s-lab/         # Mini Kubernetes control plane from scratch (zero deps)
```

- `k8s-lab/` — a pure-stdlib implementation of the core k8s control-plane
  machinery for learning: MVCC store (etcd-like), typed apiserver facade,
  informers (LIST+WATCH), dedup workqueue, ReplicaSet controller with
  expectations, kubelet simulator, and an end-to-end demo
  (`go run ./cmd/demo`). See `k8s-lab/README.md`.

Other Go code in the repository:

- `liminalis/llm-wiki/` — the substantial Go module (CLI + web context service)
- `cc/golab/` — a single cgo-interop LeetCode file

## Key Concepts
- **Concurrency**: Goroutines, channels, select, context
- **Error Handling**: Explicit errors (no exceptions)
- **Interfaces**: Structural typing, implicit satisfaction
- **Pointers**: Value vs reference semantics
- **Zero Value**: Variables initialized to zero by default

## Coding Conventions
- Use `gofmt` for formatting (standard tool)
- Package names: short, lowercase, simple
- Receiver methods for type operations
- `err` as last return value convention
- `ctx context.Context` first parameter for request-scoped operations
- Slice capacity doubling for growth
- `io.Reader`/`io.Writer` for streaming

## AI Vibe Coding Tips
- Always handle errors explicitly (no `panic` in production code)
- Use `context` for cancellation and timeouts
- Prefer small, focused interfaces (`io.Reader`, `io.Writer`)
- Use `sync.Pool` for object reuse under pressure
- Remember: slices are reference types, arrays are value types
- Use `go vet` and `golangci-lint` for quality checks
- Profile with `pprof` for performance issues
- Goroutine leaks: ensure proper channel closure
