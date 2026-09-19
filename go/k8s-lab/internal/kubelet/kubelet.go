// Package kubelet implements a stand-in for the node agent. In real
// Kubernetes the kubelet watches Pods bound to its node, starts containers,
// and reports observed status back to the apiserver. This lab has no
// containers, so the simulator does the one thing that matters for the
// control-plane story: it observes Pending Pods and flips them to Running,
// writing Status through the status subresource.
//
// What it teaches:
//
//   - Status is owned by the node, not by the controller. The ReplicaSet
//     controller creates Pods but leaves Status empty; the kubelet is the only
//     writer that transitions Pending -> Running. Two components writing one
//     object safely is exactly why the status subresource exists.
//   - The kubelet is itself a controller: it runs an informer over Pods,
//     enqueues what it sees, and reconciles (start containers == set Running)
//     level-triggered. Restarting it re-converges without replaying history.
//   - Scheduling is folded in here for simplicity: any unscheduled Pod
//     (spec.nodeName empty) is adopted by this simulated node, standing in for
//     the scheduler's bind plus the kubelet's pickup.
package kubelet

import (
	"context"
	"io"
	"log"
	"strconv"
	"sync"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/workqueue"
)

// Kubelet simulates one node.
type Kubelet struct {
	api      *apiserver.Server
	nodeName string
	pods     *informer.Informer
	queue    *workqueue.Queue
	logger   *log.Logger

	// startupDelay models image pull / container start latency so observers
	// can see the Pending phase before it flips. Zero means instant.
	startupDelay time.Duration

	mu      sync.Mutex
	started int // count of pods transitioned to Running (for tests/telemetry)
}

// Option configures a Kubelet.
type Option func(*Kubelet)

// WithStartupDelay sets how long a Pod stays Pending before the kubelet marks
// it Running. Useful in demos to make the lifecycle visible.
func WithStartupDelay(d time.Duration) Option {
	return func(k *Kubelet) { k.startupDelay = d }
}

// WithLogger attaches a logger; nil discards.
func WithLogger(l *log.Logger) Option {
	return func(k *Kubelet) { k.logger = l }
}

// New returns a Kubelet that adopts unscheduled Pods and runs them.
func New(api *apiserver.Server, podInformer *informer.Informer, nodeName string, opts ...Option) *Kubelet {
	k := &Kubelet{
		api:      api,
		nodeName: nodeName,
		pods:     podInformer,
		queue:    workqueue.New(),
		logger:   log.New(io.Discard, "", 0),
	}
	for _, o := range opts {
		o(k)
	}
	if k.logger == nil {
		k.logger = log.New(io.Discard, "", 0)
	}

	// Enqueue every pod we observe; reconcile decides whether it needs work.
	h := informer.HandlerFuncs{
		AddFunc:    func(key string, _ apis.Object) { k.queue.Add(key) },
		UpdateFunc: func(key string, _, _ apis.Object) { k.queue.Add(key) },
	}
	podInformer.AddHandler(h)
	return k
}

// Started reports how many Pods this kubelet has transitioned to Running.
func (k *Kubelet) Started() int {
	k.mu.Lock()
	defer k.mu.Unlock()
	return k.started
}

// Run blocks until ctx is cancelled, processing the Pod queue with one worker.
func (k *Kubelet) Run(ctx context.Context) {
	var wg sync.WaitGroup
	wg.Go(func() { k.worker(ctx) })
	<-ctx.Done()
	k.queue.ShutDown()
	wg.Wait()
}

func (k *Kubelet) worker(ctx context.Context) {
	for {
		key, shutdown := k.queue.Get()
		if shutdown {
			return
		}
		if err := k.syncPod(ctx, key); err != nil {
			k.logger.Printf("kubelet sync %s: %v (requeue)", key, err)
			if ctx.Err() == nil {
				k.queue.Add(key)
			}
			select {
			case <-ctx.Done():
				k.queue.Done(key)
				return
			case <-time.After(50 * time.Millisecond):
			}
		}
		k.queue.Done(key)
	}
}

// syncPod is the kubelet's reconcile for one Pod: if it is Pending, simulate
// "starting containers" and write Running status. Idempotent: an already
// Running Pod is a no-op.
func (k *Kubelet) syncPod(ctx context.Context, key string) error {
	if ctx.Err() != nil {
		return ctx.Err()
	}
	obj := k.pods.Store().Get(key)
	if obj == nil {
		return nil // Pod deleted; nothing to do.
	}
	pod := obj.(*apis.Pod)
	if pod.Status.Phase == apis.PodRunning {
		return nil // already synced.
	}

	// Model container startup latency (image pull etc.).
	if k.startupDelay > 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(k.startupDelay):
		}
	}

	ns := pod.ObjectMeta.Namespace
	name := pod.ObjectMeta.Name

	// Re-read from the apiserver to get the freshest resourceVersion; the
	// cache may lag. A conflict just requeues.
	cur, err := k.api.Get("pods", ns, name)
	if err != nil {
		return err
	}
	curPod := cur.(*apis.Pod)
	if curPod.Status.Phase == apis.PodRunning {
		return nil
	}

	// Simulate scheduling+binding (spec.nodeName) and startup (status).
	update := curPod.DeepCopyObject().(*apis.Pod)
	if update.Spec.NodeName == "" {
		update.Spec.NodeName = k.nodeName
	}
	// Bind the node through the normal Update (spec change), then status.
	if update.Spec.NodeName != curPod.Spec.NodeName {
		rv, _ := strconv.ParseUint(curPod.ResourceVersion, 10, 64)
		if _, err := k.api.Update("pods", update, rv); err != nil {
			return err
		}
	}

	// Status write through the subresource, re-reading for a fresh rv.
	latest, err := k.api.Get("pods", ns, name)
	if err != nil {
		return err
	}
	statusCopy := latest.DeepCopyObject().(*apis.Pod)
	statusCopy.Status.Phase = apis.PodRunning
	rv, _ := strconv.ParseUint(latest.GetObjectMeta().ResourceVersion, 10, 64)
	if _, err := k.api.UpdateStatus("pods", statusCopy, rv); err != nil {
		return err
	}

	k.mu.Lock()
	k.started++
	k.mu.Unlock()
	k.logger.Printf("kubelet: pod %s/%s now Running on %s", ns, name, k.nodeName)
	return nil
}
