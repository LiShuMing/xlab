// Package informer implements the LIST+WATCH machinery behind client-go
// informers: a Reflector that mirrors one resource from the apiserver into a
// local, thread-safe cache and fires handler callbacks on every change.
//
// What it teaches about Kubernetes clients:
//
//   - Controllers do not poll the apiserver. On startup they LIST the whole
//     resource (seeding the cache and recording the list's resourceVersion),
//     then WATCH from that revision so no change is missed and none is seen
//     twice. This is why ListWithRevision pairs the snapshot with its
//     revision atomically.
//   - Reads hit the local cache, not the server: a controller reconciling in
//     a loop costs the apiserver nothing after the initial LIST. This is the
//     whole reason informers exist — a hundred controllers watching Pods
//     would otherwise melt the API server.
//   - Watches break (network, server restart, log compaction/etcd eviction).
//     The Reflector's response is always the same: relist. Correctness never
//     depends on seeing every event exactly once; it depends on the cache
//     eventually matching the server. Level-triggered design makes that safe.
//   - Handlers are notifications, not data. Our handlers just enqueue the
//     key; the reconcile reads state from the cache when it runs.
package informer

import (
	"context"
	"runtime"
	"sort"
	"sync"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// ListWatch abstracts the two apiserver operations a Reflector needs,
// mirroring client-go's cache.ListerWatcher. Depending on this interface
// rather than a concrete server keeps the informer testable in isolation.
type ListWatch interface {
	// List returns a consistent snapshot with the revision it was taken at.
	List() ([]apis.Object, uint64)
	// Watch streams changes that occur after sinceRV. The returned func
	// cancels the watch; the channel closing means "relist needed".
	Watch(sinceRV uint64) (<-chan store.WatchEvent, func())
}

// ResourceEventHandler receives cache-change notifications, mirroring
// client-go's tool of the same name. Handlers run sequentially in the
// Reflector goroutine, so they must be cheap — enqueue a key, nothing more.
type ResourceEventHandler interface {
	OnAdd(key string, obj apis.Object)
	OnUpdate(key string, oldObj, newObj apis.Object)
	OnDelete(key string, obj apis.Object)
}

// HandlerFuncs adapts plain functions to ResourceEventHandler.
type HandlerFuncs struct {
	AddFunc    func(key string, obj apis.Object)
	UpdateFunc func(key string, oldObj, newObj apis.Object)
	DeleteFunc func(key string, obj apis.Object)
}

// OnAdd implements ResourceEventHandler.
func (h HandlerFuncs) OnAdd(key string, obj apis.Object) {
	if h.AddFunc != nil {
		h.AddFunc(key, obj)
	}
}

// OnUpdate implements ResourceEventHandler.
func (h HandlerFuncs) OnUpdate(key string, oldObj, newObj apis.Object) {
	if h.UpdateFunc != nil {
		h.UpdateFunc(key, oldObj, newObj)
	}
}

// OnDelete implements ResourceEventHandler.
func (h HandlerFuncs) OnDelete(key string, obj apis.Object) {
	if h.DeleteFunc != nil {
		h.DeleteFunc(key, obj)
	}
}

// Cache is the informer's local, thread-safe mirror of one resource. It is a
// cut-down client-go cache.Store / ThreadSafeStore.
type Cache struct {
	mu      sync.RWMutex
	objects map[string]apis.Object
}

// NewCache returns an empty Cache.
func NewCache() *Cache {
	return &Cache{objects: make(map[string]apis.Object)}
}

// Get returns the cached object for key (deep-copied, so callers cannot
// corrupt the cache) or nil if absent.
func (c *Cache) Get(key string) apis.Object {
	c.mu.RLock()
	defer c.mu.RUnlock()
	obj, ok := c.objects[key]
	if !ok {
		return nil
	}
	return obj.DeepCopyObject()
}

// List returns deep copies of every cached object, keyed-sorted for
// determinism.
func (c *Cache) List() []apis.Object {
	c.mu.RLock()
	defer c.mu.RUnlock()
	out := make([]apis.Object, 0, len(c.objects))
	keys := make([]string, 0, len(c.objects))
	for k := range c.objects {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		out = append(out, c.objects[k].DeepCopyObject())
	}
	return out
}

// Len returns the number of cached objects.
func (c *Cache) Len() int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return len(c.objects)
}

// replace swaps in a fresh snapshot. Called by the Reflector after LIST; it
// discards any stale view, exactly like client-go's cache.Replace.
func (c *Cache) replace(objects []apis.Object) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.objects = make(map[string]apis.Object, len(objects))
	for _, obj := range objects {
		c.objects[keyOf(obj)] = obj
	}
}

// upsert stores one object (Added/Modified event).
func (c *Cache) upsert(key string, obj apis.Object) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.objects[key] = obj
}

// remove deletes one object (Deleted event).
func (c *Cache) remove(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.objects, key)
}

// Informer mirrors one resource from a ListWatch source into a Cache and
// dispatches events to registered handlers.
type Informer struct {
	lw    ListWatch
	cache *Cache

	hmu      sync.RWMutex // guards handlers
	handlers []ResourceEventHandler

	mu     sync.RWMutex
	lastRV uint64 // revision of the most recent applied state
	// hasSynced becomes true after the first LIST completes. Controllers
	// wait for it before reconciling, so they never act on a half-populated
	// cache — client-go's WaitForCacheSync exists for the same reason.
	hasSynced bool
}

// New returns an Informer that mirrors via lw and notifies handlers.
func New(lw ListWatch, handlers ...ResourceEventHandler) *Informer {
	return &Informer{
		lw:       lw,
		cache:    NewCache(),
		handlers: handlers,
	}
}

