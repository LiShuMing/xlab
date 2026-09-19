// Package controller implements the reconciliation loops of the mini control
// plane — the lab's version of kube-controller-manager.
//
// What it teaches about Kubernetes controllers:
//
//   - A controller is an infinite loop with one job: make observed state
//     match desired state. It never trusts its memory of what happened; each
//     pass re-reads the world (level-triggered). A missed event delays
//     convergence by one requeue — it can never corrupt it.
//   - Events are just doorbells. The informer enqueues KEYS; the worker pulls
//     a key and reconciles from the cache + apiserver. This indirection gives
//     deduplication (the workqueue), failure isolation (one bad object cannot
//     stall the loop) and safe requeue-on-conflict.
//   - Ownership is expressed through labels. The ReplicaSet "owns" Pods by
//     selecting them, not by holding pointers — the same mechanism real
//     Kubernetes uses (via ownerReferences, which we fold into labels for
//     simplicity).
//   - Spec is read-only to the controller; Status is written through the
//     status subresource; children (Pods) are created/deleted through the
//     apiserver. Those three write paths are the entire surface a controller
//     touches.
package controller

import (
	"context"
	"fmt"
	"io"
	"log"
	"sync"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/workqueue"
)

// ReplicaSetController drives observed Pod counts toward spec.replicas for
// every ReplicaSet, mirroring kube-controller-manager's ReplicaSet controller.
type ReplicaSetController struct {
	api *apiserver.Server

	rsInformers []*informer.Informer // one per namespace we watch; lab uses one
	podCache    *informer.Cache      // Pods informer's cache for adoption scans

	queue *workqueue.Queue

	logger *log.Logger

	// exp records, per ReplicaSet, how many Pod creations/deletions we have
	// issued but not yet seen come back through the informer. It is the
	// lab's ControllerExpectations and the key to not over-provisioning.
	exp *expectations

	// podSeq numbers generated Pod names. Guarded by mu because reconcile
	// runs on a single worker in the lab, but the controller should stay
	// correct if someone raises workers above 1.
	mu     sync.Mutex
	podSeq map[string]int // rsKey -> next ordinal
}

// expectations is a simplified k8s ControllerExpectations.
//
// Why it exists (the subtlest bug in naive controllers):
//
// A controller acts on its informer CACHE, which lags the apiserver by the
// watch-delivery latency. Suppose reconcile creates 3 Pods and returns. Those
// Pods are in the store, but the Pod Add events have not reached the cache
// yet. If anything re-enqueues the ReplicaSet in that window — and in a
// level-triggered system something always does — the next reconcile still
// counts 0 owned Pods and creates 3 MORE. Left unchecked this is an
// over-provisioning storm.
//
// The fix real Kubernetes uses: before acting, record "I expect N creations
// for this owner". Each observed Pod Add decrements the count. Reconcile
// refuses to create/delete again until expectations are SATISFIED (back to
// zero), which by definition means the cache has caught up with what we did.
// Only then is it safe to diff desired vs observed again.
type expectations struct {
	mu  sync.Mutex
	cre map[string]int // pending creations per RS key
	del map[string]int // pending deletions per RS key
}

func newExpectations() *expectations {
	return &expectations{cre: map[string]int{}, del: map[string]int{}}
}

// expectCreations records that n Pod creations are in flight for key.
func (e *expectations) expectCreations(key string, n int) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.cre[key] = n
}

// expectDeletions records that n Pod deletions are in flight for key.
func (e *expectations) expectDeletions(key string, n int) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.del[key] = n
}

// creationObserved notes one Pod Add for key (floored at zero so a stray Add
// cannot drive the counter negative).
func (e *expectations) creationObserved(key string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.cre[key] > 0 {
		e.cre[key]--
	}
}

// deletionObserved notes one Pod Delete for key (floored at zero).
func (e *expectations) deletionObserved(key string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.del[key] > 0 {
		e.del[key]--
	}
}

// satisfied reports whether all in-flight actions for key have been observed,
// i.e. the cache has caught up and it is safe to reconcile again.
func (e *expectations) satisfied(key string) bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.cre[key] <= 0 && e.del[key] <= 0
}

