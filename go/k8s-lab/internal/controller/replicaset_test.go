package controller

import (
	"context"
	"log"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// testEnv bundles a full mini control plane for controller tests.
type testEnv struct {
	api         *apiserver.Server
	rsInformer  *informer.Informer
	podInformer *informer.Informer
	ctrl        *ReplicaSetController
	cancel      context.CancelFunc
}

func newTestEnv(t *testing.T, opts ...envOption) *testEnv {
	t.Helper()
	cfg := envConfig{workers: 1}
	for _, o := range opts {
		o(&cfg)
	}

	api := apiserver.New(store.New())

	rsLW := informer.NewServerListWatch(api, "replicasets")
	podLW := informer.NewServerListWatch(api, "pods")
	rsInf := informer.New(rsLW)
	podInf := informer.New(podLW)

	ctrl := NewReplicaSetController(api, rsInf, podInf, log.New(testWriter{t}, "", 0))

	ctx, cancel := context.WithCancel(context.Background())
	go rsInf.Run(ctx)
	go podInf.Run(ctx)
	if cfg.workers > 0 {
		go ctrl.Run(ctx, cfg.workers)
	}

	rsInf.WaitForSync(ctx)
	podInf.WaitForSync(ctx)

	t.Cleanup(func() { cancel() })
	return &testEnv{api: api, rsInformer: rsInf, podInformer: podInf, ctrl: ctrl, cancel: cancel}
}

type envConfig struct{ workers int }
type envOption func(*envConfig)

// withoutWorkers starts informers but no reconcile workers, so a test can
// drive reconcile directly without racing the controller loop.
func withoutWorkers() envOption { return func(c *envConfig) { c.workers = 0 } }

// testWriter routes controller logs into t.Log.
type testWriter struct{ t *testing.T }

func (w testWriter) Write(p []byte) (int, error) {
	w.t.Log(string(p))
	return len(p), nil
}

func makeRS(name string, replicas int32, image string) *apis.ReplicaSet {
	labels := map[string]string{"app": name}
	return &apis.ReplicaSet{
		ObjectMeta: apis.ObjectMeta{Name: name, Namespace: "default"},
		Spec: apis.ReplicaSetSpec{
			Replicas: replicas,
			Selector: apis.LabelSelector{MatchLabels: labels},
			Template: apis.PodTemplateSpec{
				ObjectMeta: apis.ObjectMeta{Labels: labels},
				Spec:       apis.PodSpec{Image: image},
			},
		},
	}
}

// waitFor polls cond until true or the test times out.
func waitFor(t *testing.T, desc string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(2 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for %s", desc)
}

func podCount(env *testEnv) int {
	list, err := env.api.List("pods", "default")
	if err != nil {
		return -1
	}
	return len(list)
}

// TestScaleUpFromZero: creating an RS must materialise spec.replicas Pods,
// each labelled with the owner and templated from the pod template.
func TestScaleUpFromZero(t *testing.T) {
	env := newTestEnv(t)
	if _, err := env.api.Create("replicasets", makeRS("web", 3, "nginx:1.0")); err != nil {
		t.Fatalf("Create RS: %v", err)
	}

	waitFor(t, "3 pods created", func() bool { return podCount(env) == 3 })

	list, _ := env.api.List("pods", "default")
	for _, obj := range list {
		pod := obj.(*apis.Pod)
		if pod.Labels[OwnerLabel] != "web" {
			t.Errorf("pod %s missing owner label: %v", pod.Name, pod.Labels)
		}
		if pod.Spec.Image != "nginx:1.0" {
			t.Errorf("pod %s image = %q, want nginx:1.0 (template must propagate)", pod.Name, pod.Spec.Image)
		}
		if pod.Status.Phase != "" && pod.Status.Phase != apis.PodPending {
			t.Errorf("pod %s phase = %q, want empty/Pending (controller must not write pod status)", pod.Name, pod.Status.Phase)
		}
	}

	// Status is written by the controller: replicas == 3, ready == 0
	// (nothing simulates the kubelet here, so no pod is Running).
	waitFor(t, "RS status replicas=3", func() bool {
		rs, err := env.api.Get("replicasets", "default", "web")
		if err != nil {
			return false
		}
		return rs.(*apis.ReplicaSet).Status.Replicas == 3 &&
			rs.(*apis.ReplicaSet).Status.ReadyReplicas == 0
	})
}

// TestScaleDown: lowering spec.replicas must delete surplus pods, newest first.
func TestScaleDown(t *testing.T) {
	env := newTestEnv(t)
	rs := makeRS("web", 4, "nginx")
	if _, err := env.api.Create("replicasets", rs); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "4 pods", func() bool { return podCount(env) == 4 })

	// Scale to 2. The controller has written status since Create, so the
	// resourceVersion we got back is stale — re-read first. This retry-on-
	// conflict dance is exactly what optimistic concurrency demands of every
	// real client.
	scaleDown := func() error {
		cur, err := env.api.Get("replicasets", "default", "web")
		if err != nil {
			return err
		}
		updated := cur.DeepCopyObject().(*apis.ReplicaSet)
		updated.Spec.Replicas = 2
		rv := parseRV(cur.GetObjectMeta().ResourceVersion)
		_, err = env.api.Update("replicasets", updated, rv)
		return err
	}
	if err := scaleDown(); err != nil {
		t.Fatalf("scale down: %v", err)
	}
	waitFor(t, "2 pods after scale-down", func() bool { return podCount(env) == 2 })

	// The survivors must be the oldest ordinals (delete newest-first).
	list, _ := env.api.List("pods", "default")
	names := map[string]bool{}
	for _, obj := range list {
		names[obj.GetObjectMeta().Name] = true
	}
	if !names["web-0"] || !names["web-1"] {
		t.Errorf("surviving pods = %v, want web-0 and web-1", names)
	}
}

// TestSelfHealOnPodDelete is the level-triggered guarantee: deleting a pod
// behind the controller's back must be repaired without any special handling —
// the pod-delete event requeues the owner and reconcile recreates it.
func TestSelfHealOnPodDelete(t *testing.T) {
	env := newTestEnv(t)
	if _, err := env.api.Create("replicasets", makeRS("web", 3, "nginx")); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "3 pods", func() bool { return podCount(env) == 3 })

	// Kill one pod like a node failure would.
	list, _ := env.api.List("pods", "default")
	victim := list[0].GetObjectMeta().Name
	if _, err := env.api.Delete("pods", "default", victim); err != nil {
		t.Fatalf("Delete pod: %v", err)
	}

	waitFor(t, "back to 3 pods after delete", func() bool { return podCount(env) == 3 })

	// The replacement must be a NEW pod (fresh ordinal), not a resurrection
	// of the same name — same as real RS behaviour after owner-scoped naming.
	list2, _ := env.api.List("pods", "default")
	for _, obj := range list2 {
		if obj.GetObjectMeta().Name == victim {
			// It is legitimate for the ordinal to be reused only if the
			// controller's sequence wrapped; with podSeq it never does.
			t.Errorf("pod %q was recreated with the same name; expected a fresh ordinal", victim)
		}
	}
}

