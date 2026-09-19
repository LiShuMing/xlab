// Package apiserver implements the typed front door of the mini control
// plane — the analogue of kube-apiserver.
//
// What it teaches about the Kubernetes API layer:
//
//   - The apiserver is the ONLY component that talks to storage. Controllers
//     never touch etcd directly; they go through the API. Centralising access
//     is what makes validation, defaulting and watch delivery uniform.
//   - Defaulting: clients may omit namespace (defaults to "default"), uid,
//     creationTimestamp and TypeMeta; the server fills them in on write,
//     exactly like real API machinery.
//   - Validation: writes are rejected before they reach storage, so the store
//     only ever contains well-formed objects.
//   - Status subresource: UpdateStatus is a separate path that only accepts
//     Status changes. Splitting the write paths is how real Kubernetes stops a
//     controller from clobbering a user's Spec (and vice versa) when both
//     write the same object concurrently.
package apiserver

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// Server is the typed API facade over the backing store.
type Server struct {
	store *store.Store
	now   func() time.Time // injectable for deterministic tests
}

// New returns a Server backed by the given store.
func New(s *store.Store) *Server {
	return &Server{store: s, now: time.Now}
}

// Storage exposes the underlying store for components that need the raw
// watch/revision primitives (informers). Writes must still go through the
// Server so defaulting and validation are not bypassed.
func (a *Server) Storage() *store.Store { return a.store }

// ---------------------------------------------------------------------------
// Resource registry: REST resource name -> Kind + fresh typed object
// ---------------------------------------------------------------------------

// kindInfo binds a REST resource to its type metadata and a constructor.
type kindInfo struct {
	kind       string
	apiVersion string
	newObj     func() apis.Object
}

// registry mirrors the RESTMapper/scheme of a real apiserver: it knows which
// Go type backs each URL path segment.
var registry = map[string]kindInfo{
	"pods": {
		kind:       "Pod",
		apiVersion: "v1",
		newObj:     func() apis.Object { return &apis.Pod{} },
	},
	"replicasets": {
		kind:       "ReplicaSet",
		apiVersion: "apps/v1",
		newObj:     func() apis.Object { return &apis.ReplicaSet{} },
	},
}