// NewReplicaSetController wires a controller over an apiserver. The caller
// supplies (and separately runs) the informers so tests can inject fakes. A
// nil logger discards output. log.Logger is already safe for concurrent use,
// so no extra locking is needed around it.
func NewReplicaSetController(api *apiserver.Server, rsInformer, podInformer *informer.Informer, logger *log.Logger) *ReplicaSetController {
	if logger == nil {
		logger = log.New(io.Discard, "", 0)
	}
	c := &ReplicaSetController{
		api:         api,
		rsInformers: []*informer.Informer{rsInformer},
		podCache:    podInformer.Store(),
		queue:       workqueue.New(),
		logger:      logger,
		exp:         newExpectations(),
		podSeq:      make(map[string]int),
	}

	// The ONLY thing event handlers do is enqueue keys. Reading state here
	// would race with the worker; reconcile re-reads everything anyway.
	rsHandlers := informer.HandlerFuncs{
		AddFunc:    func(key string, _ apis.Object) { c.queue.Add(key) },
		UpdateFunc: func(key string, _, _ apis.Object) { c.queue.Add(key) },
		DeleteFunc: func(key string, _ apis.Object) { c.queue.Add(key) },
	}
	rsInformer.AddHandler(rsHandlers)

	// Pod events do two jobs: (1) decrement the owner's expectations so a
	// pending create/delete is marked observed, and (2) enqueue the OWNING
	// ReplicaSet — a Pod change only matters because it moves some RS away
	// from its desired count. This "map to owner" is client-go's
	// ownerReferences pattern, expressed through a label here.
	podHandlers := informer.HandlerFuncs{
		AddFunc: func(_ string, obj apis.Object) {
			if owner := obj.GetObjectMeta().Labels[OwnerLabel]; owner != "" {
				key := ownerKeyOf(obj)
				c.exp.creationObserved(key)
				c.queue.Add(key)
			}
		},
		UpdateFunc: func(_ string, _, newObj apis.Object) {
			if owner := newObj.GetObjectMeta().Labels[OwnerLabel]; owner != "" {
				c.queue.Add(ownerKeyOf(newObj))
			}
		},
		DeleteFunc: func(_ string, obj apis.Object) {
			if owner := obj.GetObjectMeta().Labels[OwnerLabel]; owner != "" {
				key := ownerKeyOf(obj)
				c.exp.deletionObserved(key)
				c.queue.Add(key)
			}
		},
	}
	podInformer.AddHandler(podHandlers)

	return c
}

// OwnerLabel marks the ReplicaSet a Pod belongs to. Real Kubernetes uses
// metadata.ownerReferences plus the controller-uid label; a single label is
// enough for the lab and keeps the adoption logic readable.
//
// The value is the RS name only, so ownerKeyOf can build a cache key of the
// form "namespace/name". A slash in the label value would collide with that
// key format (splitKey parses at the first slash).
const OwnerLabel = "k8s-lab.owner"

// ownerKeyOf derives the cache key of the RS that owns a pod, from the label.
func ownerKeyOf(pod apis.Object) string {
	owner := pod.GetObjectMeta().Labels[OwnerLabel]
	return pod.GetObjectMeta().Namespace + "/" + owner
}

// Run blocks until ctx is cancelled, processing the work queue with the given
// number of workers. One worker is the canonical setup; more is safe because
// the workqueue guarantees a key is never processed twice concurrently.
func (c *ReplicaSetController) Run(ctx context.Context, workers int) {
	if workers < 1 {
		workers = 1
	}
	var wg sync.WaitGroup
	for range workers {
		wg.Go(func() { c.worker(ctx) })
	}
	<-ctx.Done()
	c.queue.ShutDown()
	wg.Wait()
}

// worker is the reconcile pump: Get a key, reconcile, Done; requeue on error.
func (c *ReplicaSetController) worker(ctx context.Context) {
	for {
		key, shutdown := c.queue.Get()
		if shutdown {
			return
		}
		err := c.reconcile(ctx, key)
		c.queue.Done(key)
		if err != nil {
			// Requeue and retry: conflicts and transient failures are
			// expected in a level-triggered system. Real controllers use a
			// rate-limited queue here; a plain requeue suffices for the lab.
			c.logger.Printf("reconcile %s failed: %v (requeueing)", key, err)
			if ctx.Err() == nil {
				c.queue.Add(key)
			}
			// Back off briefly so a persistently failing key cannot spin.
			select {
			case <-ctx.Done():
				return
			case <-time.After(50 * time.Millisecond):
			}
		}
	}
}

