package service

import "time"

func (a *App) ExpireTTL() (int, error) {
	now := time.Now()
	expired, err := a.Store.FindExpiredContexts(now)
	if err != nil {
		return 0, err
	}
	count := 0
	for _, ctx := range expired {
		if _, err := a.DeleteContext(ctx.ID); err != nil {
			continue
		}
		count++
	}
	return count, nil
}
