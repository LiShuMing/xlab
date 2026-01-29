package main

import "fmt"

func minMutation(start string, end string, bank []string) int {
	if start == end {
		return 0
	}
	if len(bank) == 0 {
		return -1
	}
	bucket := make(map[string]struct{})
	for _, gene := range bank {
		bucket[gene] = struct{}{}
	}
	// if end is not in bank, return -1
	if _, ok := bucket[end]; !ok {
		return -1
	}
	queue := []string{start}
	visited := make(map[string]bool)
	visited[start] = true
	steps := 0
	for len(queue) > 0 {
		levelSize := len(queue)
		for i := 0; i < levelSize; i++ {
			cur := queue[0]
			queue = queue[1:]
			for gene := range bucket {
				if _, ok := visited[gene]; ok {
					continue // skip visited genes
				}
				if isOneMutation(cur, gene) {
					queue = append(queue, gene)
					visited[gene] = true
					if gene == end {
						return steps + 1
					}
				}
			}
		}
		steps++
	}
	return -1
}

func isOneMutation(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	diff := 0
	for i := range a {
		if a[i] != b[i] {
			diff++
		}
		if diff > 1 {
			return false
		}
	}
	return diff == 1
}

func main() {
	fmt.Println(minMutation("AACCGGTT", "AACCGGTA", []string{"AACCGGTA", "AACCGGTT", "AAACGGTT"}))
	fmt.Println(minMutation("AACCGGTT", "AAACGGTA", []string{"AACCGGTA", "AACCGGTT", "AAACGGTT"}))
	fmt.Println(minMutation("AACCGGTT", "AAACGGTA", []string{"AACCGGTA", "AACCGGTT", "AAACGGTT"}))
	fmt.Println(minMutation("AACCGGTT", "AAACGGTA", []string{"AACCGGTA", "AACCGCTA", "AAACGGTA"}))
	// Test case: AAAACCCC -> CCCCCCCC
	// Path: AAAACCCC -> AAACCCCA -> AACCCCCA -> AACCCCCC -> CCCCCCCC (4 steps)
	fmt.Println(minMutation("AAAACCCC", "CCCCCCCC", []string{"AAAACCCA", "AAACCCCA", "AACCCCCA", "AACCCCCC", "ACCCCCCC", "CCCCCCCC", "AAACCCCC", "AACCCCCC"}))
}
