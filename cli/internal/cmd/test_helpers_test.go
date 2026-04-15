package cmd

import (
	"bytes"
	"context"
	"encoding/json"
	"path/filepath"
	"testing"

	"github.com/willem/newsbuddy/cli/internal/config"
)

type testCLI struct {
	app        *App
	stdout     *bytes.Buffer
	stderr     *bytes.Buffer
	configPath string
}

func newTestCLI(t *testing.T, cfg config.FileConfig) testCLI {
	t.Helper()

	configPath := filepath.Join(t.TempDir(), "config.json")
	if err := config.Save(configPath, cfg); err != nil {
		t.Fatalf("save config: %v", err)
	}

	stdout := &bytes.Buffer{}
	stderr := &bytes.Buffer{}

	return testCLI{
		app:        New("test", stdout, stderr),
		stdout:     stdout,
		stderr:     stderr,
		configPath: configPath,
	}
}

func (c testCLI) run(args ...string) int {
	argv := append([]string{"--config", c.configPath}, args...)
	return c.app.Execute(context.Background(), argv)
}

func (c testCLI) envelope(t *testing.T) map[string]any {
	t.Helper()

	var envelope map[string]any
	if err := json.Unmarshal(c.stdout.Bytes(), &envelope); err != nil {
		t.Fatalf("decode output: %v", err)
	}
	return envelope
}

func requireErrorMessage(t *testing.T, envelope map[string]any, want string) {
	t.Helper()

	errorPayload, ok := envelope["error"].(map[string]any)
	if !ok {
		t.Fatalf("expected error payload object: %#v", envelope["error"])
	}
	if errorPayload["message"] != want {
		t.Fatalf("unexpected message: %#v", errorPayload["message"])
	}
}
