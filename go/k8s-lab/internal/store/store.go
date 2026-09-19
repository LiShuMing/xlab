// Package store implements a minimal etcd-like backing store for the mini
// control plane. It is the single source of truth that the apiserver
// fronts and that every controller watches.
//
// What it teaches about Kubernetes storage:
//
//   - MVCC: every write bumps a single monotonically increasing revision.
//     Objects carry that revision as resourceVersion. This is exactly how
//     etcd's global revision backs Kubernetes optimistic concurrency.
//   - Optimistic concurrency: Update requires the caller's resourceVersion to
//     match the current one, else it returns ErrConflict. Controllers must
//     re-read and retry — this is why reconcile loops are written to be
//     idempotent and to requeue on conflict.
//   - Watch: subscribers receive a stream of changes with the revision at
//     which each occurred, so an informer can keep a local cache and never
//     poll. This is the mechanism behind client-go informers.
//
// The store is deliberately in-memory and single-node; real etcd is a Raft
// replicated log, but the client-visible semantics modelled here are the ones
// controllers actually depend on.
package store

import (
	"errors"
	"fmt"
	"sort"
	"strings"
	"sync"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
)

// Object is the store's view of a storable API object.
type Object = apis.Object

// Sentinel errors returned by the store.
var (
	// ErrNotFound is returned for Get/Update/Delete on a missing key.
	ErrNotFound = errors.New("store: object not found")
	// ErrAlreadyExists is returned when Create targets an existing key.
	ErrAlreadyExists = errors.New("store: object already exists")
	// ErrConflict is returned by Update when the supplied resourceVersion is
	// stale. The caller must re-read and retry (optimistic concurrency).
	ErrConflict = errors.New("store: conflict, resourceVersion is stale")
)

// entry is one stored object plus the revision it was written at.
type entry struct {
	obj             Object
	resourceVersion uint64
}

// Store is a concurrency-safe, MVCC, watchable key/object store.
type Store struct {
	mu       sync.RWMutex
	revision uint64 // global monotonic counter; never decreases
	objects  map[string]entry
	// events is a bounded log of recent changes used to replay a watch that
	// resumes at an older revision. Real etcd retains history until
	// compaction; we keep a fixed ring to bound memory while still modelling
	// "resume from resourceVersion" faithfully for recent events.
	events    []WatchEvent
	maxEvents int
	watchers  map[uint64]*watcher
	nextID    uint64
}

// watcher is a single subscription.
//
// Delivery uses a two-stage buffer: commit() appends to pending (under the
// store lock, in revision order) and a per-watcher pump goroutine drains
// pending into ch. Splitting it this way keeps global ordering correct even
// while a consumer is slow, and lets Watch() seed pending with the replay
// backlog before the watcher starts receiving live events.
//
// ch is buffered; if a consumer is so slow that pending grows past
// maxPending, the watcher is considered broken and closed, forcing the
// informer to relist. This mirrors client-go's watch buffer + relist-on-lag.
type watcher struct {
	prefix  string
	ch      chan WatchEvent
	done    chan struct{} // closed on stop; unblocks the pump
	closed  bool
	pending []WatchEvent
	notify  chan struct{} // buffered size 1; wakes the pump
}

// maxPending caps a watcher's backlog before it is force-closed as a slow
// consumer.
const maxPending = 1024

// defaultMaxEvents bounds the replay log. 4096 comfortably exceeds any
// workload in this lab while keeping memory trivial.
const defaultMaxEvents = 4096

// New returns an empty Store. Revision starts at 1 so that the first write
// produces resourceVersion "1" (k8s resourceVersion is an opaque string, but
// a non-zero start avoids ambiguity with the zero value).
func New() *Store {
	return &Store{
		revision:  1,
		objects:   make(map[string]entry),
		events:    make([]WatchEvent, 0, 256),
		maxEvents: defaultMaxEvents,
		watchers:  make(map[uint64]*watcher),
	}
}

// Revision returns the current global revision (the resourceVersion of the
// store as a whole). Informers record this to resume watches.
func (s *Store) Revision() uint64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.revision
}

// Create inserts a new object under key. It fails with ErrAlreadyExists if the
// key is taken. The object's resourceVersion is stamped from the new revision.
func (s *Store) Create(key string, obj Object) (Object, error) {
	if key == "" {
		return nil, fmt.Errorf("store: empty key")
	}
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, ok := s.objects[key]; ok {
		return nil, ErrAlreadyExists
	}
	s.revision++
	rv := s.revision
	// Store a deep copy so later caller mutations cannot corrupt the
	// authoritative state (real etcd gets this isolation via serialization).
	stamped := stamp(obj.DeepCopyObject(), rv)
	s.objects[key] = entry{obj: stamped, resourceVersion: rv}
	s.commit(key, Added, stamped, rv)
	return stamped.DeepCopyObject(), nil
}

