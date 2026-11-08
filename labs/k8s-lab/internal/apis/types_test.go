package apis

import (
	"testing"
	"time"
)

func TestKeyDefaultsNamespace(t *testing.T) {
	if got := Key("pods", "", "web-1"); got != "/pods/default/web-1" {
		t.Errorf("Key with empty ns = %q, want /pods/default/web-1", got)
	}
	if got := Key("pods", "kube-system", "dns"); got != "/pods/kube-system/dns" {
		t.Errorf("Key = %q", got)
	}
}

func TestLabelSelectorMatches(t *testing.T) {
	sel := LabelSelector{MatchLabels: map[string]string{"app": "web", "tier": "fe"}}

	cases := []struct {
		labels map[string]string
		want   bool
	}{
		{map[string]string{"app": "web", "tier": "fe", "extra": "x"}, true}, // superset
		{map[string]string{"app": "web", "tier": "fe"}, true},               // exact
		{map[string]string{"app": "web"}, false},                            // missing key
		{map[string]string{"app": "db", "tier": "fe"}, false},               // wrong value
		{nil, false},
	}
	for _, c := range cases {
		if got := sel.Matches(c.labels); got != c.want {
			t.Errorf("Matches(%v) = %v, want %v", c.labels, got, c.want)
		}
	}

	// An empty selector matches everything, as in real Kubernetes.
	empty := LabelSelector{}
	if !empty.Matches(map[string]string{"any": "thing"}) {
		t.Error("empty selector should match all")
	}
	if !empty.Matches(nil) {
		t.Error("empty selector should match nil labels")
	}
}

func TestPodDeepCopyIsolation(t *testing.T) {
	p := &Pod{
		ObjectMeta: ObjectMeta{
			Name:   "web-1",
			Labels: map[string]string{"app": "web"},
		},
		Spec: PodSpec{Image: "nginx"},
	}
	cp := p.DeepCopyObject().(*Pod)

	cp.Labels["app"] = "mutated"
	cp.Spec.Image = "redis"

	if p.Labels["app"] != "web" {
		t.Errorf("original labels mutated through copy: %v", p.Labels)
	}
	if p.Spec.Image != "nginx" {
		t.Errorf("original spec mutated through copy: %v", p.Spec.Image)
	}
}

func TestPodDeepCopyDeletionTimestamp(t *testing.T) {
	original := time.Date(2026, 9, 19, 12, 0, 0, 0, time.UTC)
	p := &Pod{ObjectMeta: ObjectMeta{Name: "x"}}
	// Set a DeletionTimestamp and verify the copy gets an independent pointer.
	p.DeletionTimestamp = &original
	cp := p.DeepCopyObject().(*Pod)
	if cp.DeletionTimestamp == p.DeletionTimestamp {
		t.Error("DeletionTimestamp pointer must be deep-copied, not shared")
	}
	other := time.Date(2000, 1, 1, 0, 0, 0, 0, time.UTC)
	*cp.DeletionTimestamp = other
	if !p.DeletionTimestamp.Equal(original) {
		t.Error("mutating the copy's DeletionTimestamp changed the original")
	}
}

func TestNilPodDeepCopy(t *testing.T) {
	var p *Pod
	if p.DeepCopyObject() != nil {
		t.Error("nil Pod DeepCopyObject should return nil")
	}
	var r *ReplicaSet
	if r.DeepCopyObject() != nil {
		t.Error("nil ReplicaSet DeepCopyObject should return nil")
	}
}

func TestReplicaSetDeepCopyIsolation(t *testing.T) {
	r := &ReplicaSet{
		ObjectMeta: ObjectMeta{Name: "web", Labels: map[string]string{"app": "web"}},
		Spec: ReplicaSetSpec{
			Replicas: 3,
			Selector: LabelSelector{MatchLabels: map[string]string{"app": "web"}},
			Template: PodTemplateSpec{
				ObjectMeta: ObjectMeta{Labels: map[string]string{"app": "web"}},
				Spec:       PodSpec{Image: "nginx"},
			},
		},
	}
	cp := r.DeepCopyObject().(*ReplicaSet)

	cp.Labels["app"] = "mutated"
	cp.Spec.Selector.MatchLabels["app"] = "mutated"
	cp.Spec.Template.Labels["app"] = "mutated"
	cp.Spec.Template.Spec.Image = "redis"
	cp.Spec.Replicas = 99

	if r.Labels["app"] != "web" {
		t.Error("RS labels mutated through copy")
	}
	if r.Spec.Selector.MatchLabels["app"] != "web" {
		t.Error("RS selector mutated through copy")
	}
	if r.Spec.Template.Labels["app"] != "web" {
		t.Error("RS template labels mutated through copy")
	}
	if r.Spec.Template.Spec.Image != "nginx" {
		t.Error("RS template spec mutated through copy")
	}
	if r.Spec.Replicas != 3 {
		t.Error("RS replicas mutated through copy")
	}
}

func TestReplicaSetDeepCopyDeletionTimestamp(t *testing.T) {
	original := time.Date(2026, 9, 19, 12, 0, 0, 0, time.UTC)
	r := &ReplicaSet{ObjectMeta: ObjectMeta{Name: "web"}}
	r.DeletionTimestamp = &original
	cp := r.DeepCopyObject().(*ReplicaSet)
	if cp.DeletionTimestamp == r.DeletionTimestamp {
		t.Error("DeletionTimestamp pointer must be deep-copied")
	}
}

func TestPodTemplateDeepCopyNilLabels(t *testing.T) {
	tmpl := PodTemplateSpec{ObjectMeta: ObjectMeta{Name: "x"}} // nil Labels
	cp := tmpl.DeepCopy()
	if cp.Labels != nil {
		t.Error("nil labels should stay nil, not become an empty map")
	}
}

func TestCopyLabelsNil(t *testing.T) {
	if got := copyLabels(nil); got != nil {
		t.Errorf("copyLabels(nil) = %v, want nil", got)
	}
}

func TestTypeMetaAccessors(t *testing.T) {
	p := &Pod{}
	tm := p.GetTypeMeta()
	tm.Kind = "Pod"
	if p.TypeMeta.Kind != "Pod" {
		t.Error("GetTypeMeta should return a live pointer to the embedded TypeMeta")
	}
	r := &ReplicaSet{}
	if r.GetObjectMeta() != &r.ObjectMeta {
		t.Error("GetObjectMeta should return a live pointer to the embedded ObjectMeta")
	}
}
