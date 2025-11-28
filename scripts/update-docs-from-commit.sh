#!/bin/bash
# Script to update CLAUDE.md and docs/architecture.md based on recent commits
# Usage: ./scripts/update-docs-from-commit.sh [commit-range]
# Examples:
#   ./scripts/update-docs-from-commit.sh          # Last commit
#   ./scripts/update-docs-from-commit.sh HEAD~3   # Last 3 commits
#   ./scripts/update-docs-from-commit.sh abc123   # Specific commit

set -e

COMMIT_RANGE="${1:-HEAD~1..HEAD}"
REPO_ROOT=$(git rev-parse --show-toplevel)

cd "$REPO_ROOT"

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo "❌ Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
    exit 1
fi

echo "📊 Analyzing changes in: $COMMIT_RANGE"

# Get the diff
DIFF=$(git diff "$COMMIT_RANGE" -- . ':!CLAUDE.md' ':!docs/architecture.md' ':!*.lock' ':!*.css' ':!*.map' 2>/dev/null || git show --stat HEAD)

# Get changed files
CHANGED_FILES=$(git diff --name-only "$COMMIT_RANGE" 2>/dev/null || git diff-tree --no-commit-id --name-only -r HEAD)

# Get commit messages for context
COMMIT_MESSAGES=$(git log --oneline "$COMMIT_RANGE" 2>/dev/null || git log -1 --oneline)

if [ -z "$DIFF" ]; then
    echo "No changes found in range: $COMMIT_RANGE"
    exit 0
fi

echo "📁 Changed files:"
echo "$CHANGED_FILES" | head -20
echo ""

# Read current docs
CLAUDE_MD=""
ARCH_MD=""
if [ -f "CLAUDE.md" ]; then
    CLAUDE_MD=$(cat CLAUDE.md)
fi
if [ -f "docs/architecture.md" ]; then
    ARCH_MD=$(cat docs/architecture.md)
fi

# Create the prompt
PROMPT=$(cat << 'EOF'
You are a documentation maintainer. Analyze the code changes and update the project documentation.

## Task
Review the diff and update CLAUDE.md and/or docs/architecture.md if the changes warrant documentation updates.

## What to update:
- New modules, files, or directories → Update project structure sections
- New API endpoints → Update API documentation
- New database models/tables → Update schema documentation
- New dependencies → Update dependencies section
- New services or architectural patterns → Update architecture docs
- Significant new features → Update relevant sections

## What NOT to update:
- Bug fixes (unless they reveal undocumented behavior)
- Refactoring that doesn't change structure
- Test files (unless they document new patterns)
- Minor changes

## Output format:
If CLAUDE.md needs updates, output:
```claude.md
[the specific section to add or modify, with enough context to locate it]
```

If docs/architecture.md needs updates, output:
```architecture.md
[the specific section to add or modify]
```

If no updates needed, output: NO_UPDATES_NEEDED

## Current Documentation

### CLAUDE.md (excerpt - first 500 lines):
EOF
)

PROMPT="$PROMPT

\`\`\`
$(echo "$CLAUDE_MD" | head -500)
\`\`\`

### docs/architecture.md (excerpt - first 300 lines):
\`\`\`
$(echo "$ARCH_MD" | head -300)
\`\`\`

## Recent Commits:
$COMMIT_MESSAGES

## Changed Files:
$CHANGED_FILES

## Diff:
\`\`\`diff
$(echo "$DIFF" | head -1000)
\`\`\`
"

echo "🤖 Asking Claude to analyze changes..."
echo ""

# Run Claude
claude -p "$PROMPT" --no-input

echo ""
echo "---"
echo "💡 Review the suggestions above and apply manually, or run:"
echo "   claude \"Update CLAUDE.md based on the suggestions above\""
