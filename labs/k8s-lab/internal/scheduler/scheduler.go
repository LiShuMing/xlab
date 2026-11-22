// Package scheduler implements a GPU-aware, topology-aware, and gang-capable
// Kubernetes scheduler (analogue of kube-scheduler + Volcano/Kueue coscheduling
// + DRA GPU topology plugins).
//
// What it teaches:
//
//   - Filter + Score pipeline: every scheduling decision first filters nodes
//     that cannot satisfy GPU count / VRAM / readiness, then scores feasible
//     nodes using pluggable policies (BinPack to minimize whole-GPU cluster
//     fragmentation vs Spread for fault isolation) plus NVLink island affinity.
//   - Topology-aware device selection: when a Pod requests >= 2 GPUs (e.g.
//     Tensor Parallelism), placing all GPUs inside one NVLinkGroup avoids slow
//     PCIe fallback and receives a strong score bonus.
//   - Gang Scheduling (Coscheduling): multi-Pod distributed training or TP/PP
//     jobs sharing a PodGroup must bind all MinAvailable Pods atomically or
//     bind none. Without atomic reservation, interleaved arrivals of two large
//     jobs deadlock permanently (each holds half the cluster waiting for more).
//   - Single write path: bindings are committed solely via apiserver.Server
//     using optimistic concurrency (resourceVersion), preserving k8s-lab's
//     control-plane architecture.
//
// Simplifications vs real kube-scheduler:
//   - No preemption/eviction of lower-priority running Pods.
//   - Single-process cluster snapshot rebuilt from apiserver/informer per cycle.
//   - GPU allocation is exclusive per physical GPU ID (no MIG/MPS slicing here).
package scheduler

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"slices"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/informer"
	"github.com/LiShuMing/xlab/labs/k8s-lab/internal/workqueue"
)

// ScorePolicy controls how feasible nodes are ranked when placing GPU Pods.
type ScorePolicy string

const (
	// PolicyBinPack prefers fuller nodes (least remaining free GPUs) so whole
	// empty nodes stay intact for large multi-GPU jobs (low fragmentation).
	PolicyBinPack ScorePolicy = "binpack"
	// PolicySpread prefers emptier nodes (most remaining free GPUs) to balance
	// load across the cluster, at the cost of higher multi-GPU fragmentation.
	PolicySpread ScorePolicy = "spread"
)

// Option configures a Scheduler.
type Option func(*Scheduler)

// WithScorePolicy selects BinPack (default) or Spread scoring.
func WithScorePolicy(p ScorePolicy) Option {
	return func(s *Scheduler) { s.policy = p }
}

// WithLogger attaches a logger; nil discards output.
func WithLogger(l *log.Logger) Option {
	return func(s *Scheduler) { s.logger = l }
}

// Scheduler binds unscheduled Pods (Spec.NodeName == "") to ready Nodes.
type Scheduler struct {
	api    *apiserver.Server
	pods   *informer.Informer
	nodes  *informer.Informer
	queue  *workqueue.Queue
	policy ScorePolicy
	logger *log.Logger

	// mu serializes ScheduleOnce so concurrent callers or worker goroutines
	// cannot double-book the same physical GPU ID within one cycle.
	mu sync.Mutex
}

// New constructs a Scheduler wired to Pod and Node informers.
// Either informer may be nil when driving ScheduleOnce directly in unit tests.
func New(api *apiserver.Server, podInf, nodeInf *informer.Informer, opts ...Option) *Scheduler {
	s := &Scheduler{
		api:    api,
		pods:   podInf,
		nodes:  nodeInf,
		queue:  workqueue.New(),
		policy: PolicyBinPack,
		logger: log.New(io.Discard, "", 0),
	}
	for _, opt := range opts {
		opt(s)
	}
	if s.logger == nil {
		s.logger = log.New(io.Discard, "", 0)
	}

	trigger := func(_ string, _ apis.Object) { s.queue.Add("reschedule") }
	if podInf != nil {
		podInf.AddHandler(informer.HandlerFuncs{
			AddFunc:    trigger,
			UpdateFunc: func(key string, _, _ apis.Object) { s.queue.Add("reschedule") },
			DeleteFunc: trigger,
		})
	}
	if nodeInf != nil {
		nodeInf.AddHandler(informer.HandlerFuncs{
			AddFunc:    trigger,
			UpdateFunc: func(key string, _, _ apis.Object) { s.queue.Add("reschedule") },
			DeleteFunc: trigger,
		})
	}
	return s
}

