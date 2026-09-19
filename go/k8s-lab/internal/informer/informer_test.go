package informer

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// ---------------------------------------------------------------------------
// Recording handler
// ---------------------------------------------------------------------------

type recordEvent struct {
	kind string // "add" | "update" | "delete"
	key  string
}

type recorder struct {
	mu     sync.Mutex
	events []recordEvent
}

func (r *recorder) OnAdd(key string, _ apis.Object) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.events = append(r.events, recordEvent{"add", key})
}

func (r *recorder) OnUpdate(key string, _, _ apis.Object) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.events = append(r.events, recordEvent{"update", key})
}

func (r *recorder) OnDelete(key string, _ apis.Object) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.events = append(r.events, recordEvent{"delete", key})
}

func (r *recorder) snapshot() []recordEvent {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]recordEvent, len(r.events))
	copy(out, r.events)
	return out
}

func waitFor(t *testing.T, desc string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", desc)
}

// ---------------------------------------------------------------------------
// fakeListWatch: full control over list snapshots and watch lifetime
// ---------------------------------------------------------------------------

// fakeListWatch is a scriptable ListWatch: each List() call pops the next
// snapshot; each Watch() returns a channel the test controls (and can close to
// simulate a broken watch).
type fakeListWatch struct {
	mu        sync.Mutex
	snapshots [][]apis.Object
	rv        uint64
	watches   []chan store.WatchEvent
	listCount int
}

func (f *fakeListWatch) List() ([]apis.Object, uint64) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.listCount++
	f.rv++
	var snap []apis.Object
	if len(f.snapshots) > 0 {
		snap = f.snapshots[0]
		f.snapshots = f.snapshots[1:]
	}
	return snap, f.rv
}

func (f *fakeListWatch) Watch(uint64) (<-chan store.WatchEvent, func()) {
	f.mu.Lock()
	defer f.mu.Unlock()
	ch := make(chan store.WatchEvent, 16)
	f.watches = append(f.watches, ch)
	return ch, func() {}
}

// breakLatestWatch closes the most recent watch channel, simulating a server
// disconnect / compaction that forces the Reflector to relist.
func (f *fakeListWatch) breakLatestWatch() {
	f.mu.Lock()
	defer f.mu.Unlock()
	if n := len(f.watches); n > 0 {
		close(f.watches[n-1])
	}
}

func (f *fakeListWatch) lists() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.listCount
}

func fakePod(ns, name string) *apis.Pod {
	return &apis.Pod{ObjectMeta: apis.ObjectMeta{Name: name, Namespace: ns}}
}

// ---------------------------------------------------------------------------
// Tests against the fake source (isolate Reflector logic)
// ---------------------------------------------------------------------------

func TestInitialListSeedsCacheAndFiresAdds(t *testing.T) {
	pods := []apis.Object{fakePod("default", "web-0"), fakePod("default", "web-1")}
	f := &fakeListWatch{snapshots: [][]apis.Object{pods}}
	rec := &recorder{}
	in := New(f, rec)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go in.Run(ctx)

	if !in.WaitForSync(ctx) {
		t.Fatal("WaitForSync reported context cancelled before first LIST")
	}
	waitFor(t, "2 adds", func() bool { return len(rec.snapshot()) == 2 })
	if got := in.Store().Len(); got != 2 {
		t.Errorf("cache len = %d, want 2", got)
	}
	if obj := in.Store().Get("default/web-0"); obj == nil {
		t.Error("cache missing default/web-0 after initial LIST")
	}
}

func TestWatchEventsUpdateCache(t *testing.T) {
	f := &fakeListWatch{snapshots: [][]apis.Object{nil}} // start empty
	rec := &recorder{}
	in := New(f, rec)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go in.Run(ctx)
	in.WaitForSync(ctx)

	send := func(ev store.WatchEvent) {
		waitFor(t, "watch established", func() bool {
			f.mu.Lock()
			defer f.mu.Unlock()
			return len(f.watches) > 0
		})
		f.mu.Lock()
		ch := f.watches[len(f.watches)-1]
		f.mu.Unlock()
		ch <- ev
	}

	send(store.WatchEvent{Type: store.Added, Key: "default/web-0", Object: fakePod("default", "web-0"), ResourceVersion: 5})
	waitFor(t, "add applied", func() bool { return in.Store().Get("default/web-0") != nil })

	send(store.WatchEvent{Type: store.Modified, Key: "default/web-0", Object: fakePod("default", "web-0"), ResourceVersion: 6})
	waitFor(t, "update applied", func() bool {
		kinds := 0
		for _, e := range rec.snapshot() {
			if e.kind == "update" {
				kinds++
			}
		}
		return kinds == 1
	})
	if in.LastResourceVersion() != 6 {
		t.Errorf("LastResourceVersion = %d, want 6", in.LastResourceVersion())
	}

	send(store.WatchEvent{Type: store.Deleted, Key: "default/web-0", Object: fakePod("default", "web-0"), ResourceVersion: 7})
	waitFor(t, "delete applied", func() bool { return in.Store().Get("default/web-0") == nil })
}

// TestRelistOnWatchBreak is the defining resilience property: a closed watch
// channel must trigger a fresh LIST that re-syncs the cache from scratch —
// including dropping objects that vanished while we were disconnected.
func TestRelistOnWatchBreak(t *testing.T) {
	first := []apis.Object{fakePod("default", "web-0"), fakePod("default", "web-1")}
	// After the break, the world changed: web-1 is gone, web-2 appeared.
	second := []apis.Object{fakePod("default", "web-0"), fakePod("default", "web-2")}
	f := &fakeListWatch{snapshots: [][]apis.Object{first, second}}
	in := New(f)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go in.Run(ctx)
	in.WaitForSync(ctx)
	waitFor(t, "initial cache of 2", func() bool { return in.Store().Len() == 2 })

	f.breakLatestWatch()

	waitFor(t, "relist to new snapshot", func() bool {
		return f.lists() >= 2 &&
			in.Store().Get("default/web-2") != nil &&
			in.Store().Get("default/web-1") == nil
	})
}

