package apiserver

import (
	"errors"
	"strconv"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// newTestServer returns a Server with a frozen clock so creationTimestamp is
// deterministic.
func newTestServer() *Server {
	s := New(store.New())
	fixed := time.Date(2026, 9, 19, 12, 0, 0, 0, time.UTC)
	s.now = func() time.Time { return fixed }
	return s
}

func newPod(name string) *apis.Pod {
	return &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: name},
		Spec:       apis.PodSpec{Image: "nginx"},
	}
}

func newRS(name string, replicas int32, match map[string]string) *apis.ReplicaSet {
	return &apis.ReplicaSet{
		ObjectMeta: apis.ObjectMeta{Name: name},
		Spec: apis.ReplicaSetSpec{
			Replicas: replicas,
			Selector: apis.LabelSelector{MatchLabels: match},
			Template: apis.PodTemplateSpec{
				ObjectMeta: apis.ObjectMeta{Labels: match},
				Spec:       apis.PodSpec{Image: "nginx"},
			},
		},
	}
}

// ---------------------------------------------------------------------------
// Defaulting
// ---------------------------------------------------------------------------

func TestCreateDefaults(t *testing.T) {
	a := newTestServer()
	got, err := a.Create("pods", newPod("web-1"))
	if err != nil {
		t.Fatalf("Create: %v", err)
	}
	meta := got.GetObjectMeta()
	tm := got.GetTypeMeta()

	if meta.Namespace != "default" {
		t.Errorf("Namespace = %q, want defaulted to \"default\"", meta.Namespace)
	}
	if meta.UID == "" {
		t.Error("UID should be defaulted")
	}
	if meta.CreationTimestamp.IsZero() {
		t.Error("CreationTimestamp should be defaulted")
	}
	if tm.Kind != "Pod" || tm.APIVersion != "v1" {
		t.Errorf("TypeMeta = {%s %s}, want {Pod v1}", tm.Kind, tm.APIVersion)
	}
	if meta.ResourceVersion == "" || meta.ResourceVersion == "0" {
		t.Errorf("ResourceVersion = %q, want a stamped value", meta.ResourceVersion)
	}
}

func TestCreateDefaultsDoNotMutateInput(t *testing.T) {
	a := newTestServer()
	in := newPod("web-1")
	if _, err := a.Create("pods", in); err != nil {
		t.Fatalf("Create: %v", err)
	}
	if in.Namespace != "" || in.UID != "" || !in.CreationTimestamp.IsZero() {
		t.Error("Create must not mutate the caller's object (defaulting happens on a copy)")
	}
}

