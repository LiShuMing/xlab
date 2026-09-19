package kubelet

import (
	"context"
	"log"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/controller"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// waitFor polls cond until true or timeout.
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

// fullStack builds apiserver + informers + RS controller + kubelet, the whole
// mini control plane, wired like cmd/demo.
func fullStack(t *testing.T, startup time.Duration) (*apiserver.Server, *controller.ReplicaSetController, *Kubelet, context.CancelFunc) {
	t.Helper()
	api := apiserver.New(store.New())

	rsInf := informer.New(informer.NewServerListWatch(api, "replicasets"))
	podInf := informer.New(informer.NewServerListWatch(api, "pods"))

	ctrl := controller.NewReplicaSetController(api, rsInf, podInf, nil)
	k := New(api, podInf, "node-1", WithStartupDelay(startup), WithLogger(log.New(testWriter{t}, "", 0)))

	ctx, cancel := context.WithCancel(context.Background())
	go rsInf.Run(ctx)
	go podInf.Run(ctx)
	go ctrl.Run(ctx, 1)
	go k.Run(ctx)
	rsInf.WaitForSync(ctx)
	podInf.WaitForSync(ctx)

	t.Cleanup(cancel)
	return api, ctrl, k, cancel
}

type testWriter struct{ t *testing.T }

func (w testWriter) Write(p []byte) (int, error) {
	w.t.Log(string(p))
	return len(p), nil
}

func makeRS(name string, replicas int32) *apis.ReplicaSet {
	labels := map[string]string{"app": name}
	return &apis.ReplicaSet{
		ObjectMeta: apis.ObjectMeta{Name: name, Namespace: "default"},
		Spec: apis.ReplicaSetSpec{
			Replicas: replicas,
			Selector: apis.LabelSelector{MatchLabels: labels},
			Template: apis.PodTemplateSpec{
				ObjectMeta: apis.ObjectMeta{Labels: labels},
				Spec:       apis.PodSpec{Image: "nginx"},
			},
		},
	}
}

// TestPendingToRunning is the kubelet's core job: a Pod born Pending ends up
// Running, and only the kubelet wrote that transition.
func TestPendingToRunning(t *testing.T) {
	api, _, k, _ := fullStack(t, 0)

	pod := &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: "solo", Namespace: "default"},
		Spec:       apis.PodSpec{Image: "nginx"},
	}
	if _, err := api.Create("pods", pod); err != nil {
		t.Fatalf("Create pod: %v", err)
	}

	waitFor(t, "kubelet to start the pod", func() bool { return k.Started() == 1 })

	got, err := api.Get("pods", "default", "solo")
	if err != nil {
		t.Fatalf("Get: %v", err)
	}
	gotPod := got.(*apis.Pod)
	if gotPod.Status.Phase != apis.PodRunning {
		t.Errorf("Phase = %q, want Running", gotPod.Status.Phase)
	}
	if gotPod.Spec.NodeName != "node-1" {
		t.Errorf("NodeName = %q, want node-1 (kubelet simulates the bind)", gotPod.Spec.NodeName)
	}
}

// TestStartupDelayKeepsPodPending: with a nonzero delay the Pod must still be
// Pending before the kubelet finishes "pulling the image".
func TestStartupDelayKeepsPodPending(t *testing.T) {
	api, _, _, _ := fullStack(t, 300*time.Millisecond)

	pod := &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: "slow", Namespace: "default"},
		Spec:       apis.PodSpec{Image: "big-image"},
	}
	if _, err := api.Create("pods", pod); err != nil {
		t.Fatalf("Create pod: %v", err)
	}

	// Give the informer time to observe it but not the full startup delay.
	time.Sleep(100 * time.Millisecond)
	got, _ := api.Get("pods", "default", "slow")
	if phase := got.(*apis.Pod).Status.Phase; phase == apis.PodRunning {
		t.Error("pod is Running before the startup delay elapsed")
	}

	waitFor(t, "pod Running after delay", func() bool {
		g, err := api.Get("pods", "default", "slow")
		return err == nil && g.(*apis.Pod).Status.Phase == apis.PodRunning
	})
}

