package cmd

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/cobra"

	"github.com/willem/news_app/cli/internal/config"
	"github.com/willem/news_app/cli/internal/runtime"
)

const libraryManifestFilename = ".newsly-agent-manifest.json"

type localLibraryManifest struct {
	Files map[string]string `json:"files"`
}

func (a *App) newLibraryCommand() *cobra.Command {
	libraryCmd := &cobra.Command{
		Use:   "library",
		Short: "Sync the personal markdown library to local disk",
	}

	var args struct {
		Dir           string
		IncludeSource bool
	}

	syncCmd := &cobra.Command{
		Use:   "sync",
		Short: "Download the current markdown library diff to local disk",
		RunE: func(cmd *cobra.Command, _ []string) error {
			runtimeCfg, err := config.ResolveRuntime(a.opts.ConfigPath, a.opts.ServerURL, a.opts.APIKey)
			if err != nil {
				return a.renderError("library.sync", err)
			}
			if err := runtimeCfg.ValidateRemote(); err != nil {
				return a.renderErrorWithPath("library.sync", runtimeCfg.Path, err)
			}

			client, err := runtime.NewClient(runtimeCfg, a.opts.Timeout)
			if err != nil {
				return a.renderErrorWithPath("library.sync", runtimeCfg.Path, err)
			}

			libraryRoot := runtimeCfg.LibraryRoot
			if strings.TrimSpace(args.Dir) != "" {
				libraryRoot = args.Dir
			}
			if libraryRoot == "" {
				return a.renderError("library.sync", errors.New("missing library root"))
			}
			libraryRoot = filepath.Clean(libraryRoot)
			if err := os.MkdirAll(libraryRoot, 0o755); err != nil {
				return a.renderError("library.sync", err)
			}

			remoteManifest, err := client.GetLibraryManifest(cmd.Context(), args.IncludeSource)
			if err != nil {
				return a.renderErrorWithPath("library.sync", runtimeCfg.Path, err)
			}
			localManifest, err := loadLocalLibraryManifest(
				filepath.Join(libraryRoot, libraryManifestFilename),
			)
			if err != nil {
				return a.renderError("library.sync", err)
			}

			downloaded := 0
			unchanged := 0
			remoteFiles := make(map[string]string, len(remoteManifest.Documents))
			for _, document := range remoteManifest.Documents {
				remoteFiles[document.RelativePath] = document.ChecksumSHA256
				targetPath, err := safeLibraryPath(libraryRoot, document.RelativePath)
				if err != nil {
					return a.renderError("library.sync", err)
				}
				if localManifest.Files[document.RelativePath] == document.ChecksumSHA256 {
					if _, err := os.Stat(targetPath); err == nil {
						unchanged++
						continue
					}
				}

				filePayload, err := client.GetLibraryFile(cmd.Context(), document.RelativePath)
				if err != nil {
					return a.renderErrorWithPath("library.sync", runtimeCfg.Path, err)
				}
				if err := os.MkdirAll(filepath.Dir(targetPath), 0o755); err != nil {
					return a.renderError("library.sync", err)
				}
				if err := os.WriteFile(targetPath, []byte(filePayload.Text), 0o644); err != nil {
					return a.renderError("library.sync", err)
				}
				downloaded++
			}

			deleted := 0
			for relativePath := range localManifest.Files {
				if _, ok := remoteFiles[relativePath]; ok {
					continue
				}
				targetPath, err := safeLibraryPath(libraryRoot, relativePath)
				if err != nil {
					return a.renderError("library.sync", err)
				}
				if err := os.Remove(targetPath); err == nil || os.IsNotExist(err) {
					deleted++
				} else {
					return a.renderError("library.sync", err)
				}
			}

			if err := saveLocalLibraryManifest(filepath.Join(libraryRoot, libraryManifestFilename), remoteFiles); err != nil {
				return a.renderError("library.sync", err)
			}

			return a.renderSuccess("library.sync", commandResult{
				Data: map[string]any{
					"library_root":   libraryRoot,
					"downloaded":     downloaded,
					"deleted":        deleted,
					"unchanged":      unchanged,
					"document_count": len(remoteManifest.Documents),
				},
			})
		},
	}

	syncCmd.Flags().StringVar(&args.Dir, "dir", "", "Override the local sync directory")
	syncCmd.Flags().BoolVar(&args.IncludeSource, "include-source", false, "Also sync source/full-text markdown")

	libraryCmd.AddCommand(syncCmd)
	return libraryCmd
}

func loadLocalLibraryManifest(path string) (localLibraryManifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return localLibraryManifest{Files: map[string]string{}}, nil
		}
		return localLibraryManifest{}, err
	}
	var manifest localLibraryManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return localLibraryManifest{}, err
	}
	if manifest.Files == nil {
		manifest.Files = map[string]string{}
	}
	return manifest, nil
}

func saveLocalLibraryManifest(path string, files map[string]string) error {
	manifest := localLibraryManifest{Files: files}
	payload, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	return os.WriteFile(path, payload, 0o644)
}

func safeLibraryPath(root string, relativePath string) (string, error) {
	cleanRoot := filepath.Clean(root)
	targetPath := filepath.Clean(filepath.Join(cleanRoot, filepath.FromSlash(relativePath)))
	rel, err := filepath.Rel(cleanRoot, targetPath)
	if err != nil {
		return "", err
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", errors.New("library path escapes the sync root")
	}
	return targetPath, nil
}
