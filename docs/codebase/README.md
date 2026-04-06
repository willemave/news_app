# Codebase Reference

Codex-generated folder-by-folder reference for the backend (`app/`), CLI (`cli/`), and iOS client (`client/`), with a small `config/` support section for shared file-backed settings.

## Layout
- `app/` documents the FastAPI backend one top-level folder at a time.
- `cli/` documents the Go command-line client one top-level folder at a time.
- `client/` documents the SwiftUI iOS app one top-level folder at a time.
- `config/` remains a support section for shared file-backed configuration.

## Generation workflow
Use `./docs/generate_codebase_docs.sh` from the repo root. It runs Codex with `gpt-5.4-mini` once per top-level folder and refreshes the corresponding overview markdown.

```bash
./docs/generate_codebase_docs.sh
```

The script also refreshes the `config/` support overview.

## Markdown shape
- What the folder owns
- Which files or subfolders matter most
- How it fits into the rest of the codebase
- Any generated artifacts, build steps, or runtime dependencies

## Concat commands
```bash
find docs/codebase/app -type f -name '*.md' | sort | xargs cat
find docs/codebase/cli -type f -name '*.md' | sort | xargs cat
find docs/codebase/client -type f -name '*.md' | sort | xargs cat
find docs/codebase/config -type f -name '*.md' | sort | xargs cat
find docs/codebase -type f -name '*.md' | sort | xargs cat
```
