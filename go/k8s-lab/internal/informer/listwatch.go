package informer

import (
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apis"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/apiserver"
	"github.com/LiShuMing/xlab/go/k8s-lab/internal/store"
)

// ServerListWatch adapts an *apiserver.Server into the ListWatch interface for
// a single REST resource. It mirrors how client-go builds a ListerWatcher from
// a typed client: bind the resource path once, expose List/Watch.
type ServerListWatch struct {
	server   *apiserver.Server
	resource string // e.g. "pods"
}

// NewServerListWatch returns a ListWatch for the given resource.
func NewServerListWatch(server *apiserver.Server, resource string) *ServerListWatch {
	return &ServerListWatch{server: server, resource: resource}
}

// List implements ListWatch using the store's atomic snapshot+revision.
func (slw *ServerListWatch) List() ([]apis.Object, uint64) {
	return slw.server.Storage().ListWithRevision("/" + slw.resource + "/")
}

// Watch implements ListWatch by starting a store watch after sinceRV.
func (slw *ServerListWatch) Watch(sinceRV uint64) (<-chan store.WatchEvent, func()) {
	ch, stop, err := slw.server.Watch(slw.resource, sinceRV)
	if err != nil {
		// The resource was validated at construction in practice; if it is
		// somehow unknown here, return a closed channel so the Reflector
		// relists and surfaces the empty state rather than blocking forever.
		closed := make(chan store.WatchEvent)
		close(closed)
		return closed, func() {}
	}
	return ch, stop
}