// Get returns a deep copy of the object at key, or ErrNotFound.
func (s *Store) Get(key string) (Object, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	e, ok := s.objects[key]
	if !ok {
		return nil, ErrNotFound
	}
	return e.obj.DeepCopyObject(), nil
}

// Update replaces the object at key under optimistic concurrency.
//
// If expectedResourceVersion is non-zero it must equal the object's current
// resourceVersion, else ErrConflict is returned. Passing zero skips the check
// (a "blind write"), which the apiserver only allows for subresource-style
// status updates in this lab.
func (s *Store) Update(key string, obj Object, expectedResourceVersion uint64) (Object, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	cur, ok := s.objects[key]
	if !ok {
		return nil, ErrNotFound
	}
	if expectedResourceVersion != 0 && expectedResourceVersion != cur.resourceVersion {
		return nil, fmt.Errorf("%w: got %d, current is %d", ErrConflict, expectedResourceVersion, cur.resourceVersion)
	}
	s.revision++
	rv := s.revision
	stamped := stamp(obj.DeepCopyObject(), rv)
	s.objects[key] = entry{obj: stamped, resourceVersion: rv}
	s.commit(key, Modified, stamped, rv)
	return stamped.DeepCopyObject(), nil
}

// Delete removes the object at key. It returns the last state of the object
// (as a watch Deleted event carries it) or ErrNotFound.
func (s *Store) Delete(key string) (Object, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	cur, ok := s.objects[key]
	if !ok {
		return nil, ErrNotFound
	}
	s.revision++
	rv := s.revision
	deleted := cur.obj.DeepCopyObject()
	stamp(deleted, rv)
	delete(s.objects, key)
	// The delete is recorded in the event log so a watcher resuming at an
	// older revision still observes it; real etcd keeps tombstones until
	// compaction, and we keep a bounded log for the same purpose.
	s.commit(key, Deleted, deleted, rv)
	return deleted, nil
}