// TestFullClosedLoop is the end-to-end story the lab exists to tell:
// declare desired state -> controller creates pods -> kubelet runs them ->
// controller status reflects readyReplicas. Expected drives actual through
// the whole chain, with no component touching another's fields.
func TestFullClosedLoop(t *testing.T) {
	api, _, _, _ := fullStack(t, 0)

	if _, err := api.Create("replicasets", makeRS("web", 3)); err != nil {
		t.Fatalf("Create RS: %v", err)
	}

	// Eventually: 3 pods, all Running, RS status says replicas=3, ready=3.
	waitFor(t, "full convergence: 3 running replicas", func() bool {
		list, err := api.List("pods", "default")
		if err != nil || len(list) != 3 {
			return false
		}
		for _, obj := range list {
			p := obj.(*apis.Pod)
			if p.Status.Phase != apis.PodRunning {
				return false
			}
			if p.Spec.NodeName != "node-1" {
				return false
			}
		}
		rs, err := api.Get("replicasets", "default", "web")
		if err != nil {
			return false
		}
		st := rs.(*apis.ReplicaSet).Status
		return st.Replicas == 3 && st.ReadyReplicas == 3
	})
}

// TestFullClosedLoopSelfHeal: kill a running pod; the whole loop must restore
// it — controller recreates, kubelet runs it, status re-converges.
func TestFullClosedLoopSelfHeal(t *testing.T) {
	api, _, _, _ := fullStack(t, 0)

	if _, err := api.Create("replicasets", makeRS("web", 2)); err != nil {
		t.Fatalf("Create RS: %v", err)
	}
	waitFor(t, "initial convergence", func() bool {
		rs, err := api.Get("replicasets", "default", "web")
		return err == nil && rs.(*apis.ReplicaSet).Status.ReadyReplicas == 2
	})

	// Delete a pod, like a container crash the kubelet cannot restart.
	list, _ := api.List("pods", "default")
	victim := list[0].GetObjectMeta().Name
	if _, err := api.Delete("pods", "default", victim); err != nil {
		t.Fatalf("Delete pod: %v", err)
	}

	waitFor(t, "self-heal back to 2 ready", func() bool {
		rs, err := api.Get("replicasets", "default", "web")
		if err != nil {
			return false
		}
		st := rs.(*apis.ReplicaSet).Status
		if st.Replicas != 2 || st.ReadyReplicas != 2 {
			return false
		}
		pods, _ := api.List("pods", "default")
		return len(pods) == 2
	})
}

// TestKubeletIgnoresRunningPods: syncPod on an already-Running pod is a no-op
// and must not bump Started().
func TestKubeletIgnoresRunningPods(t *testing.T) {
	api, _, k, _ := fullStack(t, 0)

	pod := &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: "done", Namespace: "default"},
		Spec:       apis.PodSpec{Image: "nginx"},
	}
	if _, err := api.Create("pods", pod); err != nil {
		t.Fatalf("Create: %v", err)
	}
	waitFor(t, "pod started once", func() bool { return k.Started() == 1 })

	// Touch the pod (a status no-op update) to generate more events.
	got, _ := api.Get("pods", "default", "done")
	if _, err := api.UpdateStatus("pods", got, 0); err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	time.Sleep(100 * time.Millisecond)
	if s := k.Started(); s != 1 {
		t.Errorf("Started = %d, want 1 (already-Running pods must be no-ops)", s)
	}
}

// TestSyncPodDeletedFromCache: syncPod on a key whose pod vanished from the
// cache must return nil, not an error (avoiding a requeue storm on deletes).
func TestSyncPodDeletedFromCache(t *testing.T) {
	api, _, k, cancel := fullStack(t, 0)
	defer cancel()
	_ = api
	// Nothing in the cache under this key.
	if err := k.syncPod(context.Background(), "default/ghost"); err != nil {
		t.Errorf("syncPod on missing key = %v, want nil", err)
	}
}
