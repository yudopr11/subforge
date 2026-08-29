.PHONY: all build test clean lint release

BINARY_NAME=subforge
BUILD_DIR=bin
DIST_DIR=dist
VERSION=$(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
LDFLAGS=-s -w -X main.version=$(VERSION)

all: test build

build:
	CGO_ENABLED=0 go build -ldflags="$(LDFLAGS)" -o $(BUILD_DIR)/$(BINARY_NAME) ./cmd/subforge

test:
	go test -v -race ./...

lint:
	go vet ./...

clean:
	rm -rf $(BUILD_DIR) $(DIST_DIR)

release:
	@echo "Building release binaries for all platforms..."
	@mkdir -p $(DIST_DIR)

	@echo "→ linux/amd64"
	CGO_ENABLED=0 GOOS=linux   GOARCH=amd64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-linux-x64        ./cmd/subforge

	@echo "→ linux/arm64"
	CGO_ENABLED=0 GOOS=linux   GOARCH=arm64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-linux-arm64      ./cmd/subforge

	@echo "→ darwin/amd64"
	CGO_ENABLED=0 GOOS=darwin  GOARCH=amd64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-darwin-x64       ./cmd/subforge

	@echo "→ darwin/arm64"
	CGO_ENABLED=0 GOOS=darwin  GOARCH=arm64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-darwin-arm64     ./cmd/subforge

	@echo "→ windows/amd64"
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-windows-x64.exe  ./cmd/subforge

	@echo "→ windows/arm64"
	CGO_ENABLED=0 GOOS=windows GOARCH=arm64 go build -ldflags="$(LDFLAGS)" -o $(DIST_DIR)/subforge-windows-arm64.exe ./cmd/subforge

	@echo ""
	@echo "✓ All binaries built in $(DIST_DIR)/:"
	@ls -lh $(DIST_DIR)/
