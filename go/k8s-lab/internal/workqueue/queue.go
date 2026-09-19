// Package workqueue implements the deduplicating work queue that every
// Kubernetes controller runs on — a miniature of
// k8s.io/client-go/util/workqueue.
//
// Why controllers need it (the core lesson of this package):
//
//   - Events are edge-triggered, reconciliation is level-triggered. A watch
//     event says "something changed"; the controller does not act on the event
//     itself. It enqueues the KEY of the affected object and reconciles later
//     from current state. If three events for one ReplicaSet arrive before the
//     worker gets to it, one reconcile handles all three.
//   - Deduplication. The same key is never queued twice: the dirty set absorbs
//     repeat adds. This collapses bursts and prevents hot-looping on one
//     object.
//   - Safe concurrent reconciliation. A key that is being processed is tracked
//     in the processing set; adds during processing mark it dirty but do not
//     requeue it, and Done() requeues it exactly once. Two workers therefore
//     never reconcile the same object simultaneously — that is the invariant
//     that keeps reconcile logic single-threaded per object without any
//     locking inside the controller.
//   - Requeue on error. A failed reconcile (e.g. a resourceVersion conflict)
//     is retried by simply adding the key again.
//
// The implementation mirrors client-go's algorithm state-for-state:
// two sets (dirty, processing) plus an ordered slice, guarded by a mutex and
// driven by a condition variable.
package workqueue

import "sync"

// Queue is a concurrency-safe, deduplicating FIFO of string keys.
type Queue struct {
	mu   sync.Mutex
	cond *sync.Cond

	// queue is the ordered backlog of keys ready to be handed to a worker.
	queue []string
	// dirty holds every key that needs processing, whether or not it is
	// currently with a worker. Add() dedupes through this set.
	dirty map[string]struct{}
	// processing holds keys currently checked out via Get() and not yet
	// Done(). A key here is NOT in queue; Done() moves it back if it was
	// re-added while being processed.
	processing map[string]struct{}

	shutdown bool
}

// New returns an empty Queue.
func New() *Queue {
	q := &Queue{
		dirty:      make(map[string]struct{}),
		processing: make(map[string]struct{}),
	}
	q.cond = sync.NewCond(&q.mu)
	return q
}

// Add marks key as needing processing.
//
// Semantics (identical to client-go):
//   - If the key is already dirty, this is a no-op (dedup).
//   - If the key is currently being processed, it becomes dirty but is not
//     appended to the queue — Done() will requeue it then. This guarantees a
//     key is never processed by two workers at once.
//   - Otherwise it is appended and a waiting worker is woken.
func (q *Queue) Add(key string) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.shutdown {
		return
	}
	if _, ok := q.dirty[key]; ok {
		return
	}
	q.dirty[key] = struct{}{}
	if _, ok := q.processing[key]; ok {
		// Being worked on right now; Done() will requeue it.
		return
	}
	q.queue = append(q.queue, key)
	q.cond.Signal()
}

// Get blocks until a key is available and checks it out. It returns
// shutdown=true (with an empty key) once ShutDown has been called and the
// backlog is drained. Every successful Get must be paired with Done.
func (q *Queue) Get() (key string, shutdown bool) {
	q.mu.Lock()
	defer q.mu.Unlock()

	for len(q.queue) == 0 && !q.shutdown {
		q.cond.Wait()
	}
	if len(q.queue) == 0 {
		return "", true // shutting down, nothing left
	}

	key = q.queue[0]
	q.queue = q.queue[1:]
	delete(q.dirty, key)
	q.processing[key] = struct{}{}
	return key, false
}

// Done marks a key as finished processing. If it was Add()ed again while being
// processed, it is requeued now — exactly once, preserving dedup.
func (q *Queue) Done(key string) {
	q.mu.Lock()
	defer q.mu.Unlock()

	delete(q.processing, key)
	if _, ok := q.dirty[key]; ok {
		q.queue = append(q.queue, key)
		q.cond.Signal()
	}
}

// Len returns the number of keys waiting (not those being processed).
func (q *Queue) Len() int {
	q.mu.Lock()
	defer q.mu.Unlock()
	return len(q.queue)
}

// ShutDown drains the queue semantics: blocked and future Get calls return
// shutdown=true once the current queue slice empties, and Add becomes a
// no-op. Workers use this to exit their loops.
func (q *Queue) ShutDown() {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.shutdown = true
	q.cond.Broadcast()
}

// ShuttingDown reports whether ShutDown has been called.
func (q *Queue) ShuttingDown() bool {
	q.mu.Lock()
	defer q.mu.Unlock()
	return q.shutdown
}