// List returns deep copies of all objects whose key starts with prefix,
// ordered by key for determinism. Mirrors the apiserver LIST operation.
func (s *Store) List(prefix string) []Object {
	s.mu.RLock()
	defer s.mu.RUnlock()

	keys := make([]string, 0, len(s.objects))
	for k := range s.objects {
		if strings.HasPrefix(k, prefix) {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)

	out := make([]Object, 0, len(keys))
	for _, k := range keys {
		out = append(out, s.objects[k].obj.DeepCopyObject())
	}
	return out
}

// ListWithRevision atomically returns a sorted snapshot of all objects under
// prefix together with the global revision at that instant.
//
// This pairing is what makes the informer pattern exact: LIST gives a
// consistent snapshot plus the revision it was taken at, then WATCH resumes
// from that revision — guaranteeing no change is missed and none is
// double-counted. Real Kubernetes LIST responses carry the same
// resourceVersion in their list metadata for precisely this reason.
func (s *Store) ListWithRevision(prefix string) ([]Object, uint64) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	keys := make([]string, 0, len(s.objects))
	for k := range s.objects {
		if strings.HasPrefix(k, prefix) {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)

	out := make([]Object, 0, len(keys))
	for _, k := range keys {
		out = append(out, s.objects[k].obj.DeepCopyObject())
	}
	return out, s.revision
}

// commit records a change in the event log and enqueues it to every matching
// watcher. Called with s.mu held (write-locked) from Create/Update/Delete.
//
// The object is deep-copied once here; each watcher receives the same
// immutable snapshot, so a consumer mutating what it gets cannot affect
// another consumer or the store.
func (s *Store) commit(key string, typ EventType, obj Object, rv uint64) {
	ev := WatchEvent{
		Type:            typ,
		Key:             key,
		Object:          obj.DeepCopyObject(),
		ResourceVersion: rv,
	}
	s.appendEvent(ev)
	for id, w := range s.watchers {
		if w.closed || !strings.HasPrefix(key, w.prefix) {
			continue
		}
		w.pending = append(w.pending, ev)
		if len(w.pending) > maxPending {
			// Consumer is hopelessly behind; force a relist by cancelling it.
			// We only close `done` here — the pump owns `ch` and closes it on
			// the way out, so there is no send-on-closed-channel race.
			delete(s.watchers, id)
			s.closeWatcher(w)
			continue
		}
		// Wake the pump (non-blocking; a pending signal may already be set).
		select {
		case w.notify <- struct{}{}:
		default:
		}
	}
}

// closeWatcher cancels a watcher exactly once by closing its done channel.
// It never touches w.ch: only the pump closes ch (via defer), which keeps
// shutdown free of send-on-closed-channel races. Callers must hold s.mu.
func (s *Store) closeWatcher(w *watcher) {
	if w.closed {
		return
	}
	w.closed = true
	close(w.done)
}

// appendEvent adds ev to the bounded replay log, evicting the oldest entry
// when full. Called with s.mu held.
func (s *Store) appendEvent(ev WatchEvent) {
	if len(s.events) >= s.maxEvents {
		// Drop the oldest; a watcher resuming before the retained window must
		// relist. This is the in-memory analogue of etcd compaction.
		s.events = s.events[1:]
	}
	s.events = append(s.events, ev)
}

// Watch subscribes to changes on keys under prefix, starting AFTER the given
// resourceVersion.
//
// Resume semantics: any event in the retained log with ResourceVersion >
// sinceResourceVersion and a matching prefix is replayed first, then live
// changes stream in. Passing 0 means "everything retained". If the requested
// revision has already been evicted from the log, the caller cannot catch up
// incrementally and must LIST to reseed — the informer handles that by
// starting a fresh Watch after re-listing.
//
// This is the primitive an informer's Reflector uses: LIST to seed a cache,
// record the list revision, then WATCH from that revision onward.
func (s *Store) Watch(prefix string, sinceResourceVersion uint64) (<-chan WatchEvent, func()) {
	s.mu.Lock()
	w := &watcher{
		prefix: prefix,
		ch:     make(chan WatchEvent, 64),
		done:   make(chan struct{}),
		notify: make(chan struct{}, 1),
	}
	// Seed the replay backlog before registering, so no live event can slip
	// in ahead of the history.
	for _, ev := range s.events {
		if ev.ResourceVersion > sinceResourceVersion && strings.HasPrefix(ev.Key, prefix) {
			w.pending = append(w.pending, ev)
		}
	}
	id := s.nextID
	s.nextID++
	s.watchers[id] = w
	// Kick the pump in case the backlog is already non-empty.
	select {
	case w.notify <- struct{}{}:
	default:
	}
	s.mu.Unlock()

	go s.pump(w)
	return w.ch, func() { s.stopWatcher(id) }
}

// pump drains a watcher's pending queue into its channel until the watcher is
// cancelled. It is the sole closer of w.ch (via defer), which is what makes
// shutdown race-free: every cancellation path only closes w.done, and the pump
// observes that and closes ch on its way out.
//
// It holds s.mu only to move events out of pending, never while blocking on a
// channel send, so a slow consumer cannot stall the store.
func (s *Store) pump(w *watcher) {
	defer close(w.ch)
	for {
		// Snapshot state under the lock; never block on ch while holding it.
		s.mu.Lock()
		closed := w.closed
		has := len(w.pending) > 0
		var batch []WatchEvent
		if has && !closed {
			batch = w.pending
			w.pending = nil
		}
		s.mu.Unlock()

		if closed {
			return
		}
		if !has {
			// Idle: wait for new work or cancellation. Selecting on done
			// prevents a goroutine leak when stopped while idle.
			select {
			case <-w.notify:
			case <-w.done:
				return
			}
			continue
		}
		for _, ev := range batch {
			select {
			case w.ch <- ev:
			case <-w.done:
				return
			}
		}
	}
}

// stopWatcher cancels a single watcher exactly once. The pump closes w.ch.
func (s *Store) stopWatcher(id uint64) {
	s.mu.Lock()
	w, ok := s.watchers[id]
	if ok {
		delete(s.watchers, id)
		s.closeWatcher(w)
	}
	s.mu.Unlock()
}

// Close cancels all watchers. The object data is left intact for final reads.
func (s *Store) Close() {
	s.mu.Lock()
	for id, w := range s.watchers {
		s.closeWatcher(w)
		delete(s.watchers, id)
	}
	s.mu.Unlock()
}

// stamp sets the object's resourceVersion from rv and returns it for chaining.
func stamp(obj Object, rv uint64) Object {
	obj.GetObjectMeta().ResourceVersion = fmt.Sprintf("%d", rv)
	return obj
}
