package cmd

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/spf13/cobra"

	"github.com/willem/news_app/cli/internal/config"
	"github.com/willem/news_app/cli/internal/runtime"
)

func (a *App) newAuthCommand() *cobra.Command {
	authCmd := &cobra.Command{
		Use:   "auth",
		Short: "Authenticate and link the CLI to a Newsly account",
	}

	var args struct {
		DeviceName string
		Wait       waitFlags
	}

	loginCmd := &cobra.Command{
		Use:   "login",
		Short: "Start QR login and persist the linked API key",
		RunE: func(cmd *cobra.Command, _ []string) error {
			runtimeCfg, err := config.ResolveRuntime(a.opts.ConfigPath, a.opts.ServerURL, a.opts.APIKey)
			if err != nil {
				return a.renderError("auth.login", err)
			}
			if err := runtimeCfg.ValidateServerOnly(); err != nil {
				return a.renderErrorWithPath("auth.login", runtimeCfg.Path, err)
			}
			if args.Wait.Interval <= 0 {
				return a.renderError("auth.login", errors.New("poll-interval must be greater than zero"))
			}

			client, err := runtime.NewClient(runtimeCfg, a.opts.Timeout)
			if err != nil {
				return a.renderErrorWithPath("auth.login", runtimeCfg.Path, err)
			}

			deviceName := args.DeviceName
			if deviceName == "" {
				deviceName = runtime.DefaultDeviceName()
			}

			started, err := client.StartCLILink(cmd.Context(), deviceName)
			if err != nil {
				return a.renderErrorWithPath("auth.login", runtimeCfg.Path, err)
			}

			fmt.Fprintf(a.stderr, "Scan this link in the Newsly app to approve CLI access:\n%s\n\n", started.ApproveURL)

			polled, err := waitForCLILink(cmd.Context(), client, started.SessionID, started.PollToken, args.Wait.Interval, args.Wait.Timeout)
			if err != nil {
				return a.renderErrorWithPath("auth.login", runtimeCfg.Path, err)
			}
			if polled.APIKey == "" {
				return a.renderError("auth.login", errors.New("CLI link completed without an API key"))
			}

			savedCfg, err := config.Update(runtimeCfg.Path, func(current config.FileConfig) config.FileConfig {
				current.ServerURL = runtimeCfg.ServerURL
				current.APIKey = polled.APIKey
				if current.LibraryRoot == "" {
					current.LibraryRoot = runtimeCfg.LibraryRoot
				}
				return current
			})
			if err != nil {
				return a.renderErrorWithPath("auth.login", runtimeCfg.Path, err)
			}

			return a.renderSuccess("auth.login", commandResult{
				Data: map[string]any{
					"config_path":  runtimeCfg.Path,
					"server_url":   savedCfg.ServerURL,
					"api_key_set":  savedCfg.APIKey != "",
					"key_prefix":   polled.KeyPrefix,
					"library_root": savedCfg.LibraryRoot,
				},
			})
		},
	}

	loginCmd.Flags().StringVar(&args.DeviceName, "device-name", "", "Optional display name for this CLI device")
	loginCmd.Flags().DurationVar(&args.Wait.Interval, "poll-interval", 2*time.Second, "Polling interval while waiting for approval")
	loginCmd.Flags().DurationVar(&args.Wait.Timeout, "poll-timeout", 2*time.Minute, "Maximum time to wait for approval")

	authCmd.AddCommand(loginCmd)
	return authCmd
}

func waitForCLILink(
	ctx context.Context,
	client *runtime.Client,
	sessionID string,
	pollToken string,
	interval time.Duration,
	timeout time.Duration,
) (*runtime.CLILinkPollResponse, error) {
	deadline := time.Now().Add(timeout)
	for {
		polled, err := client.PollCLILink(ctx, sessionID, pollToken)
		if err != nil {
			return nil, err
		}
		switch polled.Status {
		case "approved":
			if polled.APIKey != "" {
				return polled, nil
			}
		case "claimed":
			return nil, errors.New("CLI link session was already claimed")
		case "expired":
			return nil, errors.New("CLI link session expired")
		}
		if time.Now().After(deadline) {
			return nil, errors.New("timed out waiting for CLI approval")
		}
		timer := time.NewTimer(interval)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil, ctx.Err()
		case <-timer.C:
		}
	}
}

