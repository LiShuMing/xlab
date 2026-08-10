package repository

import (
	"fmt"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

// ── Entity ──

func (s *Store) AddEntity(entity domain.Entity) error {
	if entity.ID == "" {
		entity.ID = domain.NewID("ent")
	}
	if entity.CreatedAt.IsZero() {
		entity.CreatedAt = time.Now()
	}
	s.State.Entities = append(s.State.Entities, entity)
	return s.Save()
}

func (s *Store) EntityByID(id string) (*domain.Entity, error) {
	for i := range s.State.Entities {
		if s.State.Entities[i].ID == id {
			return &s.State.Entities[i], nil
		}
	}
	return nil, fmt.Errorf("entity %q not found", id)
}

func (s *Store) EntityByName(name string) (*domain.Entity, error) {
	for i := range s.State.Entities {
		if s.State.Entities[i].Name == name || s.State.Entities[i].CanonicalName == name {
			return &s.State.Entities[i], nil
		}
	}
	return nil, fmt.Errorf("entity name %q not found", name)
}

// ── UserEntityEdge ──

func (s *Store) UpsertUserEntityEdge(edge domain.UserEntityEdge) error {
	edge.UpdatedAt = time.Now()
	for i := range s.State.Edges {
		if s.State.Edges[i].UserID == edge.UserID && s.State.Edges[i].EntityID == edge.EntityID {
			s.State.Edges[i] = edge
			return s.Save()
		}
	}
	s.State.Edges = append(s.State.Edges, edge)
	return s.Save()
}

func (s *Store) UserEntityEdges(userID string) ([]domain.UserEntityEdge, error) {
	var out []domain.UserEntityEdge
	for _, e := range s.State.Edges {
		if e.UserID == userID {
			out = append(out, e)
		}
	}
	return out, nil
}

// ── UserContextSummary ──

func (s *Store) AddUserContextSummary(summary domain.UserContextSummary) error {
	if summary.ID == "" {
		summary.ID = domain.NewID("sum")
	}
	if summary.CreatedAt.IsZero() {
		summary.CreatedAt = time.Now()
	}
	if summary.UpdatedAt.IsZero() {
		summary.UpdatedAt = time.Now()
	}
	s.State.Summaries = append(s.State.Summaries, summary)
	return s.Save()
}

func (s *Store) UserContextSummaries(userID string) ([]domain.UserContextSummary, error) {
	var out []domain.UserContextSummary
	for _, sm := range s.State.Summaries {
		if sm.UserID == userID {
			out = append(out, sm)
		}
	}
	return out, nil
}

// ── ExtractionJob ──

func (s *Store) AddExtractionJob(job domain.ExtractionJob) error {
	if job.ID == "" {
		job.ID = domain.NewID("job")
	}
	if job.CreatedAt.IsZero() {
		job.CreatedAt = time.Now()
	}
	s.State.Jobs = append(s.State.Jobs, job)
	return s.Save()
}

func (s *Store) UpdateExtractionJob(id string, update func(*domain.ExtractionJob) error) (*domain.ExtractionJob, error) {
	for i := range s.State.Jobs {
		if s.State.Jobs[i].ID == id {
			if update != nil {
				if err := update(&s.State.Jobs[i]); err != nil {
					return nil, err
				}
			}
			if err := s.Save(); err != nil {
				return nil, err
			}
			j := s.State.Jobs[i]
			return &j, nil
		}
	}
	return nil, fmt.Errorf("extraction job %q not found", id)
}

func (s *Store) ExtractionJobsByUser(userID string) ([]domain.ExtractionJob, error) {
	var out []domain.ExtractionJob
	for _, j := range s.State.Jobs {
		if j.UserID == userID {
			out = append(out, j)
		}
	}
	return out, nil
}