// TestRSDeleteStopsReconcile: deleting the RS must stop reconcile activity;
// orphaned pods are tolerated in the lab (no GC controller).
func TestRSDeleteStopsReconcile(t *testing.T) {
	env := newTestEnv(t)
	if _, err := env.api.Create("replicasets", makeRS("web", 2, "nginx")); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "2 pods", func() bool { return podCount(env) == 2 })

	if _, err := env.api.Delete("replicasets", "default", "web"); err != nil {
		t.Fatalf("Delete RS: %v", err)
	}
	waitFor(t, "RS gone from cache", func() bool {
		return env.rsInformer.Store().Get("default/web") == nil
	})

	// Deleting an orphaned pod must not recreate it (its owner is gone).
	list, _ := env.api.List("pods", "default")
	orphan := list[0].GetObjectMeta().Name
	if _, err := env.api.Delete("pods", "default", orphan); err != nil {
		t.Fatalf("Delete orphan: %v", err)
	}
	waitFor(t, "orphan count drops to 1", func() bool { return podCount(env) == 1 })
	time.Sleep(200 * time.Millisecond)
	if got := podCount(env); got != 1 {
		t.Errorf("pod count = %d after orphan delete, want 1 (RS is gone, nothing may recreate)", got)
	}
}

// TestTwoReplicaSetsCoexist: two RS with different selectors must each
// converge independently.
func TestTwoReplicaSetsCoexist(t *testing.T) {
	env := newTestEnv(t)
	if _, err := env.api.Create("replicasets", makeRS("web", 2, "nginx")); err != nil {
		t.Fatalf("Create web: %v", err)
	}
	if _, err := env.api.Create("replicasets", makeRS("cache", 3, "redis")); err != nil {
		t.Fatalf("Create cache: %v", err)
	}
	waitFor(t, "5 total pods", func() bool { return podCount(env) == 5 })

	list, _ := env.api.List("pods", "default")
	var web, cache int
	for _, obj := range list {
		switch obj.GetObjectMeta().Labels[OwnerLabel] {
		case "web":
			web++
		case "cache":
			cache++
		}
	}
	if web != 2 || cache != 3 {
		t.Errorf("ownership split = web:%d cache:%d, want 2:3", web, cache)
	}
}

