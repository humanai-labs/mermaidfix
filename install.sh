#!/usr/bin/env bash
# mermaidfix 安装: symlink CLI 到 ~/.local/bin + 生成 config + zsh noglob 别名
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$DIR/mermaid" "$DIR/serve.py"
mkdir -p "$HOME/.local/bin"
ln -sf "$DIR/mermaid" "$HOME/.local/bin/mermaid"
echo "✓ 已安装: ~/.local/bin/mermaid -> $DIR/mermaid"

if [ ! -f "$DIR/config.json" ]; then
  cp "$DIR/config.example.json" "$DIR/config.json"
  echo "✓ 已生成 $DIR/config.json —— 请编辑它,填入你的 API key(任何 OpenAI 兼容端点均可)"
fi

# zsh: 防括号被 glob 解析(`mermaid 画一个(xx)流程` 不炸)
if [ "$(basename "${SHELL:-}")" = "zsh" ] && [ -f "$HOME/.zshrc" ]; then
  if ! grep -q "alias mermaid='noglob mermaid'" "$HOME/.zshrc"; then
    printf "\n# mermaidfix: 禁用 glob 解析,让括号不被 zsh 吃掉\nalias mermaid='noglob mermaid'\n" >> "$HOME/.zshrc"
    echo "✓ 已在 ~/.zshrc 加 noglob 别名(新终端生效)"
  fi
fi

case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) echo "⚠ ~/.local/bin 不在 PATH 里,请加入后重开终端" ;;
esac
echo "完成。试试: mermaid -h"