// Run processes scheduling triggers until ctx is cancelled.
func (s *Scheduler) Run(ctx context.Context) {
	var wg sync.WaitGroup
	wg.Go(func() { s.worker(ctx) })
	<-ctx.Done()
	s.queue.ShutDown()
	wg.Wait()
}

func (s *Scheduler) worker(ctx context.Context) {
	for {
		key, shutdown := s.queue.Get()
		if shutdown {
			return
		}
		if _, err := s.ScheduleOnce(ctx, "default"); err != nil && !errors.Is(err, context.Canceled) {
			s.logger.Printf("scheduler cycle error: %v", err)
			if ctx.Err() == nil {
				s.queue.Add(key)
			}
			select {
			case <-ctx.Done():
				s.queue.Done(key)
				return
			case <-time.After(25 * time.Millisecond):
			}
		}
		s.queue.Done(key)
	}
}

type nodeState struct {
	node     *apis.Node
	freeGPUs map[int]apis.GPUDevice
}

type placement struct {
	pod      *apis.Pod
	nodeName string
	gpuIDs   []int
}

// ScheduleOnce runs a deterministic scheduling pass over all unscheduled Pods
// in `namespace` and commits bindings through apiserver.Server. Returns the
// number of Pods newly bound during this pass.
func (s *Scheduler) ScheduleOnce(ctx context.Context, namespace string) (int, error) {
	if ctx.Err() != nil {
		return 0, ctx.Err()
	}
	s.mu.Lock()
	defer s.mu.Unlock()

	nodeObjs, err := s.api.List("nodes", namespace)
	if err != nil {
		return 0, err
	}
	podObjs, err := s.api.List("pods", namespace)
	if err != nil {
		return 0, err
	}

	cluster := make(map[string]*nodeState, len(nodeObjs))
	for _, obj := range nodeObjs {
		n := obj.(*apis.Node)
		if !n.Status.Ready || n.Spec.Unschedulable {
			continue
		}
		free := make(map[int]apis.GPUDevice, len(n.Spec.GPUs))
		for _, g := range n.Spec.GPUs {
			free[g.ID] = g
		}
		cluster[n.Name] = &nodeState{node: n, freeGPUs: free}
	}

	var unscheduled []*apis.Pod
	for _, obj := range podObjs {
		p := obj.(*apis.Pod)
		if p.Status.Phase == apis.PodSucceeded || p.Status.Phase == apis.PodFailed {
			continue
		}
		if p.Spec.NodeName != "" {
			if ns, ok := cluster[p.Spec.NodeName]; ok {
				for _, gid := range p.Spec.AssignedGPUs {
					delete(ns.freeGPUs, gid)
				}
			}
			continue
		}
		unscheduled = append(unscheduled, p)
	}

	sort.Slice(unscheduled, func(i, j int) bool {
		ti, tj := unscheduled[i].CreationTimestamp, unscheduled[j].CreationTimestamp
		if !ti.Equal(tj) {
			return ti.Before(tj)
		}
		return unscheduled[i].Name < unscheduled[j].Name
	})

	type schedUnit struct {
		groupName    string
		minAvailable int
		pods         []*apis.Pod
	}
	var units []*schedUnit
	groupIdx := make(map[string]int)
	for _, p := range unscheduled {
		if p.Spec.PodGroup == "" || p.Spec.MinAvailable <= 1 {
			units = append(units, &schedUnit{minAvailable: 1, pods: []*apis.Pod{p}})
			continue
		}
		if idx, ok := groupIdx[p.Spec.PodGroup]; ok {
			units[idx].pods = append(units[idx].pods, p)
		} else {
			groupIdx[p.Spec.PodGroup] = len(units)
			units = append(units, &schedUnit{
				groupName:    p.Spec.PodGroup,
				minAvailable: p.Spec.MinAvailable,
				pods:         []*apis.Pod{p},
			})
		}
	}

	var commits []placement
	for _, u := range units {
		if len(u.pods) < u.minAvailable {
			continue
		}
		planned, ok := s.planUnitAtomic(cluster, u.pods[:u.minAvailable])
		if !ok {
			continue
		}
		commits = append(commits, planned...)
	}

	bound := 0
	for _, pl := range commits {
		if ctx.Err() != nil {
			return bound, ctx.Err()
		}
		updated := pl.pod.DeepCopyObject().(*apis.Pod)
		updated.Spec.NodeName = pl.nodeName
		updated.Spec.AssignedGPUs = append([]int(nil), pl.gpuIDs...)
		rv, _ := strconv.ParseUint(pl.pod.ResourceVersion, 10, 64)
		if _, err := s.api.Update("pods", updated, rv); err != nil {
			return bound, err
		}
		bound++
	}
	return bound, nil
}

