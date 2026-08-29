.PHONY: all build test clean lint release

BINARY_NAME=subforge
BUILD_DIR=bin

all: test build

build:
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BUILD_DIR)/$(BINARY_NAME) ./cmd/subforge

test:
	go test -v -race ./...

lint:
	go vet ./...

clean:
	rm -rf $(BUILD_DIR) dist