// reconcile drives ONE ReplicaSet toward its desired replica count.
//
// The shape is deliberate and mirrors the real controller:
//
//  1. Read desired state (RS from informer cache; gone means deleted).
//  2. Read observed state (adopted Pods, scanned from the pod cache).
//  3. Diff and act through the apiserver only: create missing Pods, delete
//     surplus Pods.
//  4. Write Status back through the status subresource.
//
// Every step is idempotent: running reconcile twice with no external change
// is a no-op, which is what makes requeue-on-anything safe.
func (c *ReplicaSetController) reconcile(ctx context.Context, key string) error {
	if ctx.Err() != nil {
		return ctx.Err()
	}

	ns, name, err := splitKey(key)
	if err != nil {
		return err
	}

	// 1. Desired state. The cache is the read path; the apiserver Get would
	// also work but costs a server round-trip — informers exist to avoid it.
	rsObj := c.rsInformers[0].Store().Get(key)
	if rsObj == nil {
		// The RS is gone; its Pods will be garbage-collected by the Pod
		// handlers (each orphan Pod delete/add requeues this key, which now
		// finds nothing and stops). Real k8s relies on ownerReference GC;
		// the lab lets orphan Pods be cleaned by kubelet simulation end.
		return nil
	}
	rs := rsObj.(*apis.ReplicaSet)

	// 2. Gate on expectations: if creates/deletes we issued have not been
	// observed back through the informer yet, the cache is stale and any
	// diff we compute now would double-count. Skip this pass; the Pod
	// Add/Delete events will requeue us once the cache catches up.
	if !c.exp.satisfied(key) {
		return nil
	}

	// 3. Observed state: all Pods in this namespace carrying our owner label.
	// Scanning the local cache is free; a real controller uses an indexed
	// informer — same idea, O(1) instead of O(n).
	owned := c.ownedPods(ns, name)

	// 4. Diff and act, recording expectations FIRST so a racing requeue
	// cannot re-diff before our actions are observed.
	desired := int(rs.Spec.Replicas)
	switch {
	case len(owned) < desired:
		n := desired - len(owned)
		c.exp.expectCreations(key, n)
		for range n {
			if err := c.createPod(ctx, ns, name, rs); err != nil {
				// Creation failed; the pending count would never clear, so
				// mark this one observed and let the requeue retry the rest.
				c.exp.creationObserved(key)
				return err
			}
		}
	case len(owned) > desired:
		n := len(owned) - desired
		c.exp.expectDeletions(key, n)
		// Delete newest-first, like the real controller's getPodsToDelete
		// ordering (unscheduled/not-ready pods go first there).
		for i := len(owned) - 1; i >= desired; i-- {
			podName := owned[i].GetObjectMeta().Name
			if _, err := c.api.Delete("pods", ns, podName); err != nil {
				c.exp.deletionObserved(key)
				return err
			}
			c.logger.Printf("rs %s: deleted surplus pod %s", key, podName)
		}
	}

	// 5. Status — recomputed from the cache and written through the status
	// subresource so a concurrent spec write by the user cannot be clobbered.
	//
	// Critically, write ONLY when something changed. An unconditional write
	// bumps resourceVersion, which fires an RS Modified event, which requeues
	// the RS, which writes again... a self-sustaining busy loop that burns
	// revisions forever (and amplifies any cache-lag race into a pod storm).
	// "Do not write status you did not change" is a real controller rule for
	// exactly this reason.
	var ready int32
	for _, p := range owned {
		if p.(*apis.Pod).Status.Phase == apis.PodRunning {
			ready++
		}
	}
	if rs.Status.Replicas == int32(len(owned)) && rs.Status.ReadyReplicas == ready {
		return nil // observed status already current; nothing to write
	}
	statusCopy := rs.DeepCopyObject().(*apis.ReplicaSet)
	statusCopy.Status.Replicas = int32(len(owned))
	statusCopy.Status.ReadyReplicas = ready
	cur, err := c.api.Get("replicasets", ns, name)
	if err != nil {
		return err
	}
	rv := parseRV(cur.GetObjectMeta().ResourceVersion)
	if _, err := c.api.UpdateStatus("replicasets", statusCopy, rv); err != nil {
		// A conflict here is fine: someone else moved the object. Requeue.
		return err
	}
	return nil
}

// ownedPods returns cache-sorted Pods in ns owned by the named RS.
func (c *ReplicaSetController) ownedPods(ns, rsName string) []apis.Object {
	var out []apis.Object
	for _, obj := range c.podCache.List() {
		meta := obj.GetObjectMeta()
		if meta.Namespace == ns && meta.Labels[OwnerLabel] == rsName {
			out = append(out, obj)
		}
	}
	return out
}

// createPod materialises spec.template into a real Pod through the apiserver.
// The generated name is <rs>-<ordinal>, with the ordinal advancing per RS so
// retries after partial failure never collide.
func (c *ReplicaSetController) createPod(ctx context.Context, ns, rsName string, rs *apis.ReplicaSet) error {
	if ctx.Err() != nil {
		return ctx.Err()
	}
	c.mu.Lock()
	seq := c.podSeq[ns+"/"+rsName]
	c.podSeq[ns+"/"+rsName] = seq + 1
	c.mu.Unlock()

	tmpl := rs.Spec.Template.DeepCopy()
	labels := tmpl.Labels
	if labels == nil {
		labels = make(map[string]string)
	}
	labels[OwnerLabel] = rsName

	pod := &apis.Pod{
		ObjectMeta: apis.ObjectMeta{
			Name:      fmt.Sprintf("%s-%d", rsName, seq),
			Namespace: ns,
			Labels:    labels,
		},
		Spec: rs.Spec.Template.Spec,
		// Status deliberately zero: the kubelet simulator owns it. A Pod is
		// born Pending in real Kubernetes too.
	}
	if _, err := c.api.Create("pods", pod); err != nil {
		return fmt.Errorf("create pod %s: %w", pod.Name, err)
	}
	c.logger.Printf("rs %s/%s: created pod %s", ns, rsName, pod.Name)
	return nil
}

// splitKey parses "namespace/name" cache keys.
func splitKey(key string) (ns, name string, err error) {
	for i := range len(key) {
		if key[i] == '/' {
			return key[:i], key[i+1:], nil
		}
	}
	return "", "", fmt.Errorf("controller: malformed key %q, want namespace/name", key)
}

// parseRV converts a resourceVersion string to uint64, treating garbage as 0
// (a blind write) rather than failing the reconcile.
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