// TestModifiedWithoutAddPassesNilOld covers the defensive branch where an
// update arrives for a key the cache somehow lacks (missed add across a relist
// boundary): oldObj is nil and the handler still fires.
func TestModifiedWithoutAddPassesNilOld(t *testing.T) {
	f := &fakeListWatch{snapshots: [][]apis.Object{nil}}
	var gotNilOld bool
	var mu sync.Mutex
	in := New(f, HandlerFuncs{
		UpdateFunc: func(_ string, oldObj, _ apis.Object) {
			mu.Lock()
			gotNilOld = oldObj == nil
			mu.Unlock()
		},
	})
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go in.Run(ctx)
	in.WaitForSync(ctx)

	waitFor(t, "watch established", func() bool {
		f.mu.Lock()
		defer f.mu.Unlock()
		return len(f.watches) > 0
	})
	f.mu.Lock()
	ch := f.watches[0]
	f.mu.Unlock()
	ch <- store.WatchEvent{Type: store.Modified, Key: "default/x", Object: fakePod("default", "x"), ResourceVersion: 9}

	waitFor(t, "update handler with nil old", func() bool {
		mu.Lock()
		defer mu.Unlock()
		return gotNilOld
	})
}

func TestHandlerFuncsNilSafe(t *testing.T) {
	// Empty HandlerFuncs must not panic on any event kind.
	h := HandlerFuncs{}
	h.OnAdd("k", nil)
	h.OnUpdate("k", nil, nil)
	h.OnDelete("k", nil)
}

func TestRunStopsOnContextCancel(t *testing.T) {
	f := &fakeListWatch{snapshots: [][]apis.Object{nil}}
	in := New(f)
	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan struct{})
	go func() { in.Run(ctx); close(done) }()
	in.WaitForSync(ctx)

	cancel()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("Run did not return after context cancel")
	}
}

func TestWaitForSyncCancelledContext(t *testing.T) {
	f := &fakeListWatch{snapshots: [][]apis.Object{nil}}
	in := New(f)
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // never run the informer
	if in.WaitForSync(ctx) {
		t.Error("WaitForSync should return false on a cancelled context")
	}
}

func TestCacheGetReturnsCopy(t *testing.T) {
	c := NewCache()
	pod := fakePod("default", "web-0")
	c.upsert("default/web-0", pod)

	got := c.Get("default/web-0")
	got.GetObjectMeta().Name = "mutated"
	if again := c.Get("default/web-0").GetObjectMeta().Name; again != "web-0" {
		t.Errorf("cache corrupted through Get: name = %q", again)
	}
}

func TestCacheListSorted(t *testing.T) {
	c := NewCache()
	c.upsert("default/c", fakePod("default", "c"))
	c.upsert("default/a", fakePod("default", "a"))
	c.upsert("default/b", fakePod("default", "b"))
	list := c.List()
	if len(list) != 3 {
		t.Fatalf("List len = %d, want 3", len(list))
	}
	for i, want := range []string{"a", "b", "c"} {
		if got := list[i].GetObjectMeta().Name; got != want {
			t.Errorf("List[%d] = %q, want %q", i, got, want)
		}
	}
}

func TestKeyOf(t *testing.T) {
	if got := keyOf(fakePod("kube-system", "core-dns")); got != "kube-system/core-dns" {
		t.Errorf("keyOf = %q", got)
	}
}

// ---------------------------------------------------------------------------
// Integration: informer over a real apiserver + store
// ---------------------------------------------------------------------------

func TestServerListWatchIntegration(t *testing.T) {
	srv := apiserver.New(store.New())
	lw := NewServerListWatch(srv, "pods")
	rec := &recorder{}
	in := New(lw, rec)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go in.Run(ctx)
	in.WaitForSync(ctx)

	// Write through the apiserver; the informer must see it.
	if _, err := srv.Create("pods", fakePod("default", "web-0")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	waitFor(t, "informer to observe the created pod", func() bool {
		return in.Store().Get("default/web-0") != nil
	})

	// Objects from other resources must not leak into this informer.
	rs := &apis.ReplicaSet{
		ObjectMeta: apis.ObjectMeta{Name: "web", Namespace: "default"},
		Spec: apis.ReplicaSetSpec{
			Replicas: 1,
			Selector: apis.LabelSelector{MatchLabels: map[string]string{"app": "web"}},
			Template: apis.PodTemplateSpec{
				ObjectMeta: apis.ObjectMeta{Labels: map[string]string{"app": "web"}},
			},
		},
	}
	if _, err := srv.Create("replicasets", rs); err != nil {
		t.Fatalf("Create rs: %v", err)
	}
	time.Sleep(50 * time.Millisecond)
	if got := in.Store().Len(); got != 1 {
		t.Errorf("cache len = %d, want 1 (replicasets must not enter a pods informer)", got)
	}

	// Delete propagates too.
	if _, err := srv.Delete("pods", "default", "web-0"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	waitFor(t, "informer to observe the delete", func() bool {
		return in.Store().Get("default/web-0") == nil
	})
}

func TestServerListWatchUnknownResourceClosesWatch(t *testing.T) {
	srv := apiserver.New(store.New())
	lw := NewServerListWatch(srv, "deployments") // not registered
	ch, stop := lw.Watch(0)
	defer stop()
	if _, ok := <-ch; ok {
		t.Error("watch on unknown resource should be a closed channel")
	}
}
