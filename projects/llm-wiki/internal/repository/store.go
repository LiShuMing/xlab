package repository

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"sort"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
)

type Store struct {
	Path    string
	DataDir string
	State   State
}

type Backend string

const (
	BackendFile     Backend = "file"
	BackendPostgres Backend = "postgres"
)

type Options struct {
	Backend     Backend
	DataDir     string
	DatabaseURL string
}

type Repository interface {
	Init() error
	Describe() string
	DataDirPath() string

	UserByHandle(handle string) (*domain.User, error)
	UserByID(id string) (*domain.User, error)
	ListUsers() []domain.User
	AddUser(user domain.User) error

	AddAsset(asset domain.SourceAsset) error
	AssetByID(id string) (*domain.SourceAsset, error)
	AssetsByUser(userID string) []domain.SourceAsset

	AddContext(item domain.ContextItem) error
	ContextByID(id string) (*domain.ContextItem, error)
	UpdateContext(id string, update func(*domain.ContextItem) error) (*domain.ContextItem, error)
	ContextsByUser(userID string) []domain.ContextItem
	AllContexts() []domain.ContextItem

	AddContextVector(vector domain.ContextVector) error
	ContextVectorsByUser(userID string) []domain.ContextVector
	ContextVectorByContextID(contextID string) (*domain.ContextVector, error)

	AddAudit(audit domain.UsageAudit) error
	AddModelCall(call domain.ModelCallLog) error
	ModelCalls() []domain.ModelCallLog
	AddMatch(match domain.MatchResult) error
	MatchesByUser(userID string) []domain.MatchResult

	// Cascade delete helpers
	DeleteContextVector(contextID string) error
	DeleteMatchesByContextID(contextID string) error
	DeleteSummariesBySourceContextID(contextID string) error
	DeleteJobsByContextID(contextID string) error
	DeleteContextsByAssetID(assetID string) ([]domain.ContextItem, error)
	DeleteAsset(id string) (*domain.SourceAsset, error)
	FindExpiredContexts(now time.Time) ([]domain.ContextItem, error)

	// Entity
	AddEntity(entity domain.Entity) error
	EntityByID(id string) (*domain.Entity, error)
	EntityByName(name string) (*domain.Entity, error)

	// UserEntityEdge
	UpsertUserEntityEdge(edge domain.UserEntityEdge) error
	UserEntityEdges(userID string) ([]domain.UserEntityEdge, error)

	// UserContextSummary
	AddUserContextSummary(summary domain.UserContextSummary) error
	UserContextSummaries(userID string) ([]domain.UserContextSummary, error)

	// ExtractionJob
	AddExtractionJob(job domain.ExtractionJob) error
	UpdateExtractionJob(id string, update func(*domain.ExtractionJob) error) (*domain.ExtractionJob, error)
	ExtractionJobsByUser(userID string) ([]domain.ExtractionJob, error)
}

type State struct {
	Users       []domain.User               `json:"users"`
	Assets      []domain.SourceAsset        `json:"assets"`
	Contexts    []domain.ContextItem        `json:"contexts"`
	Vectors     []domain.ContextVector      `json:"vectors"`
	Audits      []domain.UsageAudit         `json:"audits"`
	ModelCalls  []domain.ModelCallLog       `json:"model_calls"`
	Matches     []domain.MatchResult        `json:"matches"`
	Entities    []domain.Entity             `json:"entities"`
	Edges       []domain.UserEntityEdge     `json:"edges"`
	Summaries   []domain.UserContextSummary `json:"summaries"`
	Jobs        []domain.ExtractionJob      `json:"jobs"`
	Initialized time.Time                   `json:"initialized"`
}

func Open(dataDir string) (*Store, error) {
	repo, err := OpenWithOptions(Options{Backend: BackendFile, DataDir: dataDir})
	if err != nil {
		return nil, err
	}
	store, ok := repo.(*Store)
	if !ok {
		return nil, fmt.Errorf("repository backend %T is not file store", repo)
	}
	return store, nil
}

func OpenWithOptions(opts Options) (Repository, error) {
	if opts.Backend == "" {
		opts.Backend = BackendFile
	}
	switch opts.Backend {
	case BackendFile:
		return OpenFile(opts.DataDir)
	case BackendPostgres:
		return OpenPostgres(opts)
	default:
		return nil, fmt.Errorf("unknown repository backend %q", opts.Backend)
	}
}

func OpenFile(dataDir string) (*Store, error) {
	if dataDir == "" {
		dataDir = "data"
	}
	path := filepath.Join(dataDir, "context_poc.json")
	store := &Store{Path: path, DataDir: dataDir}
	if err := store.Load(); err != nil {
		return nil, err
	}
	return store, nil
}

func (s *Store) Describe() string {
	return "file:" + s.Path
}

