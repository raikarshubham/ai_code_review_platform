package words

func CountWords(words []string) map[string]int {
	var counts map[string]int
	for _, w := range words {
		// expect: bug
		counts[w]++
	}
	return counts
}
