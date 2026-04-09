package cmd

import (
	"context"

	"github.com/spf13/cobra"

	"github.com/willem/news_app/cli/internal/config"
)

func (a *App) newConfigCommand() *cobra.Command {
	configCmd := &cobra.Command{
		Use:   "config",
		Short: "Manage local CLI configuration",
	}

	setCmd := &cobra.Command{
		Use:   "set",
		Short: "Set one configuration value",
	}
	setServer := &cobra.Command{
		Use:   "server <url>",
		Short: "Persist the server URL",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return a.updateConfig(
				cmd,
				"config.set-server",
				func(current config.FileConfig) config.FileConfig {
					current.ServerURL = args[0]
					return current
				},
				func(path string, cfg config.FileConfig) any {
					return map[string]any{
						"config_path": path,
						"server_url":  cfg.ServerURL,
					}
				},
			)
		},
	}
	setAPIKey := &cobra.Command{
		Use:   "api-key <key>",
		Short: "Persist the API key",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return a.updateConfig(
				cmd,
				"config.set-api-key",
				func(current config.FileConfig) config.FileConfig {
					current.APIKey = args[0]
					return current
				},
				func(path string, cfg config.FileConfig) any {
					return map[string]any{
						"config_path": path,
						"api_key_set": cfg.APIKey != "",
					}
				},
			)
		},
	}
	setLibraryRoot := &cobra.Command{
		Use:   "library-root <path>",
		Short: "Persist the local markdown sync directory",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return a.updateConfig(
				cmd,
				"config.set-library-root",
				func(current config.FileConfig) config.FileConfig {
					current.LibraryRoot = args[0]
					return current
				},
				func(path string, cfg config.FileConfig) any {
					return map[string]any{
						"config_path":  path,
						"library_root": cfg.LibraryRoot,
					}
				},
			)
		},
	}

	showCmd := &cobra.Command{
		Use:   "show",
		Short: "Show the effective CLI configuration",
		RunE: func(cmd *cobra.Command, _ []string) error {
			return a.runLocal(cmd, "config.show", func(_ context.Context) (commandResult, error) {
				runtimeCfg, err := a.resolveRuntimeConfig()
				if err != nil {
					return commandResult{}, err
				}
				return commandResult{
					Data: map[string]any{
						"config_path":  runtimeCfg.Path,
						"server_url":   runtimeCfg.ServerURL,
						"api_key_set":  runtimeCfg.APIKey != "",
						"api_key_mask": config.MaskedAPIKey(runtimeCfg.APIKey),
						"library_root": runtimeCfg.LibraryRoot,
					},
				}, nil
			})
		},
	}

	setCmd.AddCommand(setServer, setAPIKey, setLibraryRoot)
	configCmd.AddCommand(setCmd, showCmd)
	return configCmd
}