func (s *Store) DataDirPath() string {
	return s.DataDir
}

func (s *Store) Load() error {
	raw, err := os.ReadFile(s.Path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			s.State = State{}
			return nil
		}
		return err
	}
	if len(raw) == 0 {
		s.State = State{}
		return nil
	}
	return json.Unmarshal(raw, &s.State)
}

func (s *Store) Save() error {
	if err := os.MkdirAll(filepath.Dir(s.Path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(s.State, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.Path, append(raw, '\n'), 0o644)
}

func (s *Store) Init() error {
	if err := os.MkdirAll(filepath.Join(s.DataDir, "assets"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(s.DataDir, "processed"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(s.DataDir, "exports"), 0o755); err != nil {
		return err
	}
	if s.State.Initialized.IsZero() {
		s.State.Initialized = time.Now()
	}
	return s.Save()
}

func (s *Store) UserByHandle(handle string) (*domain.User, error) {
	for i := range s.State.Users {
		if s.State.Users[i].Handle == handle {
			return &s.State.Users[i], nil
		}
	}
	return nil, fmt.Errorf("user %q not found", handle)
}

func (s *Store) UserByID(id string) (*domain.User, error) {
	for i := range s.State.Users {
		if s.State.Users[i].ID == id {
			return &s.State.Users[i], nil
		}
	}
	return nil, fmt.Errorf("user id %q not found", id)
}

func (s *Store) ListUsers() []domain.User {
	out := append([]domain.User(nil), s.State.Users...)
	return out
}

func (s *Store) AddUser(user domain.User) error {
	if _, err := s.UserByHandle(user.Handle); err == nil {
		return fmt.Errorf("user %q already exists", user.Handle)
	}
	s.State.Users = append(s.State.Users, user)
	return s.Save()
}

func (s *Store) AddAsset(asset domain.SourceAsset) error {
	for _, existing := range s.State.Assets {
		if existing.UserID == asset.UserID && existing.SHA256 != "" && existing.SHA256 == asset.SHA256 {
			return fmt.Errorf("duplicate asset sha256=%s", asset.SHA256)
		}
	}
	s.State.Assets = append(s.State.Assets, asset)
	return s.Save()
}

func (s *Store) AddContext(item domain.ContextItem) error {
	s.State.Contexts = append(s.State.Contexts, item)
	return s.Save()
}

func (s *Store) ContextByID(id string) (*domain.ContextItem, error) {
	for i := range s.State.Contexts {
		if s.State.Contexts[i].ID == id {
			return &s.State.Contexts[i], nil
		}
	}
	return nil, fmt.Errorf("context %q not found", id)
}

func (s *Store) UpdateContext(id string, update func(*domain.ContextItem) error) (*domain.ContextItem, error) {
	ctx, err := s.ContextByID(id)
	if err != nil {
		return nil, err
	}
	if update != nil {
		if err := update(ctx); err != nil {
			return nil, err
		}
	}
	if err := s.Save(); err != nil {
		return nil, err
	}
	return ctx, nil
}

func (s *Store) AssetByID(id string) (*domain.SourceAsset, error) {
	for i := range s.State.Assets {
		if s.State.Assets[i].ID == id {
			return &s.State.Assets[i], nil
		}
	}
	return nil, fmt.Errorf("asset %q not found", id)
}

func (s *Store) ContextsByUser(userID string) []domain.ContextItem {
	var out []domain.ContextItem
	for _, item := range s.State.Contexts {
		if item.UserID == userID {
			out = append(out, item)
		}
	}
	slices.SortFunc(out, func(a, b domain.ContextItem) int {
		return b.CreatedAt.Compare(a.CreatedAt)
	})
	return out
}

func (s *Store) AllContexts() []domain.ContextItem {
	out := append([]domain.ContextItem(nil), s.State.Contexts...)
	return out
}

func (s *Store) AssetsByUser(userID string) []domain.SourceAsset {
	var out []domain.SourceAsset
	for _, item := range s.State.Assets {
		if item.UserID == userID {
			out = append(out, item)
		}
	}
	return out
}

func (s *Store) AddContextVector(vector domain.ContextVector) error {
	for i := range s.State.Vectors {
		if s.State.Vectors[i].ContextID == vector.ContextID && s.State.Vectors[i].VectorType == vector.VectorType {
			s.State.Vectors[i] = vector
			return s.Save()
		}
	}
	s.State.Vectors = append(s.State.Vectors, vector)
	return s.Save()
}

func (s *Store) ContextVectorsByUser(userID string) []domain.ContextVector {
	var out []domain.ContextVector
	for _, vector := range s.State.Vectors {
		if vector.UserID == userID {
			out = append(out, vector)
		}
	}
	return out
}

func (s *Store) ContextVectorByContextID(contextID string) (*domain.ContextVector, error) {
	for i := range s.State.Vectors {
		if s.State.Vectors[i].ContextID == contextID {
			return &s.State.Vectors[i], nil
		}
	}
	return nil, fmt.Errorf("context vector for %q not found", contextID)
}

func (s *Store) ModelCalls() []domain.ModelCallLog {
	out := append([]domain.ModelCallLog(nil), s.State.ModelCalls...)
	return out
}

func (s *Store) AddAudit(audit domain.UsageAudit) error {
	s.State.Audits = append(s.State.Audits, audit)
	return s.Save()
}

func (s *Store) AddModelCall(call domain.ModelCallLog) error {
	s.State.ModelCalls = append(s.State.ModelCalls, call)
	return s.Save()
}

func (s *Store) AddMatch(match domain.MatchResult) error {
	s.State.Matches = append(s.State.Matches, match)
	return s.Save()
}

func (s *Store) MatchesByUser(userID string) []domain.MatchResult {
	var out []domain.MatchResult
	for _, match := range s.State.Matches {
		if match.UserID == userID {
			out = append(out, match)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		return out[i].CreatedAt.After(out[j].CreatedAt)
	})
	return out
}

// DeleteContextVector removes the vector for a given context from the store.
// If no vector is found, it is a no-op (idempotent).
func (s *Store) DeleteContextVector(contextID string) error {
	for i := range s.State.Vectors {
		if s.State.Vectors[i].ContextID == contextID {
			s.State.Vectors = append(s.State.Vectors[:i], s.State.Vectors[i+1:]...)
			return s.Save()
		}
	}
	return nil
}

// DeleteMatchesByContextID removes all matches that reference the given contextID.
func (s *Store) DeleteMatchesByContextID(contextID string) error {
	filtered := s.State.Matches[:0]
	for _, match := range s.State.Matches {
		found := false
		for _, cid := range match.ContextIDs {
			if cid == contextID {
				found = true
				break
			}
		}
		if !found {
			filtered = append(filtered, match)
		}
	}
	s.State.Matches = filtered
	return s.Save()
}

// DeleteSummariesBySourceContextID removes all summaries that reference the given contextID.
func (s *Store) DeleteSummariesBySourceContextID(contextID string) error {
	filtered := s.State.Summaries[:0]
	for _, summary := range s.State.Summaries {
		found := false
		for _, scid := range summary.SourceContextIDs {
			if scid == contextID {
				found = true
				break
			}
		}
		if !found {
			filtered = append(filtered, summary)
		}
	}
	s.State.Summaries = filtered
	return s.Save()
}

// DeleteJobsByContextID removes all jobs whose input references the given contextID.
func (s *Store) DeleteJobsByContextID(contextID string) error {
	filtered := s.State.Jobs[:0]
	for _, job := range s.State.Jobs {
		if v, ok := job.Input["context_id"].(string); ok && v == contextID {
			continue
		}
		filtered = append(filtered, job)
	}
	s.State.Jobs = filtered
	return s.Save()
}

// DeleteContextsByAssetID removes all non-deleted contexts for an asset and returns them.
func (s *Store) DeleteContextsByAssetID(assetID string) ([]domain.ContextItem, error) {
	var deleted []domain.ContextItem
	filtered := s.State.Contexts[:0]
	for _, ctx := range s.State.Contexts {
		if ctx.SourceAssetID == assetID && ctx.State != domain.StateDeleted {
			deleted = append(deleted, ctx)
		} else {
			filtered = append(filtered, ctx)
		}
	}
	s.State.Contexts = filtered
	if err := s.Save(); err != nil {
		return nil, err
	}
	return deleted, nil
}

// DeleteAsset removes an asset by ID and returns the deleted asset.
func (s *Store) DeleteAsset(id string) (*domain.SourceAsset, error) {
	for i := range s.State.Assets {
		if s.State.Assets[i].ID == id {
			assetCopy := s.State.Assets[i]
			s.State.Assets = append(s.State.Assets[:i], s.State.Assets[i+1:]...)
			if err := s.Save(); err != nil {
				return nil, err
			}
			return &assetCopy, nil
		}
	}
	return nil, fmt.Errorf("asset %q not found", id)
}

// FindExpiredContexts returns all active contexts whose ExpiresAt is non-nil and <= now.
func (s *Store) FindExpiredContexts(now time.Time) ([]domain.ContextItem, error) {
	var expired []domain.ContextItem
	for _, ctx := range s.State.Contexts {
		if ctx.ExpiresAt != nil && !ctx.ExpiresAt.IsZero() && !ctx.ExpiresAt.After(now) && ctx.State == domain.StateActive {
			expired = append(expired, ctx)
		}
	}
	return expired, nil
}
