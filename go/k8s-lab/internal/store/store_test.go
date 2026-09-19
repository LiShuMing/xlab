package store

import (
	"errors"
	"fmt"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
)

// newPod builds a minimal Pod for tests.
func newPod(ns, name string) *apis.Pod {
	return &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: name, Namespace: ns},
		Spec:       apis.PodSpec{Image: "nginx"},
	}
}

func podKey(ns, name string) string { return apis.Key("pods", ns, name) }

// recv waits for one event on ch or fails the test after a timeout.
func recv(t *testing.T, ch <-chan WatchEvent) WatchEvent {
	t.Helper()
	select {
	case ev, ok := <-ch:
		if !ok {
			t.Fatal("watch channel closed unexpectedly")
		}
		return ev
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for watch event")
	}
	return WatchEvent{}
}

// expectClosed drains the watch channel until it reports closure. A closed
// channel still yields its buffered events first, so draining is required
// before the close can be observed. Returns the number of drained events.
func expectClosed(t *testing.T, ch <-chan WatchEvent) int {
	t.Helper()
	deadline := time.After(2 * time.Second)
	drained := 0
	for {
		select {
		case _, ok := <-ch:
			if !ok {
				return drained
			}
			drained++
		case <-deadline:
			t.Fatal("timed out waiting for channel close")
		}
	}
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

func TestCreateGetRoundTrip(t *testing.T) {
	s := New()
	key := podKey("default", "web-1")
	created, err := s.Create(key, newPod("default", "web-1"))
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	if got := created.GetObjectMeta().ResourceVersion; got != "2" {
		t.Errorf("ResourceVersion = %q, want %q (revision starts at 1, first write bumps to 2)", got, "2")
	}

	got, err := s.Get(key)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if got.GetObjectMeta().Name != "web-1" {
		t.Errorf("Name = %q, want web-1", got.GetObjectMeta().Name)
	}
}

func TestCreateDuplicateFails(t *testing.T) {
	s := New()
	key := podKey("default", "web-1")
	if _, err := s.Create(key, newPod("default", "web-1")); err != nil {
		t.Fatalf("first Create: %v", err)
	}
	if _, err := s.Create(key, newPod("default", "web-1")); !errors.Is(err, ErrAlreadyExists) {
		t.Errorf("second Create err = %v, want ErrAlreadyExists", err)
	}
}

func TestCreateEmptyKeyFails(t *testing.T) {
	s := New()
	if _, err := s.Create("", newPod("default", "x")); err == nil {
		t.Error("Create with empty key should fail")
	}
}

func TestGetMissing(t *testing.T) {
	s := New()
	if _, err := s.Get(podKey("default", "nope")); !errors.Is(err, ErrNotFound) {
		t.Errorf("Get missing err = %v, want ErrNotFound", err)
	}
}

func TestUpdateOptimisticConcurrency(t *testing.T) {
	s := New()
	key := podKey("default", "web-1")
	created, err := s.Create(key, newPod("default", "web-1"))
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	// Stale write: pretend another writer already bumped the revision.
	stale := created.DeepCopyObject().(*apis.Pod)
	_, err = s.Update(key, stale, 999)
	if !errors.Is(err, ErrConflict) {
		t.Errorf("stale Update err = %v, want ErrConflict", err)
	}

	// Correct write with the current resourceVersion succeeds.
	next := created.DeepCopyObject().(*apis.Pod)
	next.Status.Phase = apis.PodRunning
	updated, err := s.Update(key, next, 2)
	if err != nil {
		t.Fatalf("Update: %v", err)
	}
	if rv := updated.GetObjectMeta().ResourceVersion; rv == "2" {
		t.Error("Update must bump resourceVersion")
	}

	// Blind write (expected=0) skips the check, modelling a status subresource.
	blind := updated.DeepCopyObject().(*apis.Pod)
	blind.Status.Phase = apis.PodSucceeded
	if _, err := s.Update(key, blind, 0); err != nil {
		t.Fatalf("blind Update: %v", err)
	}
}

func TestUpdateMissing(t *testing.T) {
	s := New()
	_, err := s.Update(podKey("default", "nope"), newPod("default", "nope"), 0)
	if !errors.Is(err, ErrNotFound) {
		t.Errorf("Update missing err = %v, want ErrNotFound", err)
	}
}

func TestDelete(t *testing.T) {
	s := New()
	key := podKey("default", "web-1")
	if _, err := s.Create(key, newPod("default", "web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	deleted, err := s.Delete(key)
	if err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if deleted.GetObjectMeta().Name != "web-1" {
		t.Errorf("Delete returned %q, want web-1", deleted.GetObjectMeta().Name)
	}
	if _, err := s.Get(key); !errors.Is(err, ErrNotFound) {
		t.Errorf("Get after Delete err = %v, want ErrNotFound", err)
	}
	if _, err := s.Delete(key); !errors.Is(err, ErrNotFound) {
		t.Errorf("double Delete err = %v, want ErrNotFound", err)
	}
}

func TestListPrefixAndOrder(t *testing.T) {
	s := New()
	for _, name := range []string{"c", "a", "b"} {
		if _, err := s.Create(podKey("default", name), newPod("default", name)); err != nil {
			t.Fatalf("Create %s: %v", name, err)
		}
	}
	// An object in another resource must not leak into the pods list.
	rs := &apis.ReplicaSet{ObjectMeta: apis.ObjectMeta{Name: "rs-1", Namespace: "default"}}
	if _, err := s.Create(apis.Key("replicasets", "default", "rs-1"), rs); err != nil {
		t.Fatalf("Create rs: %v", err)
	}

	got := s.List("/pods/default/")
	if len(got) != 3 {
		t.Fatalf("List len = %d, want 3", len(got))
	}
	for i, want := range []string{"a", "b", "c"} {
		if name := got[i].GetObjectMeta().Name; name != want {
			t.Errorf("List[%d] = %q, want %q (keys must be sorted)", i, name, want)
		}
	}
	if all := s.List("/"); len(all) != 4 {
		t.Errorf("List(/) len = %d, want 4", len(all))
	}
}

// TestStoreIsolationFromCallerMutation verifies the deep-copy contract: after
// Create, mutating the object the caller passed in must not change what Get
// returns, and mutating what Get returns must not change store state.
func TestStoreIsolationFromCallerMutation(t *testing.T) {
	s := New()
	key := podKey("default", "web-1")
	in := newPod("default", "web-1")
	if _, err := s.Create(key, in); err != nil {
		t.Fatalf("Create: %v", err)
	}
	in.Spec.Image = "mutated-after-create"

	out, err := s.Get(key)
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	if img := out.(*apis.Pod).Spec.Image; img != "nginx" {
		t.Errorf("Image = %q, want nginx (store must not alias caller objects)", img)
	}

	out.(*apis.Pod).Spec.Image = "mutated-after-get"
	again, _ := s.Get(key)
	if img := again.(*apis.Pod).Spec.Image; img != "nginx" {
		t.Errorf("Image = %q after mutating Get result, want nginx (Get must return copies)", img)
	}
}

// ---------------------------------------------------------------------------
// Revision / MVCC
// ---------------------------------------------------------------------------

func TestRevisionMonotonic(t *testing.T) {
	s := New()
	if rv := s.Revision(); rv != 1 {
		t.Errorf("initial Revision = %d, want 1", rv)
	}
	key := podKey("default", "web-1")
	if _, err := s.Create(key, newPod("default", "web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	after := s.Revision()
	if after <= 1 {
		t.Errorf("Revision after Create = %d, want > 1", after)
	}
	// A failed write must not consume a revision.
	if _, err := s.Create(key, newPod("default", "web-1")); err == nil {
		t.Fatal("duplicate Create should fail")
	}
	if rv := s.Revision(); rv != after {
		t.Errorf("Revision changed on failed write: %d -> %d", after, rv)
	}
}

// ---------------------------------------------------------------------------
// Watch
// ---------------------------------------------------------------------------

func TestWatchLiveEvents(t *testing.T) {
	s := New()
	defer s.Close()
	ch, stop := s.Watch("/pods/", 0)
	defer stop()

	key := podKey("default", "web-1")
	if _, err := s.Create(key, newPod("default", "web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	ev := recv(t, ch)
	if ev.Type != Added || ev.Key != key {
		t.Errorf("event = {%s %s}, want {ADDED %s}", ev.Type, ev.Key, key)
	}

	pod, _ := s.Get(key)
	pod.(*apis.Pod).Status.Phase = apis.PodRunning
	if _, err := s.Update(key, pod, 0); err != nil {
		t.Fatalf("Update: %v", err)
	}
	if ev := recv(t, ch); ev.Type != Modified {
		t.Errorf("event type = %s, want MODIFIED", ev.Type)
	}

	if _, err := s.Delete(key); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if ev := recv(t, ch); ev.Type != Deleted {
		t.Errorf("event type = %s, want DELETED", ev.Type)
	}
}

func TestWatchPrefixFiltering(t *testing.T) {
	s := New()
	defer s.Close()
	ch, stop := s.Watch("/pods/", 0)
	defer stop()

	rs := &apis.ReplicaSet{ObjectMeta: apis.ObjectMeta{Name: "rs-1", Namespace: "default"}}
	if _, err := s.Create(apis.Key("replicasets", "default", "rs-1"), rs); err != nil {
		t.Fatalf("Create rs: %v", err)
	}
	if _, err := s.Create(podKey("default", "web-1"), newPod("default", "web-1")); err != nil {
		t.Fatalf("Create pod: %v", err)
	}

	// The only event the pods watcher should see is the pod, not the rs.
	ev := recv(t, ch)
	if ev.Key != podKey("default", "web-1") {
		t.Errorf("event key = %s, want the pod key (prefix filter must exclude replicasets)", ev.Key)
	}
	select {
	case extra := <-ch:
		t.Errorf("unexpected extra event: %+v", extra)
	case <-time.After(100 * time.Millisecond):
	}
}

// TestWatchResumeFromResourceVersion is the core informer contract: LIST, note
// the revision, WATCH from it, and miss nothing that happened in between.
func TestWatchResumeFromResourceVersion(t *testing.T) {
	s := New()
	defer s.Close()

	// Seed some history.
	for i := range 3 {
		name := fmt.Sprintf("web-%d", i)
		if _, err := s.Create(podKey("default", name), newPod("default", name)); err != nil {
			t.Fatalf("Create %s: %v", name, err)
		}
	}
	seeded := s.Revision()

	// Resume from the seeded revision: the 3 existing pods must NOT replay...
	ch, stop := s.Watch("/pods/", seeded)
	defer stop()
	// ...but a write that happens now MUST arrive.
	if _, err := s.Create(podKey("default", "new"), newPod("default", "new")); err != nil {
		t.Fatalf("Create new: %v", err)
	}
	ev := recv(t, ch)
	if ev.Key != podKey("default", "new") {
		t.Errorf("first resumed event key = %s, want the new pod", ev.Key)
	}
	if ev.ResourceVersion <= seeded {
		t.Errorf("resumed event rv = %d, want > %d", ev.ResourceVersion, seeded)
	}

	// Resuming from revision 1 (before the seeds) replays retained history.
	ch2, stop2 := s.Watch("/pods/", 1)
	defer stop2()
	seen := map[string]bool{}
	for range 4 { // web-0..web-2 + new
		seen[recv(t, ch2).Key] = true
	}
	for _, name := range []string{"web-0", "web-1", "web-2", "new"} {
		if !seen[podKey("default", name)] {
			t.Errorf("replay missed %s", name)
		}
	}
}

func TestWatchStopClosesChannel(t *testing.T) {
	s := New()
	defer s.Close()
	ch, stop := s.Watch("/pods/", 0)
	stop()
	expectClosed(t, ch)
	// stop is idempotent.
	stop()
}

func TestStoreCloseCancelsWatchers(t *testing.T) {
	s := New()
	ch, _ := s.Watch("/pods/", 0)
	s.Close()
	expectClosed(t, ch)
	// Data survives Close for final reads.
	if _, err := s.Create(podKey("default", "x"), newPod("default", "x")); err != nil {
		t.Fatalf("Create after Close: %v", err)
	}
	if _, err := s.Get(podKey("default", "x")); err != nil {
		t.Fatalf("Get after Close: %v", err)
	}
}

// TestWatchEventLogEviction exercises the bounded replay ring: once more than
// maxEvents accumulate, the oldest events are gone and resuming from before
// the window yields nothing for them (the informer must relist — exactly the
// etcd compaction contract).
func TestWatchEventLogEviction(t *testing.T) {
	s := New()
	s.maxEvents = 8
	defer s.Close()

	for i := range 10 {
		name := fmt.Sprintf("p-%02d", i)
		if _, err := s.Create(podKey("default", name), newPod("default", name)); err != nil {
			t.Fatalf("Create %s: %v", name, err)
		}
	}
	// Resume from revision 1: only the last 8 events survive in the ring.
	ch, stop := s.Watch("/pods/", 1)
	defer stop()

	count := 0
	for {
		select {
		case ev := <-ch:
			count++
			_ = ev
		case <-time.After(200 * time.Millisecond):
		}
		if count > 0 {
			break
		}
	}
	// Drain any remaining replayed events.
	for {
		select {
		case <-ch:
			count++
			continue
		case <-time.After(200 * time.Millisecond):
		}
		break
	}
	if count != 8 {
		t.Errorf("replayed %d events, want 8 (ring must evict oldest)", count)
	}
}

// TestWatchSlowConsumerForceClosed verifies the slow-consumer protection: a
// watcher that never drains accumulates pending past maxPending and is
// force-closed (channel closes), which is what makes an informer relist.
func TestWatchSlowConsumerForceClosed(t *testing.T) {
	s := New()
	defer s.Close()
	ch, _ := s.Watch("/pods/", 0)
	// Never read from ch. Flood writes: ch holds 64, pump holds the batch,
	// pending overflows at maxPending+1 and the watcher is force-closed.
	for i := range maxPending + 200 {
		name := fmt.Sprintf("p-%05d", i)
		if _, err := s.Create(podKey("default", name), newPod("default", name)); err != nil {
			t.Fatalf("Create %s: %v", name, err)
		}
	}
	expectClosed(t, ch)

	// The store must still be fully usable for other watchers afterwards.
	ch2, stop2 := s.Watch("/pods/", s.Revision())
	defer stop2()
	if _, err := s.Create(podKey("default", "after"), newPod("default", "after")); err != nil {
		t.Fatalf("Create after overflow: %v", err)
	}
	if ev := recv(t, ch2); ev.Key != podKey("default", "after") {
		t.Errorf("post-overflow watch got key %s, want the new pod", ev.Key)
	}
}

// TestConcurrentWritesAndWatchers hammers the store from many goroutines with
// the race detector on (go test -race) to shake out lock/ordering bugs.
func TestConcurrentWritesAndWatchers(t *testing.T) {
	s := New()
	defer s.Close()

	const writers = 8
	const perWriter = 50

	// Start a watcher that must see every event in non-decreasing rv order.
	ch, stop := s.Watch("/pods/", 0)
	defer stop()

	done := make(chan struct{})
	go func() {
		var last uint64
		for ev := range ch {
			if ev.ResourceVersion < last {
				t.Errorf("watch delivered rv %d after %d (must be ordered)", ev.ResourceVersion, last)
				return
			}
			last = ev.ResourceVersion
		}
		close(done)
	}()

	for w := range writers {
		go func(w int) {
			for i := range perWriter {
				name := fmt.Sprintf("w%d-p%d", w, i)
				key := podKey("default", name)
				if _, err := s.Create(key, newPod("default", name)); err != nil {
					t.Errorf("Create %s: %v", name, err)
					return
				}
			}
		}(w)
	}

	// Wait for all writes, then stop the watcher; the reader goroutine must
	// observe exactly writers*perWriter events before the channel closes.
	time.Sleep(300 * time.Millisecond)
	stop()
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("watcher goroutine did not finish")
	}

	if got := len(s.List("/pods/default/")); got != writers*perWriter {
		t.Errorf("store holds %d pods, want %d", got, writers*perWriter)
	}
}
