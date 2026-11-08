// Package apis defines the typed objects that flow through the mini control
// plane. These mirror, in heavily simplified form, the shapes of real
// Kubernetes API objects (k8s.io/api/core/v1, apps/v1).
//
// The learning goal here is to see WHY Kubernetes objects are structured the
// way they are:
//
//   - Every object carries TypeMeta (what kind of thing is this) and
//     ObjectMeta (identity + bookkeeping: name, namespace, uid,
//     resourceVersion, labels).
//   - Spec is the DESIRED state, written by the user.
//   - Status is the OBSERVED state, written by controllers/kubelet.
//   - Controllers never touch Spec; they read Spec and drive Status (and
//     child objects) toward it. This split is the heart of the
//     level-triggered, declarative model.
package apis

import (
	"maps"
	"time"
)

// Phase is the high-level lifecycle state of a Pod. Real Kubernetes has the
// same enum on PodStatus.Phase.
type Phase string

const (
	// PodPending means the Pod has been accepted but is not yet running
	// (in real k8s: being scheduled, images pulling). Our kubelet simulator
	// flips Pending -> Running.
	PodPending Phase = "Pending"
	// PodRunning means the Pod's containers are up.
	PodRunning Phase = "Running"
	// PodSucceeded means all containers terminated successfully.
	PodSucceeded Phase = "Succeeded"
	// PodFailed means all containers terminated, at least one in failure.
	PodFailed Phase = "Failed"
)

// TypeMeta describes an individual object in an API response or request. It
// mirrors metav1.TypeMeta.
type TypeMeta struct {
	Kind       string `json:"kind"`
	APIVersion string `json:"apiVersion"`
}

// ObjectMeta is metadata that all persisted resources must have. It mirrors a
// small subset of metav1.ObjectMeta.
type ObjectMeta struct {
	Name              string            `json:"name"`
	Namespace         string            `json:"namespace"`
	UID               string            `json:"uid"`
	ResourceVersion   string            `json:"resourceVersion"`
	Labels            map[string]string `json:"labels,omitempty"`
	CreationTimestamp time.Time         `json:"creationTimestamp"`
	DeletionTimestamp *time.Time        `json:"deletionTimestamp,omitempty"`
}

// Object is the interface implemented by every API object. It mirrors
// runtime.Object + metav1.Object, collapsed for simplicity.
//
// DeepCopyObject is essential: the store hands out copies so that a caller
// mutating an object can never corrupt the authoritative state or race with
// another watcher. Real Kubernetes gets this from generated deepcopy code.
type Object interface {
	GetTypeMeta() *TypeMeta
	GetObjectMeta() *ObjectMeta
	DeepCopyObject() Object
}

// Key returns the store path for an object: /<resource>/<namespace>/<name>.
// resource is supplied by the caller because it is not derivable from the
// object alone (it depends on the REST mapping, e.g. "pods", "replicasets").
func Key(resource, namespace, name string) string {
	if namespace == "" {
		namespace = "default"
	}
	return "/" + resource + "/" + namespace + "/" + name
}

// ---------------------------------------------------------------------------
// Pod
// ---------------------------------------------------------------------------

// PodSpec is the desired configuration of a Pod (subset).
type PodSpec struct {
	// NodeName is set by the scheduler in real k8s. In this lab the
	// ReplicaSet controller leaves it empty and the kubelet simulator adopts
	// any unscheduled Pod, standing in for scheduling+binding.
	NodeName string `json:"nodeName,omitempty"`
	// Image is a stand-in for containers[0].image; the simulator does not run
	// anything, it just tracks lifecycle.
	Image string `json:"image,omitempty"`
}

// PodStatus is the observed state of a Pod (subset).
type PodStatus struct {
	Phase Phase `json:"phase"`
}

// Pod mirrors corev1.Pod.
type Pod struct {
	TypeMeta   `json:",inline"`
	ObjectMeta `json:"metadata"`
	Spec       PodSpec   `json:"spec"`
	Status     PodStatus `json:"status"`
}

func (p *Pod) GetTypeMeta() *TypeMeta     { return &p.TypeMeta }
func (p *Pod) GetObjectMeta() *ObjectMeta { return &p.ObjectMeta }

// DeepCopyObject returns a deep copy so callers never share mutable state.
func (p *Pod) DeepCopyObject() Object {
	if p == nil {
		return nil
	}
	out := *p
	out.Labels = copyLabels(p.Labels)
	if p.DeletionTimestamp != nil {
		t := *p.DeletionTimestamp
		out.DeletionTimestamp = &t
	}
	return &out
}

// ---------------------------------------------------------------------------
// ReplicaSet
// ---------------------------------------------------------------------------

// LabelSelector selects objects whose labels are a superset of MatchLabels.
// Mirrors metav1.LabelSelector (MatchLabels only; no expressions).
type LabelSelector struct {
	MatchLabels map[string]string `json:"matchLabels,omitempty"`
}

// Matches reports whether the given labels satisfy the selector. An empty or
// nil selector matches everything, as in real Kubernetes.
func (s LabelSelector) Matches(labels map[string]string) bool {
	for k, v := range s.MatchLabels {
		if labels[k] != v {
			return false
		}
	}
	return true
}

// ReplicaSetSpec is the desired replica count + selector.
type ReplicaSetSpec struct {
	Replicas int32           `json:"replicas"`
	Selector LabelSelector   `json:"selector"`
	Template PodTemplateSpec `json:"template"`
}

// PodTemplateSpec describes the Pod a ReplicaSet creates for each replica.
type PodTemplateSpec struct {
	ObjectMeta `json:"metadata"`
	Spec       PodSpec `json:"spec"`
}

// DeepCopy returns a deep copy of the template.
func (t PodTemplateSpec) DeepCopy() PodTemplateSpec {
	out := t
	out.Labels = copyLabels(t.Labels)
	return out
}

// ReplicaSetStatus is the observed state maintained by the controller.
type ReplicaSetStatus struct {
	Replicas      int32 `json:"replicas"`
	ReadyReplicas int32 `json:"readyReplicas"`
}

// ReplicaSet mirrors apps/v1.ReplicaSet.
type ReplicaSet struct {
	TypeMeta   `json:",inline"`
	ObjectMeta `json:"metadata"`
	Spec       ReplicaSetSpec   `json:"spec"`
	Status     ReplicaSetStatus `json:"status"`
}

func (r *ReplicaSet) GetTypeMeta() *TypeMeta     { return &r.TypeMeta }
func (r *ReplicaSet) GetObjectMeta() *ObjectMeta { return &r.ObjectMeta }

// DeepCopyObject returns a deep copy.
func (r *ReplicaSet) DeepCopyObject() Object {
	if r == nil {
		return nil
	}
	out := *r
	out.Labels = copyLabels(r.Labels)
	out.Spec.Selector.MatchLabels = copyLabels(r.Spec.Selector.MatchLabels)
	out.Spec.Template = r.Spec.Template.DeepCopy()
	if r.DeletionTimestamp != nil {
		t := *r.DeletionTimestamp
		out.DeletionTimestamp = &t
	}
	return &out
}

// copyLabels deep-copies a label map, tolerating nil.
func copyLabels(in map[string]string) map[string]string {
	if in == nil {
		return nil
	}
	out := make(map[string]string, len(in))
	maps.Copy(out, in)
	return out
}
