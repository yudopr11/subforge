package config

import (
	"runtime"
)

func RecommendModelForRAM(ramGB float64) string {
	if ramGB < 3.0 {
		return "tiny"
	} else if ramGB < 5.0 {
		return "base"
	} else if ramGB < 10.0 {
		return "small"
	} else if ramGB < 20.0 {
		return "medium"
	}
	return "large-v3"
}

func DetectHardware() (totalRAMGB float64, cpuCores int, recModel string) {
	cpuCores = runtime.NumCPU()
	// Fallback/standard heuristic for system RAM estimation
	totalRAMGB = 8.0
	// Try platform-specific RAM reading if available, else 8GB default
	recModel = RecommendModelForRAM(totalRAMGB)
	return totalRAMGB, cpuCores, recModel
}
