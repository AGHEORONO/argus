#!/usr/bin/env bash
set -e

CLAUDE_SKILLS="$HOME/.claude/skills"
AGENTS_SKILLS="$HOME/.agents/skills"
AGENTS_RULES="$HOME/.agents/rules"
TMP_DIR="/tmp/agent-skills-temp"

mkdir -p "$CLAUDE_SKILLS" "$AGENTS_SKILLS" "$AGENTS_RULES" "$TMP_DIR"

# 1. AI Second Brain
SB_REPO="https://github.com/charlie947/ai-second-brain"
for target in "$CLAUDE_SKILLS" "$AGENTS_SKILLS"; do
    dest="$target/ai-second-brain"
    [ ! -d "$dest" ] && git clone "$SB_REPO" "$dest" || (git -C "$dest" pull || true)
done

# 2. Post-Karpathy Agentic Engineering
PK_REPO="https://github.com/ramsani/Post-Karpathy-Agentic-Engineering"
for target in "$CLAUDE_SKILLS" "$AGENTS_SKILLS"; do
    dest="$target/post-karpathy"
    [ ! -d "$dest" ] && git clone "$PK_REPO" "$dest" || (git -C "$dest" pull || true)
done

# 3. Ponytail
PT_REPO="https://github.com/dietrichgebert/ponytail"
PT_TEMP="$TMP_DIR/ponytail"
[ ! -d "$PT_TEMP" ] && git clone "$PT_REPO" "$PT_TEMP" || (git -C "$PT_TEMP" pull || true)

cp -R "$PT_TEMP"/skills/* "$AGENTS_SKILLS/"
cp -R "$PT_TEMP"/skills/* "$CLAUDE_SKILLS/"
[ -f "$PT_TEMP/.agents/rules/ponytail.md" ] && cp "$PT_TEMP/.agents/rules/ponytail.md" "$AGENTS_RULES/"

echo "All skills (ai-second-brain, post-karpathy, ponytail) installed and updated successfully!"
