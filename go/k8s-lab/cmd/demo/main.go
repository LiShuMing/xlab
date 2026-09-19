// Command demo wires the mini control plane end to end and narrates what is
// happening at each step, so the closed loop is visible when you run it:
//
//	apiserver (typed facade)
//	   └── store (etcd-like MVCC + watch)
//	informers (LIST+WATCH -> local cache)  ← ReplicaSet controller, kubelet
//	workqueue (dedup keys)                 ← controller / kubelet workers
//
// Run it with: go run ./cmd/demo
//
// The scenario declares a 3-replica ReplicaSet, watches it converge, kills a
// Pod to show self-healing, scales down, and scales back up — printing the
// observed vs desired state at each step.
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/controller"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/kubelet"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

func main() {
	// Root context cancelled on Ctrl-C so everything shuts down cleanly.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	fmt.Println("=== k8s-lab: mini control plane demo ===")
	fmt.Println("Building apiserver over an etcd-like MVCC store...")

	// 1. Storage + API layer — the source of truth and its front door.
	st := store.New()
	defer st.Close()
	api := apiserver.New(st)

	// 2. Informers — one per resource. Each LISTs then WATCHes into a cache.
	fmt.Println("Starting informers (LIST + WATCH) for replicasets and pods...")
	rsInf := informer.New(informer.NewServerListWatch(api, "replicasets"))
	podInf := informer.New(informer.NewServerListWatch(api, "pods"))

	// 3. Controllers / node agent — reconcile loops over the informers.
	fmt.Println("Starting ReplicaSet controller and a simulated kubelet (node-1)...")
	rsCtrl := controller.NewReplicaSetController(api, rsInf, podInf, nil)
	klet := kubelet.New(api, podInf, "node-1", kubelet.WithStartupDelay(150*time.Millisecond))

	// Run every long-lived component in its own goroutine.
	go rsInf.Run(ctx)
	go podInf.Run(ctx)
	go rsCtrl.Run(ctx, 1)
	go klet.Run(ctx)

	// Do not act until the caches are primed, exactly like a real controller
	// manager waits for cache sync before starting workers.
	syncCtx, cancelSync := context.WithTimeout(ctx, 5*time.Second)
	synced := rsInf.WaitForSync(syncCtx) && podInf.WaitForSync(syncCtx)
	cancelSync()
	if !synced {
		fmt.Fprintln(os.Stderr, "informer caches failed to sync")
		os.Exit(1)
	}
	fmt.Println("Caches synced.")
	fmt.Println()

	// 4. Declare desired state: a 3-replica ReplicaSet. This is the ONLY
	//    thing the "user" does — everything else is the system converging.
	fmt.Println(">>> kubectl apply: ReplicaSet web (replicas=3, image=nginx:1.25)")
	rs := &apis.ReplicaSet{
		ObjectMeta: apis.ObjectMeta{Name: "web", Namespace: "default"},
		Spec: apis.ReplicaSetSpec{
			Replicas: 3,
			Selector: apis.LabelSelector{MatchLabels: map[string]string{"app": "web"}},
			Template: apis.PodTemplateSpec{
				ObjectMeta: apis.ObjectMeta{Labels: map[string]string{"app": "web"}},
				Spec:       apis.PodSpec{Image: "nginx:1.25"},
			},
		},
	}
	if _, err := api.Create("replicasets", rs); err != nil {
		fmt.Fprintf(os.Stderr, "apply failed: %v\n", err)
		os.Exit(1)
	}

	waitConverged(ctx, api, "web", 3, 3)
	printState(api, "web", "after initial apply")

	// 5. Self-healing: delete a Pod and watch the loop restore it. The user
	//    does nothing — the delete event requeues the owner and reconcile
	//    recreates a replacement, which the kubelet then runs.
	fmt.Println("\n>>> kill -9 on pod web-0 (simulating a node/container failure)")
	if _, err := api.Delete("pods", "default", "web-0"); err != nil {
		fmt.Fprintf(os.Stderr, "delete failed: %v\n", err)
	}
	waitConverged(ctx, api, "web", 3, 3)
	printState(api, "web", "after self-heal")

	// 6. Scale down to 1.
	fmt.Println("\n>>> kubectl scale --replicas=1")
	scale(api, "web", 1)
	waitConverged(ctx, api, "web", 1, 1)
	printState(api, "web", "after scale down to 1")

	// 7. Scale back up to 4.
	fmt.Println("\n>>> kubectl scale --replicas=4")
	scale(api, "web", 4)
	waitConverged(ctx, api, "web", 4, 4)
	printState(api, "web", "after scale up to 4")

	fmt.Println("\n=== demo complete ===")
	fmt.Println("Every transition above was driven by the same loop:")
	fmt.Println("  declare desired state -> informer cache update -> workqueue key")
	fmt.Println("  -> reconcile (diff desired vs observed) -> act via apiserver")
	fmt.Println("  -> kubelet runs pods -> status written back -> loop repeats.")
	fmt.Println("That is the whole idea of Kubernetes in one sentence.")
}