// TestReconcileIdempotent verifies the defining property of level-triggered
// control: reconciling an already-converged key does nothing observable.
// Workers are disabled so only this test calls reconcile.
func TestReconcileIdempotent(t *testing.T) {
	env := newTestEnv(t, withoutWorkers())
	if _, err := env.api.Create("replicasets", makeRS("web", 2, "nginx")); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "RS visible in informer cache", func() bool {
		return env.rsInformer.Store().Get("default/web") != nil
	})

	// Drive reconcile by hand. One pass creates ALL missing pods (owned=0 ->
	// desired=2). We then wait for both to reach the pod cache before the
	// next pass. This ordering is what the event-driven loop gets for free:
	// the informer upserts into its cache BEFORE notifying handlers, so a
	// pod-Add that requeues the owner guarantees the owner's next reconcile
	// already sees that pod. Over-provisioning is impossible for that reason.
	if err := env.ctrl.reconcile(context.Background(), "default/web"); err != nil {
		t.Fatalf("reconcile: %v", err)
	}
	waitFor(t, "both pods visible in cache", func() bool { return env.podInformer.Store().Len() >= 2 })
	if got := podCount(env); got != 2 {
		t.Fatalf("pod count = %d, want 2", got)
	}

	// Status catch-up: the RS status is still {0,0} while the world holds 2
	// pods, so reconcile must eventually write it once. Expectations may
	// briefly block a pass (pod Adds still arriving), so drive reconciles in
	// a bounded loop until the written status shows up in the RS cache.
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if err := env.ctrl.reconcile(context.Background(), "default/web"); err != nil {
			t.Fatalf("status reconcile: %v", err)
		}
		obj := env.rsInformer.Store().Get("default/web")
		if obj != nil && obj.(*apis.ReplicaSet).Status.Replicas == 2 {
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	waitFor(t, "status visible in RS cache", func() bool {
		obj := env.rsInformer.Store().Get("default/web")
		return obj != nil && obj.(*apis.ReplicaSet).Status.Replicas == 2
	})

	// Now the world is fully converged. Five more reconciles must change
	// nothing — not the pod count, and (thanks to write-status-only-on-
	// change) not even the RS resourceVersion. A true no-op.
	rsBefore, err := env.api.Get("replicasets", "default", "web")
	if err != nil {
		t.Fatalf("Get RS: %v", err)
	}
	rvBefore := rsBefore.GetObjectMeta().ResourceVersion
	for range 5 {
		if err := env.ctrl.reconcile(context.Background(), "default/web"); err != nil {
			t.Fatalf("idempotent reconcile: %v", err)
		}
	}
	if got := podCount(env); got != 2 {
		t.Errorf("pod count = %d after repeated reconciles, want 2", got)
	}
	rsAfter, err := env.api.Get("replicasets", "default", "web")
	if err != nil {
		t.Fatalf("Get RS: %v", err)
	}
	if rsAfter.GetObjectMeta().ResourceVersion != rvBefore {
		t.Errorf("resourceVersion moved (%s -> %s) on converged reconciles; "+
			"status must only be written when it changes",
			rvBefore, rsAfter.GetObjectMeta().ResourceVersion)
	}
	if got := rsAfter.(*apis.ReplicaSet).Status.Replicas; got != 2 {
		t.Errorf("Status.Replicas = %d, want 2", got)
	}
}

