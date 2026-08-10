package main

import (
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/cli"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
)

func main() {
	cfg, err := config.Load("ctx.yaml")
	if err != nil {
		os.Stderr.WriteString("config: " + err.Error() + "\n")
		os.Exit(1)
	}
	runner := &cli.Runner{Out: os.Stdout, Err: os.Stderr, Config: cfg}
	if err := runner.RunWithConfig(os.Args[1:]); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			os.Exit(0)
		}
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