// scale updates spec.replicas with a fresh read (optimistic concurrency).
func scale(api *apiserver.Server, name string, replicas int32) {
	cur, err := api.Get("replicasets", "default", name)
	if err != nil {
		fmt.Fprintf(os.Stderr, "scale: get failed: %v\n", err)
		return
	}
	updated := cur.DeepCopyObject().(*apis.ReplicaSet)
	updated.Spec.Replicas = replicas
	rv := parseRV(cur.GetObjectMeta().ResourceVersion)
	if _, err := api.Update("replicasets", updated, rv); err != nil {
		fmt.Fprintf(os.Stderr, "scale: update failed: %v\n", err)
	}
}

// waitConverged blocks until the world actually matches the goal: exactly
// `replicas` Pods owned by the RS, of which `ready` are Running, and the RS
// status agrees.
//
// Checking real Pod phases — not just the status counters — matters right
// after a disruptive action: the status still reports the PRE-delete counts
// for a few milliseconds, so a naive counter check would return immediately
// and print a half-converged state. This is the same reason controllers
// reconcile from observed objects rather than trusting a cached status field.
func waitConverged(ctx context.Context, api *apiserver.Server, name string, replicas, ready int32) {
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		if ctx.Err() != nil {
			return
		}
		pods, _ := api.List("pods", "default")
		var owned, running int32
		for _, p := range pods {
			pod := p.(*apis.Pod)
			if pod.Labels[controller.OwnerLabel] != name {
				continue
			}
			owned++
			if pod.Status.Phase == apis.PodRunning {
				running++
			}
		}
		if owned == replicas && running == ready {
			// Confirm the controller's status caught up too, then settle.
			if obj, err := api.Get("replicasets", "default", name); err == nil {
				st := obj.(*apis.ReplicaSet).Status
				if st.Replicas == replicas && st.ReadyReplicas == ready {
					time.Sleep(100 * time.Millisecond)
					return
				}
			}
		}
		time.Sleep(20 * time.Millisecond)
	}
	fmt.Fprintf(os.Stderr, "  (warning: %s did not converge to %d/%d in time)\n", name, replicas, ready)
}

// printState shows desired vs observed for a RS and its Pods.
func printState(api *apiserver.Server, name, phase string) {
	obj, err := api.Get("replicasets", "default", name)
	if err != nil {
		fmt.Fprintf(os.Stderr, "printState: %v\n", err)
		return
	}
	rs := obj.(*apis.ReplicaSet)
	fmt.Printf("--- %s ---\n", phase)
	fmt.Printf("ReplicaSet/%s  desired=%d  observed=%d  ready=%d  rv=%s\n",
		name, rs.Spec.Replicas, rs.Status.Replicas, rs.Status.ReadyReplicas, rs.ResourceVersion)

	pods, _ := api.List("pods", "default")
	for _, p := range pods {
		pod := p.(*apis.Pod)
		fmt.Printf("  Pod/%-8s phase=%-8s node=%-7s rv=%s\n",
			pod.Name, pod.Status.Phase, pod.Spec.NodeName, pod.ResourceVersion)
	}
}

// parseRV converts a resourceVersion string to uint64 (garbage -> 0).
func parseRV(s string) uint64 {
	var rv uint64
	for i := range len(s) {
		if s[i] < '0' || s[i] > '9' {
			return 0
		}
		rv = rv*10 + uint64(s[i]-'0')
	}
	return rv
}
