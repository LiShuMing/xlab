package workqueue

import (
	"sync"
	"testing"
	"time"
)

// getWithTimeout calls Get in a goroutine so the test cannot hang forever.
func getWithTimeout(t *testing.T, q *Queue, d time.Duration) (string, bool, bool) {
	t.Helper()
	type result struct {
		key      string
		shutdown bool
	}
	res := make(chan result, 1)
	go func() {
		k, sd := q.Get()
		res <- result{k, sd}
	}()
	select {
	case r := <-res:
		return r.key, r.shutdown, true
	case <-time.After(d):
		return "", false, false
	}
}

func TestAddGetDone(t *testing.T) {
	q := New()
	q.Add("a")
	q.Add("b")

	if q.Len() != 2 {
		t.Fatalf("Len = %d, want 2", q.Len())
	}
	k, sd := q.Get()
	if sd || k != "a" {
		t.Errorf("Get = (%q, %v), want (a, false)", k, sd)
	}
	if q.Len() != 1 {
		t.Errorf("Len after Get = %d, want 1 (processing key leaves the queue)", q.Len())
	}
	q.Done("a")
	k, _ = q.Get()
	if k != "b" {
		t.Errorf("Get = %q, want b", k)
	}
	q.Done("b")
	if q.Len() != 0 {
		t.Errorf("Len = %d, want 0", q.Len())
	}
}

// TestDedup: adding the same key twice before processing queues it once.
func TestDedup(t *testing.T) {
	q := New()
	q.Add("a")
	q.Add("a")
	q.Add("a")
	if q.Len() != 1 {
		t.Fatalf("Len = %d, want 1 (duplicate adds collapse)", q.Len())
	}
}

// TestAddWhileProcessingRequeuesOnce is the central client-go invariant: a key
// checked out by a worker is not handed to another worker; if it is re-added
// during processing, Done() requeues it exactly once.
func TestAddWhileProcessingRequeuesOnce(t *testing.T) {
	q := New()
	q.Add("a")

	k, _ := q.Get() // "a" now processing
	if k != "a" {
		t.Fatalf("Get = %q, want a", k)
	}
	// Re-add while processing: must NOT be immediately available.
	q.Add("a")
	q.Add("a") // dedup again
	if q.Len() != 0 {
		t.Fatalf("Len = %d, want 0 while a is processing", q.Len())
	}
	if _, _, ok := getWithTimeout(t, q, 100*time.Millisecond); ok {
		t.Fatal("Get returned while key is processing; it must block")
	}
	// Done() requeues it exactly once.
	q.Done("a")
	if q.Len() != 1 {
		t.Fatalf("Len after Done = %d, want 1 (requeued once)", q.Len())
	}
	k, _ = q.Get()
	if k != "a" {
		t.Errorf("second Get = %q, want a", k)
	}
	q.Done("a")
}

// TestDoneWithoutReaddDoesNotRequeue: Done on a key that was not re-added
// during processing must not resurrect it.
func TestDoneWithoutReaddDoesNotRequeue(t *testing.T) {
	q := New()
	q.Add("a")
	q.Get()
	q.Done("a")
	if q.Len() != 0 {
		t.Errorf("Len = %d, want 0", q.Len())
	}
}

func TestShutDownUnblocksGet(t *testing.T) {
	q := New()
	go func() {
		time.Sleep(50 * time.Millisecond)
		q.ShutDown()
	}()
	k, sd := q.Get()
	if !sd || k != "" {
		t.Errorf("Get after ShutDown = (%q, %v), want (\"\", true)", k, sd)
	}
	if !q.ShuttingDown() {
		t.Error("ShuttingDown should be true")
	}
	// Add after shutdown is a no-op.
	q.Add("ignored")
	if q.Len() != 0 {
		t.Errorf("Len = %d, want 0 after shutdown Add", q.Len())
	}
}

// TestShutDownDrainsBacklog: Get keeps serving queued keys after ShutDown
// until they run out, then reports shutdown.
func TestShutDownDrainsBacklog(t *testing.T) {
	q := New()
	q.Add("a")
	q.Add("b")
	q.ShutDown()

	k, sd := q.Get()
	if sd || k != "a" {
		t.Errorf("Get = (%q, %v), want (a, false) — backlog must drain first", k, sd)
	}
	q.Done("a")
	k, sd = q.Get()
	if sd || k != "b" {
		t.Errorf("Get = (%q, %v), want (b, false)", k, sd)
	}
	q.Done("b")
	if _, sd = q.Get(); !sd {
		t.Error("Get on drained, shut-down queue should report shutdown")
	}
}

// TestConcurrentWorkersNeverShareKey exercises the processing-set invariant
// under parallelism: many workers pull keys, and no key is ever seen by two
// workers simultaneously.
func TestConcurrentWorkersNeverShareKey(t *testing.T) {
	q := New()
	const keys = 200
	for i := range keys {
		q.Add(keyName(i))
	}

	var mu sync.Mutex
	processingNow := map[string]bool{}
	processed := map[string]int{}

	var wg sync.WaitGroup
	for range 4 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				k, sd := q.Get()
				if sd {
					return
				}
				mu.Lock()
				if processingNow[k] {
					mu.Unlock()
					t.Errorf("key %q processed by two workers at once", k)
					q.ShutDown()
					return
				}
				processingNow[k] = true
				mu.Unlock()

				// Simulate work; re-add once to force a requeue.
				time.Sleep(time.Millisecond)

				mu.Lock()
				delete(processingNow, k)
				processed[k]++
				first := processed[k] == 1
				mu.Unlock()
				if first {
					q.Add(k) // each key reprocessed once more
				}
				q.Done(k)
			}
		}()
	}

	// Stop after every key has been processed twice.
	go func() {
		for {
			mu.Lock()
			done := true
			for i := range keys {
				if processed[keyName(i)] < 2 {
					done = false
					break
				}
			}
			mu.Unlock()
			if done {
				q.ShutDown()
				return
			}
			time.Sleep(5 * time.Millisecond)
		}
	}()

	waitGroupWithTimeout(t, &wg, 10*time.Second)
}

func waitGroupWithTimeout(t *testing.T, wg *sync.WaitGroup, d time.Duration) {
	t.Helper()
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	select {
	case <-done:
	case <-time.After(d):
		t.Fatal("workers did not finish in time")
	}
}

func keyName(i int) string {
	return string(rune('a'+i%26)) + string(rune('a'+i/26))
}
