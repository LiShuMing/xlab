package store

// EventType classifies a watch event, mirroring watch.EventType in client-go.
type EventType string

const (
	// Added fires when a key that did not exist is created.
	Added EventType = "ADDED"
	// Modified fires when an existing key is updated.
	Modified EventType = "MODIFIED"
	// Deleted fires when a key is removed.
	Deleted EventType = "DELETED"
)

// WatchEvent is a single change delivered to a watcher. It mirrors
// watch.Event: a type plus the object AFTER the change (for Deleted, the
// last known state).
type WatchEvent struct {
	Type EventType
	// Key is the store path the event applies to. It is not part of the
	// client-go watch.Event API (there, the key is implied by the object's
	// metadata), but the store needs it to match watcher prefixes.
	Key    string
	Object Object
	// ResourceVersion is the global revision at which this change occurred.
	// Watchers use it to resume after a disconnect without missing or
	// duplicating events — the same contract Kubernetes exposes.
	ResourceVersion uint64
}
