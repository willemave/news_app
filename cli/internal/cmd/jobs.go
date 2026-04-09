package cmd

import (
	"context"

	"github.com/spf13/cobra"

	"github.com/willem/news_app/cli/internal/runtime"
)

func (a *App) newJobsCommand() *cobra.Command {
	jobsCmd := &cobra.Command{
		Use:   "jobs",
		Short: "Inspect async jobs",
	}

	getCmd := &cobra.Command{
		Use:   "get <job-id>",
		Short: "Fetch one async job",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			jobID, err := a.parseIntArg("jobs.get", args[0])
			if err != nil {
				return err
			}
			return a.runRemote(cmd, "jobs.get", func(ctx context.Context, client *runtime.Client) (commandResult, error) {
				job, err := client.GetJob(ctx, jobID)
				if err != nil {
					return commandResult{}, err
				}
				return commandResult{Data: job}, nil
			})
		},
	}

	var wait waitFlags
	waitCmd := &cobra.Command{
		Use:   "wait <job-id>",
		Short: "Poll a job until it reaches a terminal state",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			jobID, err := a.parseIntArg("jobs.wait", args[0])
			if err != nil {
				return err
			}
			options, err := waitOptions(wait)
			if err != nil {
				return a.renderError("jobs.wait", err)
			}
			return a.runRemote(cmd, "jobs.wait", func(ctx context.Context, client *runtime.Client) (commandResult, error) {
				job, err := client.WaitForJob(ctx, jobID, options)
				if err != nil {
					return commandResult{}, err
				}
				return commandResult{Data: job}, nil
			})
		},
	}
	a.addWaitFlags(waitCmd, &wait)

	jobsCmd.AddCommand(getCmd, waitCmd)
	return jobsCmd
}