func (s *Scheduler) planUnitAtomic(cluster map[string]*nodeState, pods []*apis.Pod) ([]placement, bool) {
	planned := make([]placement, 0, len(pods))
	type reserved struct {
		nodeName string
		devs     []apis.GPUDevice
	}
	var undo []reserved

	for _, p := range pods {
		nodeName, devs, ok := s.selectNodeAndGPUs(cluster, p)
		if !ok {
			for i := len(undo) - 1; i >= 0; i-- {
				ns := cluster[undo[i].nodeName]
				for _, d := range undo[i].devs {
					ns.freeGPUs[d.ID] = d
				}
			}
			return nil, false
		}
		ns := cluster[nodeName]
		gpuIDs := make([]int, 0, len(devs))
		for _, d := range devs {
			delete(ns.freeGPUs, d.ID)
			gpuIDs = append(gpuIDs, d.ID)
		}
		sort.Ints(gpuIDs)
		undo = append(undo, reserved{nodeName: nodeName, devs: devs})
		planned = append(planned, placement{pod: p, nodeName: nodeName, gpuIDs: gpuIDs})
	}
	return planned, true
}

func (s *Scheduler) selectNodeAndGPUs(cluster map[string]*nodeState, pod *apis.Pod) (string, []apis.GPUDevice, bool) {
	reqGPUs := pod.Spec.GPURequest
	reqMem := pod.Spec.GPUMemoryMiB

	nodeNames := make([]string, 0, len(cluster))
	for name := range cluster {
		nodeNames = append(nodeNames, name)
	}
	sort.Strings(nodeNames)

	bestScore := -1
	bestNode := ""
	var bestDevs []apis.GPUDevice

	for _, name := range nodeNames {
		ns := cluster[name]
		if reqGPUs == 0 {
			score := 100
			if s.policy == PolicySpread {
				score += len(ns.freeGPUs)
			}
			if score > bestScore {
				bestScore = score
				bestNode = name
				bestDevs = nil
			}
			continue
		}

		var eligible []apis.GPUDevice
		for _, d := range ns.freeGPUs {
			if d.MemoryMiB >= reqMem {
				eligible = append(eligible, d)
			}
		}
		if len(eligible) < reqGPUs {
			continue
		}

		chosen, sameNVLink := pickBestGPUs(eligible, reqGPUs)
		remainingFree := len(ns.freeGPUs) - reqGPUs
		totalGPUs := max(1, len(ns.node.Spec.GPUs))

		var score int
		if s.policy == PolicyBinPack {
			score = 100 - (remainingFree*100)/totalGPUs
		} else {
			score = (remainingFree * 100) / totalGPUs
		}
		if reqGPUs >= 2 && sameNVLink {
			score += 200
		}

		if score > bestScore {
			bestScore = score
			bestNode = name
			bestDevs = chosen
		}
	}

	if bestNode == "" {
		return "", nil, false
	}
	return bestNode, bestDevs, true
}

func pickBestGPUs(eligible []apis.GPUDevice, k int) ([]apis.GPUDevice, bool) {
	byGroup := make(map[string][]apis.GPUDevice)
	for _, d := range eligible {
		byGroup[d.NVLinkGroup] = append(byGroup[d.NVLinkGroup], d)
	}

	groupKeys := make([]string, 0, len(byGroup))
	for g := range byGroup {
		groupKeys = append(groupKeys, g)
	}
	sort.Strings(groupKeys)

	var bestIsland []apis.GPUDevice
	for _, g := range groupKeys {
		devs := byGroup[g]
		if g == "" || len(devs) < k {
			continue
		}
		sort.Slice(devs, func(i, j int) bool { return devs[i].ID < devs[j].ID })
		if bestIsland == nil || len(devs) < len(bestIsland) {
			bestIsland = devs
		}
	}
	if bestIsland != nil {
		return append([]apis.GPUDevice(nil), bestIsland[:k]...), true
	}

	sorted := append([]apis.GPUDevice(nil), eligible...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].ID < sorted[j].ID })
	return sorted[:k], false
}

// ClusterMetrics summarizes fragmentation and GPU utilization for evaluation.
type ClusterMetrics struct {
	TotalGPUs             int
	AllocatedGPUs         int
	FreeGPUs              int
	MaxContiguousNodeFree int
	FragmentationRatio    float64
}