// Store exposes the read-only local cache.
func (in *Informer) Store() *Cache { return in.cache }

// HasSynced reports whether the initial LIST has completed at least once.
func (in *Informer) HasSynced() bool {
	in.mu.RLock()
	defer in.mu.RUnlock()
	return in.hasSynced
}

// LastResourceVersion returns the revision of the latest applied change.
func (in *Informer) LastResourceVersion() uint64 {
	in.mu.RLock()
	defer in.mu.RUnlock()
	return in.lastRV
}

// Run drives the Reflector until ctx is cancelled. It is the blocking entry
// point; callers typically run it in its own goroutine.
//
// The loop is intentionally simple and mirrors client-go's Reflector:
//
//	for { list-and-watch until the watch breaks; repeat }
//
// Every iteration is a fresh LIST followed by a WATCH from the list's
// revision, so watch breaks (channel close) cost one relist and no
// correctness — the defining trade-off of level-triggered systems.
func (in *Informer) Run(ctx context.Context) {
	for {
		if ctx.Err() != nil {
			return
		}
		in.listAndWatch(ctx)
	}
}

// listAndWatch performs one LIST+WATCH cycle. It returns when the context is
// cancelled or the watch channel closes (server-side cancellation or a
// force-closed slow consumer), after which Run relists.
func (in *Informer) listAndWatch(ctx context.Context) {
	// LIST: atomically get a consistent snapshot and its revision.
	objs, rv := in.lw.List()
	in.cache.replace(objs)
	in.mu.Lock()
	in.lastRV = rv
	in.hasSynced = true
	in.mu.Unlock()

	// Fire OnAdd for the seeded objects so controllers that enqueue on
	// add reconcile the world as it already exists at startup. client-go
	// does the same: initial list items are delivered as Adds.
	for _, obj := range objs {
		key := keyOf(obj)
		in.dispatchAdd(key, obj)
	}

	// WATCH from the list revision: every later change arrives exactly once
	// until the channel closes.
	ch, stop := in.lw.Watch(rv)
	defer stop()

	for {
		select {
		case <-ctx.Done():
			return
		case ev, ok := <-ch:
			if !ok {
				// Watch broke: relist. This is normal, not an error —
				// compaction and server restarts do it in real clusters.
				return
			}
			in.applyEvent(ev)
		}
	}
}

// applyEvent updates the cache and notifies handlers for one watch event.
//
// Note the key normalization: the store's event key is its full path
// (/pods/default/web-0), but the cache — like client-go's — is keyed by
// namespace/name (MetaNamespaceKeyFunc). Deriving the key from the object's
// metadata keeps the LIST-seeded and WATCH-applied entries in one key space.
func (in *Informer) applyEvent(ev store.WatchEvent) {
	key := keyOf(ev.Object)
	switch ev.Type {
	case store.Added:
		in.cache.upsert(key, ev.Object)
		in.dispatchAdd(key, ev.Object)
	case store.Modified:
		old := in.cache.Get(key) // may be nil if we somehow missed the Add
		in.cache.upsert(key, ev.Object)
		in.dispatchUpdate(key, old, ev.Object)
	case store.Deleted:
		in.cache.remove(key)
		in.dispatchDelete(key, ev.Object)
	}

	in.mu.Lock()
	if ev.ResourceVersion > in.lastRV {
		in.lastRV = ev.ResourceVersion
	}
	in.mu.Unlock()
}

// AddHandler registers an extra handler after construction, mirroring
// client-go's SharedInformer.AddEventHandler. Handlers run in registration
// order on the Reflector goroutine. Safe to call concurrently with Run.
func (in *Informer) AddHandler(h ResourceEventHandler) {
	in.hmu.Lock()
	defer in.hmu.Unlock()
	in.handlers = append(in.handlers, h)
}

func (in *Informer) dispatchAdd(key string, obj apis.Object) {
	for _, h := range in.snapshotHandlers() {
		h.OnAdd(key, obj)
	}
}

func (in *Informer) dispatchUpdate(key string, oldObj, newObj apis.Object) {
	for _, h := range in.snapshotHandlers() {
		h.OnUpdate(key, oldObj, newObj)
	}
}

func (in *Informer) dispatchDelete(key string, obj apis.Object) {
	for _, h := range in.snapshotHandlers() {
		h.OnDelete(key, obj)
	}
}

// snapshotHandlers copies the handler slice so dispatch never holds the lock
// while calling user code (which may call AddHandler and deadlock otherwise).
func (in *Informer) snapshotHandlers() []ResourceEventHandler {
	in.hmu.RLock()
	defer in.hmu.RUnlock()
	out := make([]ResourceEventHandler, len(in.handlers))
	copy(out, in.handlers)
	return out
}

// WaitForSync blocks until the informer has completed its first LIST or ctx
// is cancelled, reporting which happened. It is the lab's version of
// cache.WaitForCacheSync.
func (in *Informer) WaitForSync(ctx context.Context) bool {
	for {
		if in.HasSynced() {
			return true
		}
		if ctx.Err() != nil {
			return false
		}
		select {
		case <-ctx.Done():
			return false
		default:
			// Busy-wait with a yield; the first LIST is effectively
			// instantaneous in-process, so this resolves in microseconds.
			// Real client-go polls on a timer for the same reason.
			runtime.Gosched()
		}
	}
}

// keyOf derives the cache key from an object's metadata. The store already
// uses apis.Key paths as event keys; rebuilding from metadata keeps the cache
// self-consistent even if an event's Key and object ever disagreed.
func keyOf(obj apis.Object) string {
	meta := obj.GetObjectMeta()
	if meta == nil {
		return ""
	}
	return meta.Namespace + "/" + meta.Name
}
