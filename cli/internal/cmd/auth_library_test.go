package cmd

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/willem/news_app/cli/internal/config"
)

func TestAuthLoginPersistsAPIKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/api/agent/cli/link/start":
			writeJSON(t, w, map[string]any{
				"session_id":             "session-123",
				"status":                 "pending",
				"poll_token":             "poll-123",
				"approve_url":            "newsly://cli-link?session_id=session-123&approve_token=approve-123",
				"expires_at":             "2026-04-04T18:00:00Z",
				"poll_interval_seconds":  2,
			})
		case r.Method == http.MethodGet && r.URL.Path == "/api/agent/cli/link/session-123":
			if got := r.URL.Query().Get("poll_token"); got != "poll-123" {
				t.Fatalf("unexpected poll token: %q", got)
			}
			writeJSON(t, w, map[string]any{
				"session_id": "session-123",
				"status":     "approved",
				"expires_at": "2026-04-04T18:00:00Z",
				"api_key":    "newsly_ak_linked_secret",
				"key_prefix": "newsly_ak_linked",
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	configPath := filepath.Join(t.TempDir(), "config.json")

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	app := New("test", &stdout, &stderr)

	exitCode := app.Execute(context.Background(), []string{
		"--config", configPath,
		"--server", server.URL,
		"auth", "login",
		"--poll-interval", "1ms",
		"--poll-timeout", "1s",
	})

	if exitCode != 0 {
		t.Fatalf("expected exit 0, got %d stdout=%s stderr=%s", exitCode, stdout.String(), stderr.String())
	}

	cfg, err := config.Load(configPath)
	if err != nil {
		t.Fatalf("load config: %v", err)
	}
	if cfg.ServerURL != server.URL {
		t.Fatalf("expected server to persist, got %q", cfg.ServerURL)
	}
	if cfg.APIKey != "newsly_ak_linked_secret" {
		t.Fatalf("expected linked API key to persist, got %q", cfg.APIKey)
	}
	if !strings.Contains(stderr.String(), "newsly://cli-link?") {
		t.Fatalf("expected QR/link instructions on stderr, got %q", stderr.String())
	}
}

func TestLibrarySyncDownloadsAndPrunesFiles(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer newsly_ak_test" {
			t.Fatalf("unexpected auth header: %q", got)
		}
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/agent/library/manifest":
			writeJSON(t, w, map[string]any{
				"generated_at":   "2026-04-04T18:00:00Z",
				"include_source": false,
				"documents": []map[string]any{
					{
						"relative_path":   "article/example/new-doc__2026-04-03__summary__c1.md",
						"content_id":      1,
						"variant":         "summary",
						"updated_at":      "2026-04-04T17:59:00Z",
						"size_bytes":      12,
						"checksum_sha256": "new-sha",
					},
				},
			})
		case r.Method == http.MethodGet && r.URL.Path == "/api/agent/library/file":
			if got := r.URL.Query().Get("path"); got != "article/example/new-doc__2026-04-03__summary__c1.md" {
				t.Fatalf("unexpected file path query: %q", got)
			}
			writeJSON(t, w, map[string]any{
				"relative_path":   "article/example/new-doc__2026-04-03__summary__c1.md",
				"content_id":      1,
				"variant":         "summary",
				"updated_at":      "2026-04-04T17:59:00Z",
				"checksum_sha256": "new-sha",
				"text":            "# Hello\n",
			})
		default:
			t.Fatalf("unexpected request: %s %s", r.Method, r.URL.Path)
		}
	}))
	defer server.Close()

	libraryRoot := filepath.Join(t.TempDir(), "library")
	stalePath := filepath.Join(libraryRoot, "article", "example", "old-doc.md")
	if err := os.MkdirAll(filepath.Dir(stalePath), 0o755); err != nil {
		t.Fatalf("mkdir stale dir: %v", err)
	}
	if err := os.WriteFile(stalePath, []byte("old"), 0o644); err != nil {
		t.Fatalf("write stale file: %v", err)
	}
	manifestPath := filepath.Join(libraryRoot, ".newsly-agent-manifest.json")
	if err := os.WriteFile(manifestPath, []byte(`{"files":{"article/example/old-doc.md":"old-sha"}}`), 0o644); err != nil {
		t.Fatalf("write stale manifest: %v", err)
	}

	configPath := filepath.Join(t.TempDir(), "config.json")
	if err := config.Save(configPath, config.FileConfig{
		ServerURL:   server.URL,
		APIKey:      "newsly_ak_test",
		LibraryRoot: libraryRoot,
	}); err != nil {
		t.Fatalf("save config: %v", err)
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	app := New("test", &stdout, &stderr)

	exitCode := app.Execute(context.Background(), []string{
		"--config", configPath,
		"library", "sync",
	})

	if exitCode != 0 {
		t.Fatalf("expected exit 0, got %d stdout=%s stderr=%s", exitCode, stdout.String(), stderr.String())
	}

	newPath := filepath.Join(libraryRoot, "article", "example", "new-doc__2026-04-03__summary__c1.md")
	data, err := os.ReadFile(newPath)
	if err != nil {
		t.Fatalf("read synced file: %v", err)
	}
	if string(data) != "# Hello\n" {
		t.Fatalf("unexpected synced file contents: %q", string(data))
	}
	if _, err := os.Stat(stalePath); !os.IsNotExist(err) {
		t.Fatalf("expected stale file to be pruned, stat err=%v", err)
	}
	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatalf("read manifest: %v", err)
	}
	if !strings.Contains(string(manifestBytes), "new-doc__2026-04-03__summary__c1.md") {
		t.Fatalf("expected manifest to update, got %s", string(manifestBytes))
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected no stderr output, got %q", stderr.String())
	}
}