func lookup(resource string) (kindInfo, error) {
	ki, ok := registry[resource]
	if !ok {
		return kindInfo{}, fmt.Errorf("apiserver: unknown resource %q", resource)
	}
	return ki, nil
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

// Create defaults, validates and stores a new object under the given REST
// resource (e.g. "pods"). The caller keeps ownership of obj; the server works
// on a deep copy and returns the stored (stamped) copy.
func (a *Server) Create(resource string, obj apis.Object) (apis.Object, error) {
	ki, err := lookup(resource)
	if err != nil {
		return nil, err
	}
	out := obj.DeepCopyObject()
	a.defaultObject(ki, out)
	if err := validate(resource, out); err != nil {
		return nil, err
	}
	key := apis.Key(resource, out.GetObjectMeta().Namespace, out.GetObjectMeta().Name)
	return a.store.Create(key, out)
}

// Update replaces an existing object under optimistic concurrency. The caller
// must pass the resourceVersion it read (0 = blind write). TypeMeta and the
// identity fields are protected: the server keeps the stored object's UID and
// creationTimestamp regardless of what the client sends, just like the real
// apiserver rejects attempts to change immutable metadata.
func (a *Server) Update(resource string, obj apis.Object, expectedResourceVersion uint64) (apis.Object, error) {
	ki, err := lookup(resource)
	if err != nil {
		return nil, err
	}
	key := apis.Key(resource, obj.GetObjectMeta().Namespace, obj.GetObjectMeta().Name)
	cur, err := a.store.Get(key)
	if err != nil {
		return nil, err
	}
	out := obj.DeepCopyObject()
	// Identity is owned by the server, never by the client.
	out.GetObjectMeta().UID = cur.GetObjectMeta().UID
	out.GetObjectMeta().CreationTimestamp = cur.GetObjectMeta().CreationTimestamp
	a.defaultObject(ki, out)
	if err := validate(resource, out); err != nil {
		return nil, err
	}
	return a.store.Update(key, out, expectedResourceVersion)
}

// UpdateStatus is the status-subresource write path. It takes the Spec of the
// currently stored object and applies only the Status from the client's copy.
// This is the mechanism that makes "users own Spec, controllers own Status"
// enforceable rather than merely conventional.
func (a *Server) UpdateStatus(resource string, obj apis.Object, expectedResourceVersion uint64) (apis.Object, error) {
	key := apis.Key(resource, obj.GetObjectMeta().Namespace, obj.GetObjectMeta().Name)
	cur, err := a.store.Get(key)
	if err != nil {
		return nil, err
	}
	merged := cur.DeepCopyObject()
	if err := copyStatus(merged, obj); err != nil {
		return nil, err
	}
	return a.store.Update(key, merged, expectedResourceVersion)
}

// copyStatus transfers only the Status sub-struct from src into dst.
func copyStatus(dst, src apis.Object) error {
	switch d := dst.(type) {
	case *apis.Pod:
		s, ok := src.(*apis.Pod)
		if !ok {
			return fmt.Errorf("apiserver: status source is %T, want *Pod", src)
		}
		d.Status = s.Status
	case *apis.ReplicaSet:
		s, ok := src.(*apis.ReplicaSet)
		if !ok {
			return fmt.Errorf("apiserver: status source is %T, want *ReplicaSet", src)
		}
		d.Status = s.Status
	default:
		return fmt.Errorf("apiserver: status update unsupported for %T", dst)
	}
	return nil
}

// Delete removes an object by REST resource, namespace and name.
func (a *Server) Delete(resource, namespace, name string) (apis.Object, error) {
	if _, err := lookup(resource); err != nil {
		return nil, err
	}
	return a.store.Delete(apis.Key(resource, namespace, name))
}

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

// Get returns one object. ErrNotFound (from the store) propagates as-is.
func (a *Server) Get(resource, namespace, name string) (apis.Object, error) {
	if _, err := lookup(resource); err != nil {
		return nil, err
	}
	return a.store.Get(apis.Key(resource, namespace, name))
}

// List returns all objects of a resource in one namespace, sorted by name.
func (a *Server) List(resource, namespace string) ([]apis.Object, error) {
	if _, err := lookup(resource); err != nil {
		return nil, err
	}
	if namespace == "" {
		namespace = "default"
	}
	prefix := "/" + resource + "/" + namespace + "/"
	return a.store.List(prefix), nil
}

// Watch starts a watch on a resource's key prefix. It is a thin passthrough:
// the informer layer builds caching on top of it.
func (a *Server) Watch(resource string, sinceResourceVersion uint64) (<-chan store.WatchEvent, func(), error) {
	if _, err := lookup(resource); err != nil {
		return nil, nil, err
	}
	ch, stop := a.store.Watch("/"+resource+"/", sinceResourceVersion)
	return ch, stop, nil
}

// ---------------------------------------------------------------------------
// Defaulting and validation
// ---------------------------------------------------------------------------

// defaultObject fills in server-owned fields the client may have omitted.
func (a *Server) defaultObject(ki kindInfo, obj apis.Object) {
	meta := obj.GetObjectMeta()
	tm := obj.GetTypeMeta()
	tm.Kind = ki.kind
	tm.APIVersion = ki.apiVersion
	if meta.Namespace == "" {
		meta.Namespace = "default"
	}
	if meta.UID == "" {
		meta.UID = newUID()
	}
	if meta.CreationTimestamp.IsZero() {
		meta.CreationTimestamp = a.now()
	}
}

// newUID returns a random 16-byte hex string, standing in for a UUID.
func newUID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		// crypto/rand should never fail; fall back to something unique enough
		// for a single-process lab rather than panicking.
		return fmt.Sprintf("uid-%d", time.Now().UnixNano())
	}
	return hex.EncodeToString(b[:])
}

// validate rejects malformed writes before they reach storage. Real
// validation is generated from OpenAPI schemas plus CEL rules; we hand-code
// the checks that matter for the lab's objects.
func validate(resource string, obj apis.Object) error {
	meta := obj.GetObjectMeta()
	if meta.Name == "" {
		return fmt.Errorf("apiserver: %s name must not be empty", resource)
	}
	if err := validateName(meta.Name); err != nil {
		return fmt.Errorf("apiserver: invalid %s name %q: %w", resource, meta.Name, err)
	}
	switch o := obj.(type) {
	case *apis.ReplicaSet:
		if o.Spec.Replicas < 0 {
			return fmt.Errorf("apiserver: replicasets %q: spec.replicas must be >= 0, got %d", meta.Name, o.Spec.Replicas)
		}
		if len(o.Spec.Selector.MatchLabels) == 0 {
			return fmt.Errorf("apiserver: replicasets %q: selector must not be empty (it would adopt every pod)", meta.Name)
		}
	case *apis.Pod:
		// Pods carry no extra invariants in the lab beyond the name check.
	}
	return nil
}

// validateName enforces a simplified DNS-1123 label: lowercase alphanumerics
// and '-', starting and ending alphanumeric. Kubernetes names must satisfy
// this because they end up in DNS records and file paths.
func validateName(name string) error {
	if len(name) > 253 {
		return fmt.Errorf("must be at most 253 characters")
	}
	isAlnum := func(c byte) bool {
		return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
	}
	for i := range len(name) {
		c := name[i]
		ok := isAlnum(c) || c == '-' || c == '.'
		if !ok {
			return fmt.Errorf("character %q at position %d is not one of [a-z0-9.-]", c, i)
		}
	}
	if !isAlnum(name[0]) || !isAlnum(name[len(name)-1]) {
		return fmt.Errorf("must start and end with an alphanumeric character")
	}
	return nil
}
