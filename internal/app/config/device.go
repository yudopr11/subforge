package config

import (
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strconv"
	"strings"
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

func readLinuxRAM() (float64, error) {
	data, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return 0, err
	}
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "MemTotal:") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				kb, err := strconv.ParseFloat(fields[1], 64)
				if err == nil {
					return kb / (1024 * 1024), nil
				}
			}
		}
	}
	return 0, fmt.Errorf("MemTotal not found in /proc/meminfo")
}

func readDarwinRAM() (float64, error) {
	out, err := exec.Command("sysctl", "-n", "hw.memsize").Output()
	if err != nil {
		return 0, err
	}
	bytes, err := strconv.ParseFloat(strings.TrimSpace(string(out)), 64)
	if err != nil {
		return 0, err
	}
	return bytes / (1024 * 1024 * 1024), nil
}

func readWindowsRAM() (float64, error) {
	out, err := exec.Command("powershell", "-NoProfile", "-NonInteractive", "-Command", "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize").Output()
	if err != nil {
		return 0, err
	}
	kb, err := strconv.ParseFloat(strings.TrimSpace(string(out)), 64)
	if err != nil {
		return 0, err
	}
	return kb / (1024 * 1024), nil
}

func DetectSystemRAM() float64 {
	var ram float64
	var err error

	switch runtime.GOOS {
	case "linux":
		ram, err = readLinuxRAM()
	case "darwin":
		ram, err = readDarwinRAM()
	case "windows":
		ram, err = readWindowsRAM()
	}

	if err == nil && ram > 0.5 {
		return ram
	}

	// Default fallback heuristic if OS query is blocked/unavailable
	return 8.0
}

func DetectHardware() (totalRAMGB float64, cpuCores int, recModel string) {
	cpuCores = runtime.NumCPU()
	totalRAMGB = DetectSystemRAM()
	recModel = RecommendModelForRAM(totalRAMGB)
	return totalRAMGB, cpuCores, recModel
}