func TestCreateTwoPodsGetDistinctUIDs(t *testing.T) {
	a := newTestServer()
	g1, err := a.Create("pods", newPod("web-1"))
	if err != nil {
		t.Fatalf("Create 1: %v", err)
	}
	g2, err := a.Create("pods", newPod("web-2"))
	if err != nil {
		t.Fatalf("Create 2: %v", err)
	}
	if g1.GetObjectMeta().UID == g2.GetObjectMeta().UID {
		t.Error("two objects must not share a UID")
	}
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

func TestCreateUnknownResource(t *testing.T) {
	a := newTestServer()
	if _, err := a.Create("deployments", newPod("x")); err == nil {
		t.Error("unknown resource should be rejected")
	}
	if _, err := a.Get("deployments", "default", "x"); err == nil {
		t.Error("Get on unknown resource should be rejected")
	}
	if _, err := a.List("deployments", "default"); err == nil {
		t.Error("List on unknown resource should be rejected")
	}
	if _, _, err := a.Watch("deployments", 0); err == nil {
		t.Error("Watch on unknown resource should be rejected")
	}
	if _, err := a.Delete("deployments", "default", "x"); err == nil {
		t.Error("Delete on unknown resource should be rejected")
	}
}

func TestCreateInvalidNames(t *testing.T) {
	a := newTestServer()
	bad := []string{
		"",      // empty
		"-web",  // starts with '-'
		"web-",  // ends with '-'
		"Web",   // uppercase
		"web_1", // underscore
		"web 1", // space
	}
	for _, name := range bad {
		if _, err := a.Create("pods", newPod(name)); err == nil {
			t.Errorf("Create with name %q should be rejected", name)
		}
	}
	// A valid DNS-ish name passes.
	if _, err := a.Create("pods", newPod("web-1.a")); err != nil {
		t.Errorf("valid name rejected: %v", err)
	}
}

func TestCreateReplicaSetValidation(t *testing.T) {
	a := newTestServer()
	// Negative replicas rejected.
	if _, err := a.Create("replicasets", newRS("bad", -1, map[string]string{"app": "web"})); err == nil {
		t.Error("negative replicas should be rejected")
	}
	// Empty selector rejected: it would adopt every pod in the namespace.
	if _, err := a.Create("replicasets", newRS("bad2", 1, nil)); err == nil {
		t.Error("empty selector should be rejected")
	}
	// Valid RS accepted.
	if _, err := a.Create("replicasets", newRS("web", 3, map[string]string{"app": "web"})); err != nil {
		t.Errorf("valid RS rejected: %v", err)
	}
}

// ---------------------------------------------------------------------------
// Update / identity protection / status subresource
// ---------------------------------------------------------------------------

func TestUpdatePreservesServerOwnedIdentity(t *testing.T) {
	a := newTestServer()
	created, err := a.Create("pods", newPod("web-1"))
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	// A hostile client tries to swap UID and creationTimestamp.
	tampered := created.DeepCopyObject().(*apis.Pod)
	tampered.UID = "forged"
	tampered.CreationTimestamp = time.Unix(0, 0)
	tampered.Spec.Image = "redis"

	rv := mustParseRV(t, created)
	updated, err := a.Update("pods", tampered, rv)
	if err != nil {
		t.Fatalf("Update: %v", err)
	}
	if updated.GetObjectMeta().UID != created.GetObjectMeta().UID {
		t.Error("Update must keep the server-assigned UID")
	}
	if !updated.GetObjectMeta().CreationTimestamp.Equal(created.GetObjectMeta().CreationTimestamp) {
		t.Error("Update must keep the server-assigned creationTimestamp")
	}
	if updated.(*apis.Pod).Spec.Image != "redis" {
		t.Error("Update must apply the client's spec change")
	}
}

func TestUpdateMissing(t *testing.T) {
	a := newTestServer()
	if _, err := a.Update("pods", newPod("nope"), 0); !errors.Is(err, store.ErrNotFound) {
		t.Errorf("Update missing err = %v, want ErrNotFound", err)
	}
}

func TestUpdateStatusOnlyTouchesStatus(t *testing.T) {
	a := newTestServer()
	rs, err := a.Create("replicasets", newRS("web", 3, map[string]string{"app": "web"}))
	if err != nil {
		t.Fatalf("Create: %v", err)
	}

	// The controller writes status; a concurrent user write changes spec.
	// UpdateStatus must pick up the fresh spec and apply only our status.
	clientCopy := rs.DeepCopyObject().(*apis.ReplicaSet)
	clientCopy.Status.Replicas = 3
	clientCopy.Status.ReadyReplicas = 2
	// Even if the client copy carries a mutated spec, UpdateStatus ignores it.
	clientCopy.Spec.Replicas = 999

	rv := mustParseRV(t, rs)
	updated, err := a.UpdateStatus("replicasets", clientCopy, rv)
	if err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	got := updated.(*apis.ReplicaSet)
	if got.Spec.Replicas != 3 {
		t.Errorf("Spec.Replicas = %d, want 3 (UpdateStatus must not apply client spec changes)", got.Spec.Replicas)
	}
	if got.Status.ReadyReplicas != 2 {
		t.Errorf("Status.ReadyReplicas = %d, want 2", got.Status.ReadyReplicas)
	}
}

func TestUpdateStatusWrongType(t *testing.T) {
	a := newTestServer()
	if _, err := a.Create("pods", newPod("web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	// Passing a ReplicaSet where a Pod lives must fail, not corrupt state.
	rs := newRS("web-1", 1, map[string]string{"app": "web"})
	if _, err := a.UpdateStatus("pods", rs, 0); err == nil {
		t.Error("UpdateStatus with wrong type should fail")
	}
}

func TestUpdateStatusMissing(t *testing.T) {
	a := newTestServer()
	if _, err := a.UpdateStatus("pods", newPod("nope"), 0); !errors.Is(err, store.ErrNotFound) {
		t.Errorf("UpdateStatus missing err = %v, want ErrNotFound", err)
	}
}

// ---------------------------------------------------------------------------
// Read paths and watch passthrough
// ---------------------------------------------------------------------------

func TestListAndGet(t *testing.T) {
	a := newTestServer()
	for _, name := range []string{"b", "a"} {
		if _, err := a.Create("pods", newPod(name)); err != nil {
			t.Fatalf("Create %s: %v", name, err)
		}
	}
	list, err := a.List("pods", "")
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("List len = %d, want 2", len(list))
	}
	if list[0].GetObjectMeta().Name != "a" {
		t.Errorf("List[0] = %q, want \"a\" (sorted)", list[0].GetObjectMeta().Name)
	}
	if _, err := a.Get("pods", "default", "a"); err != nil {
		t.Errorf("Get: %v", err)
	}
	if _, err := a.Get("pods", "default", "zzz"); !errors.Is(err, store.ErrNotFound) {
		t.Errorf("Get missing err = %v, want ErrNotFound", err)
	}
}

func TestDeleteThroughServer(t *testing.T) {
	a := newTestServer()
	if _, err := a.Create("pods", newPod("web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	if _, err := a.Delete("pods", "default", "web-1"); err != nil {
		t.Fatalf("Delete: %v", err)
	}
	if _, err := a.Get("pods", "default", "web-1"); !errors.Is(err, store.ErrNotFound) {
		t.Errorf("Get after Delete err = %v, want ErrNotFound", err)
	}
}

func TestWatchPassthrough(t *testing.T) {
	a := newTestServer()
	ch, stop, err := a.Watch("pods", 0)
	if err != nil {
		t.Fatalf("Watch: %v", err)
	}
	defer stop()

	if _, err := a.Create("pods", newPod("web-1")); err != nil {
		t.Fatalf("Create: %v", err)
	}
	select {
	case ev, ok := <-ch:
		if !ok {
			t.Fatal("watch channel closed")
		}
		if ev.Type != store.Added || ev.Key != "/pods/default/web-1" {
			t.Errorf("event = {%s %s}, want {ADDED /pods/default/web-1}", ev.Type, ev.Key)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("timed out waiting for watch event")
	}
}

func TestValidateNameTooLong(t *testing.T) {
	long := make([]byte, 254)
	for i := range long {
		long[i] = 'a'
	}
	if err := validateName(string(long)); err == nil {
		t.Error("254-char name should be rejected")
	}
}

// mustParseRV converts an object's resourceVersion string to uint64.
func mustParseRV(t *testing.T, obj apis.Object) uint64 {
	t.Helper()
	rv, err := strconv.ParseUint(obj.GetObjectMeta().ResourceVersion, 10, 64)
	if err != nil {
		t.Fatalf("bad resourceVersion %q: %v", obj.GetObjectMeta().ResourceVersion, err)
	}
	return rv
}