// ComputeClusterMetrics calculates utilization and fragmentation for a target large job size.
func ComputeClusterMetrics(api *apiserver.Server, namespace string, targetJobGPUs int) (ClusterMetrics, error) {
	nodeObjs, err := api.List("nodes", namespace)
	if err != nil {
		return ClusterMetrics{}, err
	}
	podObjs, err := api.List("pods", namespace)
	if err != nil {
		return ClusterMetrics{}, err
	}

	usedByNode := make(map[string]map[int]struct{})
	for _, obj := range podObjs {
		p := obj.(*apis.Pod)
		if p.Spec.NodeName == "" || p.Status.Phase == apis.PodSucceeded || p.Status.Phase == apis.PodFailed {
			continue
		}
		if usedByNode[p.Spec.NodeName] == nil {
			usedByNode[p.Spec.NodeName] = make(map[int]struct{})
		}
		for _, gid := range p.Spec.AssignedGPUs {
			usedByNode[p.Spec.NodeName][gid] = struct{}{}
		}
	}

	var m ClusterMetrics
	strandedFree := 0
	for _, obj := range nodeObjs {
		n := obj.(*apis.Node)
		total := len(n.Spec.GPUs)
		used := len(usedByNode[n.Name])
		free := total - used
		m.TotalGPUs += total
		m.AllocatedGPUs += used
		m.FreeGPUs += free
		if free > m.MaxContiguousNodeFree {
			m.MaxContiguousNodeFree = free
		}
		if free > 0 && free < targetJobGPUs {
			strandedFree += free
		}
	}
	if m.FreeGPUs > 0 {
		m.FragmentationRatio = float64(strandedFree) / float64(m.FreeGPUs)
	}
	return m, nil
}

// VerifyClusterInvariants checks strict GPU conservation across the cluster.
func VerifyClusterInvariants(api *apiserver.Server, namespace string) error {
	nodeObjs, err := api.List("nodes", namespace)
	if err != nil {
		return err
	}
	podObjs, err := api.List("pods", namespace)
	if err != nil {
		return err
	}

	nodeGPUs := make(map[string]map[int]apis.GPUDevice, len(nodeObjs))
	for _, obj := range nodeObjs {
		n := obj.(*apis.Node)
		m := make(map[int]apis.GPUDevice, len(n.Spec.GPUs))
		for _, g := range n.Spec.GPUs {
			m[g.ID] = g
		}
		nodeGPUs[n.Name] = m
	}

	type gpuKey struct {
		node string
		id   int
	}
	owner := make(map[gpuKey]string)

	for _, obj := range podObjs {
		p := obj.(*apis.Pod)
		if p.Spec.NodeName == "" || p.Status.Phase == apis.PodSucceeded || p.Status.Phase == apis.PodFailed {
			continue
		}
		devs, ok := nodeGPUs[p.Spec.NodeName]
		if !ok {
			return fmt.Errorf("pod %s bound to unknown node %q", p.Name, p.Spec.NodeName)
		}
		if len(p.Spec.AssignedGPUs) != p.Spec.GPURequest {
			return fmt.Errorf("pod %s requested %d GPUs but assigned %v", p.Name, p.Spec.GPURequest, p.Spec.AssignedGPUs)
		}
		seenLocal := make([]int, 0, len(p.Spec.AssignedGPUs))
		for _, gid := range p.Spec.AssignedGPUs {
			if slices.Contains(seenLocal, gid) {
				return fmt.Errorf("pod %s has duplicate GPU ID %d", p.Name, gid)
			}
			seenLocal = append(seenLocal, gid)
			dev, exists := devs[gid]
			if !exists {
				return fmt.Errorf("pod %s assigned non-existent GPU %d on node %s", p.Name, gid, p.Spec.NodeName)
			}
			if dev.MemoryMiB < p.Spec.GPUMemoryMiB {
				return fmt.Errorf("pod %s needs %d MiB VRAM, got GPU %d with %d MiB", p.Name, p.Spec.GPUMemoryMiB, gid, dev.MemoryMiB)
			}
			gk := gpuKey{node: p.Spec.NodeName, id: gid}
			if prev, conflict := owner[gk]; conflict {
				return fmt.Errorf("GPU %s/%d double-booked by pods %s and %s", p.Spec.NodeName, gid, prev, p.Name)
			}
			owner[gk] = p.Name
		}
	}
	return nil
}