// TestReconcileSkipsWhileExpectationsPending is the over-provisioning guard:
// reconcile must create nothing while previously issued creations are still
// unobserved (cache lag), and resume once they are observed.
//
// Wiring is manual so the test controls WHEN the pod informer observes: the
// RS informer runs, but the pod informer is only started mid-test. Until it
// runs, no Pod Add events fire, so expectations set by reconcile stay pending
// — precisely the cache-lag window that must not trigger double creation.
func TestReconcileSkipsWhileExpectationsPending(t *testing.T) {
	api := apiserver.New(store.New())
	rsInf := informer.New(informer.NewServerListWatch(api, "replicasets"))
	podInf := informer.New(informer.NewServerListWatch(api, "pods"))
	ctrl := NewReplicaSetController(api, rsInf, podInf, nil)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go rsInf.Run(ctx)
	// podInf deliberately NOT started yet.
	rsInf.WaitForSync(ctx)

	if _, err := api.Create("replicasets", makeRS("web", 3, "nginx")); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "RS in cache", func() bool { return rsInf.Store().Get("default/web") != nil })

	key := "default/web"
	podCount := func() int {
		list, err := api.List("pods", "default")
		if err != nil {
			return -1
		}
		return len(list)
	}

	// Pass 1 issues 3 creations and records the expectation.
	if err := ctrl.reconcile(ctx, key); err != nil {
		t.Fatalf("reconcile 1: %v", err)
	}
	if ctrl.exp.satisfied(key) {
		t.Fatal("expectations should be pending right after creating pods")
	}
	if got := podCount(); got != 3 {
		t.Fatalf("pod count = %d, want 3", got)
	}

	// Pass 2 fires while expectations are pending — the cache-lag window.
	// It must be a no-op: creating again here is exactly the over-
	// provisioning storm expectations exist to prevent.
	for range 3 {
		if err := ctrl.reconcile(ctx, key); err != nil {
			t.Fatalf("reconcile 2: %v", err)
		}
	}
	if got := podCount(); got != 3 {
		t.Errorf("pod count = %d after reconciles with pending expectations, want 3 (must not double-create)", got)
	}

	// Now start the pod informer. Its initial LIST seeds the cache and
	// delivers OnAdd for the 3 pods, which the handlers record as observed
	// creations — expectations become satisfied the realistic way.
	go podInf.Run(ctx)
	podInf.WaitForSync(ctx)
	waitFor(t, "expectations satisfied by pod Adds", func() bool { return ctrl.exp.satisfied(key) })

	// Pass 3 proceeds with an up-to-date cache and finds the world
	// converged: no new pods.
	if err := ctrl.reconcile(ctx, key); err != nil {
		t.Fatalf("reconcile 3: %v", err)
	}
	if got := podCount(); got != 3 {
		t.Errorf("pod count = %d, want 3 (stable once expectations satisfied)", got)
	}
}

// TestExpectationsCounters covers the counter semantics directly, including
// the floor-at-zero guards against stray observations.
func TestExpectationsCounters(t *testing.T) {
	e := newExpectations()
	key := "default/web"

	if !e.satisfied(key) {
		t.Error("fresh expectations should be satisfied")
	}

	e.expectCreations(key, 2)
	if e.satisfied(key) {
		t.Error("pending creations should not be satisfied")
	}
	e.creationObserved(key)
	if e.satisfied(key) {
		t.Error("one of two creations still pending")
	}
	e.creationObserved(key)
	if !e.satisfied(key) {
		t.Error("all creations observed; should be satisfied")
	}
	// Stray observation must not go negative and unsatisfy.
	e.creationObserved(key)
	if !e.satisfied(key) {
		t.Error("extra creationObserved must be floored at zero")
	}

	e.expectDeletions(key, 1)
	if e.satisfied(key) {
		t.Error("pending deletion should not be satisfied")
	}
	e.deletionObserved(key)
	e.deletionObserved(key) // stray, floored
	if !e.satisfied(key) {
		t.Error("deletions observed; should be satisfied")
	}
}

// TestMalformedKey: reconcile must reject a key without a namespace segment.
func TestMalformedKey(t *testing.T) {
	env := newTestEnv(t)
	if err := env.ctrl.reconcile(context.Background(), "just-a-name"); err == nil {
		t.Error("reconcile with malformed key should fail")
	}
}

// TestParseRV covers the hand-rolled parser including garbage tolerance.
func TestParseRV(t *testing.T) {
	cases := map[string]uint64{
		"0":     0,
		"42":    42,
		"99999": 99999,
		"":      0,
		"abc":   0,
		"12x":   0,
	}
	for in, want := range cases {
		if got := parseRV(in); got != want {
			t.Errorf("parseRV(%q) = %d, want %d", in, got, want)
		}
	}
}

func TestSplitKey(t *testing.T) {
	ns, name, err := splitKey("kube-system/core-dns")
	if err != nil || ns != "kube-system" || name != "core-dns" {
		t.Errorf("splitKey = (%q,%q,%v)", ns, name, err)
	}
	if _, _, err := splitKey("noseparator"); err == nil {
		t.Error("splitKey should reject a key without /")
	}
}

func TestOwnerKeyOf(t *testing.T) {
	pod := &apis.Pod{ObjectMeta: apis.ObjectMeta{
		Name: "web-0", Namespace: "default",
		Labels: map[string]string{OwnerLabel: "web"},
	}}
	if got := ownerKeyOf(pod); got != "default/web" {
		t.Errorf("ownerKeyOf = %q, want default/web", got)
	}
}
