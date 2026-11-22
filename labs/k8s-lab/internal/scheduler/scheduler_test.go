package scheduler

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/store"
)

func makeNode(name string, gpus []apis.GPUDevice) *apis.Node {
	return &apis.Node{
		ObjectMeta: apis.ObjectMeta{Name: name, Namespace: "default"},
		Spec:       apis.NodeSpec{GPUs: gpus},
		Status:     apis.NodeStatus{Ready: true},
	}
}

func make4GPUNode(name string) *apis.Node {
	return makeNode(name, []apis.GPUDevice{
		{ID: 0, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		{ID: 1, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		{ID: 2, MemoryMiB: 81920, NVLinkGroup: "nv1"},
		{ID: 3, MemoryMiB: 81920, NVLinkGroup: "nv1"},
	})
}

func waitFor(t *testing.T, desc string, cond func() bool) {
	t.Helper()
	deadline := time.Now().Add(4 * time.Second)
	for time.Now().Before(deadline) {
		if cond() {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("timed out waiting for: %s", desc)
}

func TestBinPackVsSpreadFragmentationForLargeJob(t *testing.T) {
	runScenario := func(policy ScorePolicy) (admittedLarge int, frag float64) {
		st := store.New()
		defer st.Close()
		api := apiserver.New(st)
		for i := range 4 {
			if _, err := api.Create("nodes", make4GPUNode(fmt.Sprintf("node-%d", i))); err != nil {
				t.Fatalf("create node: %v", err)
			}
		}
		sched := New(api, nil, nil, WithScorePolicy(policy))

		for i := range 4 {
			p := &apis.Pod{
				ObjectMeta: apis.ObjectMeta{Name: fmt.Sprintf("small-%d", i)},
				Spec:       apis.PodSpec{Image: "infer:1gpu", GPURequest: 1, GPUMemoryMiB: 16384},
			}
			if _, err := api.Create("pods", p); err != nil {
				t.Fatalf("create small pod: %v", err)
			}
		}
		if _, err := sched.ScheduleOnce(context.Background(), "default"); err != nil {
			t.Fatalf("schedule small pods: %v", err)
		}
		m, err := ComputeClusterMetrics(api, "default", 4)
		if err != nil {
			t.Fatalf("metrics: %v", err)
		}
		frag = m.FragmentationRatio

		for i := range 3 {
			p := &apis.Pod{
				ObjectMeta: apis.ObjectMeta{Name: fmt.Sprintf("large-%d", i)},
				Spec:       apis.PodSpec{Image: "train:4gpu", GPURequest: 4, GPUMemoryMiB: 81920},
			}
			if _, err := api.Create("pods", p); err != nil {
				t.Fatalf("create large pod: %v", err)
			}
		}
		admittedLarge, err = sched.ScheduleOnce(context.Background(), "default")
		if err != nil {
			t.Fatalf("schedule large pods: %v", err)
		}
		if err := VerifyClusterInvariants(api, "default"); err != nil {
			t.Fatalf("invariant violation under %s: %v", policy, err)
		}
		return admittedLarge, frag
	}

	spreadAdmitted, spreadFrag := runScenario(PolicySpread)
	binpackAdmitted, binpackFrag := runScenario(PolicyBinPack)

	if spreadAdmitted != 0 || spreadFrag < 0.99 {
		t.Fatalf("expected Spread to fragment all 4 nodes (admitted=0, frag=1.0), got admitted=%d frag=%.2f", spreadAdmitted, spreadFrag)
	}
	if binpackAdmitted != 3 || binpackFrag != 0.0 {
		t.Fatalf("expected BinPack to admit all 3 large jobs (admitted=3, frag=0.0), got admitted=%d frag=%.2f", binpackAdmitted, binpackFrag)
	}
}

func TestNVLinkTopologyAffinity(t *testing.T) {
	st := store.New()
	defer st.Close()
	api := apiserver.New(st)

	if _, err := api.Create("nodes", makeNode("node-a", []apis.GPUDevice{
		{ID: 0, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		{ID: 2, MemoryMiB: 81920, NVLinkGroup: "nv1"},
	})); err != nil {
		t.Fatal(err)
	}
	if _, err := api.Create("nodes", makeNode("node-b", []apis.GPUDevice{
		{ID: 0, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		{ID: 1, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		{ID: 2, MemoryMiB: 81920, NVLinkGroup: "nv1"},
	})); err != nil {
		t.Fatal(err)
	}

	sched := New(api, nil, nil, WithScorePolicy(PolicyBinPack))
	tpPod := &apis.Pod{
		ObjectMeta: apis.ObjectMeta{Name: "tp2-infer"},
		Spec:       apis.PodSpec{Image: "vllm:tp2", GPURequest: 2, GPUMemoryMiB: 40960},
	}
	if _, err := api.Create("pods", tpPod); err != nil {
		t.Fatal(err)
	}
	bound, err := sched.ScheduleOnce(context.Background(), "default")
	if err != nil || bound != 1 {
		t.Fatalf("expected 1 bound pod, got bound=%d err=%v", bound, err)
	}

	got, _ := api.Get("pods", "default", "tp2-infer")
	p := got.(*apis.Pod)
	if p.Spec.NodeName != "node-b" {
		t.Fatalf("expected NVLink-co-located node-b, got %s", p.Spec.NodeName)
	}
	if len(p.Spec.AssignedGPUs) != 2 || p.Spec.AssignedGPUs[0] != 0 || p.Spec.AssignedGPUs[1] != 1 {
		t.Fatalf("expected GPUs [0 1] in nv0, got %v", p.Spec.AssignedGPUs)
	}
	if err := VerifyClusterInvariants(api, "default"); err != nil {
		t.Fatal(err)
	}
}

func TestGangSchedulingPreventsInterleavedDeadlock(t *testing.T) {
	st := store.New()
	defer st.Close()
	api := apiserver.New(st)

	for i := range 2 {
		if _, err := api.Create("nodes", makeNode(fmt.Sprintf("gpu-node-%d", i), []apis.GPUDevice{
			{ID: 0, MemoryMiB: 81920, NVLinkGroup: "nv0"},
			{ID: 1, MemoryMiB: 81920, NVLinkGroup: "nv0"},
		})); err != nil {
			t.Fatal(err)
		}
	}

	sched := New(api, nil, nil, WithScorePolicy(PolicyBinPack))

	for _, spec := range []struct{ name, grp string }{
		{"job-a-0", "job-a"},
		{"job-b-0", "job-b"},
	} {
		if _, err := api.Create("pods", &apis.Pod{
			ObjectMeta: apis.ObjectMeta{Name: spec.name},
			Spec: apis.PodSpec{
				Image: "ddp:2gpu", GPURequest: 2, PodGroup: spec.grp, MinAvailable: 2,
			},
		}); err != nil {
			t.Fatal(err)
		}
	}
	bound, err := sched.ScheduleOnce(context.Background(), "default")
	if err != nil || bound != 0 {
		t.Fatalf("incomplete gangs must not reserve partial GPUs; got bound=%d err=%v", bound, err)
	}

	for _, spec := range []struct{ name, grp string }{
		{"job-a-1", "job-a"},
		{"job-b-1", "job-b"},
	} {
		if _, err := api.Create("pods", &apis.Pod{
			ObjectMeta: apis.ObjectMeta{Name: spec.name},
			Spec: apis.PodSpec{
				Image: "ddp:2gpu", GPURequest: 2, PodGroup: spec.grp, MinAvailable: 2,
			},
		}); err != nil {
			t.Fatal(err)
		}
	}
	bound, err = sched.ScheduleOnce(context.Background(), "default")
	if err != nil || bound != 2 {
		t.Fatalf("expected exactly 1 complete gang (2 pods) bound, got bound=%d err=%v", bound, err)
	}

	boundCount := func(prefix string) int {
		n := 0
		for i := range 2 {
			obj, _ := api.Get("pods", "default", fmt.Sprintf("%s-%d", prefix, i))
			if obj.(*apis.Pod).Spec.NodeName != "" {
				n++
			}
		}
		return n
	}
	if a, b := boundCount("job-a"), boundCount("job-b"); a != 2 || b != 0 {
		t.Fatalf("gang atomicity violated: job-a bound=%d, job-b bound=%d", a, b)
	}
	if err := VerifyClusterInvariants(api, "default"); err != nil {
		t.Fatal(err)
	}

	for i := range 2 {
		obj, _ := api.Get("pods", "default", fmt.Sprintf("job-a-%d", i))
		done := obj.DeepCopyObject().(*apis.Pod)
		done.Status.Phase = apis.PodSucceeded
		if _, err := api.UpdateStatus("pods", done, 0); err != nil {
			t.Fatal(err)
		}
	}
	bound, err = sched.ScheduleOnce(context.Background(), "default")
	if err != nil || bound != 2 {
		t.Fatalf("expected job-b (2 pods) to schedule after job-a finished, got bound=%d err=%v", bound, err)
	}
	if b := boundCount("job-b"); b != 2 {
		t.Fatalf("expected job-b bound=2, got %d", b)
	}
	if err := VerifyClusterInvariants(api, "default"); err != nil {
		t.Fatal(err)
	}
}

func TestSchedulerRunLoopAndCleanShutdown(t *testing.T) {
	st := store.New()
	defer st.Close()
	api := apiserver.New(st)

	podInf := informer.New(informer.NewServerListWatch(api, "pods"))
	nodeInf := informer.New(informer.NewServerListWatch(api, "nodes"))
	sched := New(api, podInf, nodeInf, WithScorePolicy(PolicyBinPack))

	ctx, cancel := context.WithCancel(context.Background())
	infDone := make(chan struct{})
	schedDone := make(chan struct{})
	go func() { podInf.Run(ctx); close(infDone) }()
	go nodeInf.Run(ctx)
	go func() { sched.Run(ctx); close(schedDone) }()

	syncCtx, syncCancel := context.WithTimeout(ctx, 3*time.Second)
	ok := podInf.WaitForSync(syncCtx) && nodeInf.WaitForSync(syncCtx)
	syncCancel()
	if !ok {
		cancel()
		t.Fatal("informers failed to sync")
	}

	if _, err := api.Create("nodes", make4GPUNode("node-0")); err != nil {
		t.Fatal(err)
	}
	for i := range 3 {
		if _, err := api.Create("pods", &apis.Pod{
			ObjectMeta: apis.ObjectMeta{Name: fmt.Sprintf("p-%d", i)},
			Spec:       apis.PodSpec{Image: "infer", GPURequest: 1},
		}); err != nil {
			t.Fatal(err)
		}
	}

	waitFor(t, "all 3 pods bound by scheduler loop", func() bool {
		objs, _ := api.List("pods", "default")
		bound := 0
		for _, o := range objs {
			if o.(*apis.Pod).Spec.NodeName == "node-0" {
				bound++
			}
		}
		return bound == 3
	})

	if err := VerifyClusterInvariants(api, "default"); err != nil {
		t.Fatal(err)
	}

	cancel()
	select {
	case <-schedDone:
	case <-time.After(2 * time.Second):
		t.Fatal("scheduler.Run did not exit after cancel")
	}
	select {
	case <-infDone:
	case <-time.After(2 * time.Second):
		t.Fatal("informer.Run did not exit after cancel")
	}
}
