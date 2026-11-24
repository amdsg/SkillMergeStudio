from __future__ import annotations

import concurrent.futures
import json
import os
import re
import ssl
import urllib.error
import urllib.request

CANDIDATES = [
    ("cursor-rules", "Cursor", "https://cursor.com/docs/context/rules"),
    ("cursor-skills", "Cursor", "https://cursor.com/docs/agent/skills"),
    ("codex-skills", "Codex", "https://developers.openai.com/codex/skills"),
    ("codex-docs", "Codex", "https://developers.openai.com/codex/"),
    ("chatgpt-skills", "ChatGPT", "https://help.openai.com/en/articles/12512176-what-are-skills"),
    ("github-copilot-skills", "GitHub Copilot", "https://docs.github.com/en/copilot/concepts/agents/about-agent-skills"),
    ("github-copilot-instructions", "GitHub Copilot", "https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions"),
    ("continue-skills", "Continue", "https://docs.continue.dev/customize/skills"),
    ("continue-rules", "Continue", "https://docs.continue.dev/customize/rules"),
    ("aider-conventions", "Aider", "https://aider.chat/docs/usage/conventions.html"),
    ("openhands-skills", "OpenHands", "https://docs.all-hands.dev/usage/agents/skills"),
    ("openhands-microagents", "OpenHands", "https://docs.all-hands.dev/usage/prompting/microagents-overview"),
    ("goose-skills", "Goose", "https://block.github.io/goose/docs/guides/context-engineering/using-skills/"),
    ("goose-recipes", "Goose", "https://block.github.io/goose/docs/guides/recipes/"),
    ("amp-skills", "Amp", "https://ampcode.com/news/skills"),
    ("amp-manual", "Amp", "https://ampcode.com/manual"),
    ("zed-skills", "Zed", "https://zed.dev/docs/ai/skills"),
    ("zed-rules", "Zed", "https://zed.dev/docs/ai/rules"),
    ("warp-skills", "Warp", "https://docs.warp.dev/agent-platform/capabilities/skills"),
    ("warp-rules", "Warp", "https://docs.warp.dev/agent-platform/capabilities/rules"),
    ("augment-skills", "Augment Code", "https://docs.augmentcode.com/context-services/skills"),
    ("factory-skills", "Factory", "https://docs.factory.ai/cli/configuration/skills"),
    ("replit-skills", "Replit", "https://docs.replit.com/replitai/agent-skills"),
    ("junie-guidelines", "JetBrains Junie", "https://www.jetbrains.com/help/junie/customize-guidelines.html"),
    ("kiro-steering", "Kiro", "https://kiro.dev/docs/steering/"),
    ("kiro-skills", "Kiro", "https://kiro.dev/docs/skills/"),
    ("amazon-q-context", "Amazon Q", "https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/context.html"),
    ("gitlab-duo", "GitLab Duo", "https://docs.gitlab.com/ee/user/gitlab_duo/"),
    ("tabnine-docs", "Tabnine", "https://docs.tabnine.com/main/getting-started/quick-start"),
    ("sourcegraph-cody", "Sourcegraph Cody", "https://sourcegraph.com/docs/cody/capabilities/context"),
    ("crush", "Charm Crush", "https://github.com/charmbracelet/crush"),
    ("plandex", "Plandex", "https://docs.plandex.ai/"),
    ("open-interpreter", "Open Interpreter", "https://docs.openinterpreter.com/"),
    ("devin-skills", "Devin", "https://docs.devin.ai/essential-guidelines/skills"),
    ("devin-desktop", "Devin Desktop", "https://docs.devin.ai/desktop/devin-local/customizations"),
    ("qwen-code-skills", "Qwen Code", "https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/"),
    ("qwen-code-docs", "Qwen Code", "https://qwenlm.github.io/qwen-code-docs/"),
    ("kimi-cli", "Kimi CLI", "https://github.com/MoonshotAI/kimi-cli"),
    ("coze-docs", "Coze", "https://www.coze.com/open/docs/guides"),
    ("dify-docs", "Dify", "https://docs.dify.ai/"),
    ("n8n-docs", "n8n", "https://docs.n8n.io/"),
    ("langchain-skills", "LangChain", "https://docs.langchain.com/oss/python/langchain/skills"),
    ("crewai-skills", "CrewAI", "https://docs.crewai.com/concepts/skills"),
    ("autogen", "AutoGen", "https://microsoft.github.io/autogen/stable/"),
    ("semantic-kernel", "Semantic Kernel", "https://learn.microsoft.com/en-us/semantic-kernel/"),
    ("copilot-studio", "Microsoft Copilot Studio", "https://learn.microsoft.com/en-us/microsoft-copilot-studio/"),
    ("manus", "Manus", "https://manus.im/"),
    ("genspark", "Genspark", "https://www.genspark.ai/"),
    ("flowise", "Flowise", "https://docs.flowiseai.com/"),
    ("langflow", "Langflow", "https://docs.langflow.org/"),
    ("agentskills-spec", "Agent Skills", "https://agentskills.io/specification"),
    ("skills-sh", "Skills.sh", "https://skills.sh/"),
    ("smithery", "Smithery", "https://smithery.ai/docs"),
    ("mcp", "MCP", "https://modelcontextprotocol.io/"),
    ("antigravity", "Antigravity", "https://antigravity.google/docs"),
    ("iflow", "iFlow", "https://iflow.cn/"),
    ("codebuddy", "CodeBuddy", "https://codebuddy.ai/docs"),
    ("doubao", "Doubao", "https://www.doubao.com/"),
    ("workbuddy", "WorkBuddy", "https://www.workbuddy.ai/"),
    ("dingtalk", "DingTalk", "https://www.dingtalk.com/"),
    ("trae-skills", "Trae", "https://docs.trae.ai/ide/skills"),
    ("qoder-rules", "Qoder", "https://docs.qoder.com/user-guide/rules"),
    ("cline-rules", "Cline", "https://docs.cline.bot/customization/cline-rules"),
    ("roo-instructions", "Roo", "https://roocodeinc.github.io/Roo-Code/features/custom-instructions/"),
    ("gemini-cli-skills", "Gemini CLI", "https://geminicli.com/docs/cli/skills/"),
    ("opencode-skills", "OpenCode", "https://opencode.ai/docs/skills/"),
    ("vscode-copilot-skills", "VS Code Copilot", "https://code.visualstudio.com/docs/agent-customization/agent-skills"),
    ("claude-skills", "Claude", "https://code.claude.com/docs/en/skills"),
    ("continue-hub", "Continue Hub", "https://hub.continue.dev/"),
    ("cursor-directory", "Cursor Directory", "https://cursor.directory/"),
    ("openai-agents-sdk", "OpenAI Agents SDK", "https://openai.github.io/openai-agents-python/"),
    ("google-adk", "Google ADK", "https://google.github.io/adk-docs/"),
    ("claude-agent-sdk", "Claude Agent SDK", "https://docs.claude.com/en/api/agent-sdk/overview"),
    ("vercel-ai-sdk", "Vercel AI SDK", "https://ai-sdk.dev/docs/introduction"),
    ("mistral-docs", "Mistral", "https://docs.mistral.ai/"),
    ("llamaindex-agents", "LlamaIndex", "https://docs.llamaindex.ai/en/stable/use_cases/agents/"),
    ("haystack-agents", "Haystack", "https://docs.haystack.deepset.ai/docs/agents"),
]

PATTERNS = {
    "skill_md": re.compile(r"SKILL\.md", re.I),
    "agent_skills": re.compile(r"agent\s+skills?", re.I),
    "skills_word": re.compile(r"\bskills?\b", re.I),
    "agents_md": re.compile(r"AGENTS\.md", re.I),
    "rules_word": re.compile(r"\brules?\b", re.I),
}


def probe(item):
    key, label, url = item
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
        },
    )
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    status = None
    final = url
    error = ""
    data = b""
    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            status = int(response.status)
            final = response.geturl()
            data = response.read(700000)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        final = exc.geturl() or url
        error = f"HTTP {exc.code}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:200]
    text = data.decode("utf-8", "replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip()[:120] if title_match else ""
    return {
        "key": key,
        "label": label,
        "url": url,
        "final_url": final,
        "status": status,
        "error": error,
        "title": title,
        "bytes_read": len(data),
        "markers": {name: bool(pattern.search(text)) for name, pattern in PATTERNS.items()},
    }


def main() -> int:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(probe, CANDIDATES))
    results.sort(key=lambda item: (0 if item["status"] == 200 else 1, item["label"].lower(), item["url"]))
    out_dir = os.path.join(".codeartsdoer", "specs", "skillmerge_studio")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "platform-discovery-2026-11-22.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"generated_at": "2026-11-22", "candidates": results}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    ok = [item for item in results if item["status"] == 200]
    print(f"TOTAL {len(results)} OK {len(ok)} FAILED {len(results) - len(ok)}")
    print("SAVED", out_path)
    print("--- 200 with SKILL.md ---")
    for item in results:
        if item["status"] == 200 and item["markers"]["skill_md"]:
            print(f"SKILL | {item['label']} | {item['final_url']} | {item['title']}")
    print("--- 200 with rules/agent-skills semantics but no SKILL.md ---")
    for item in results:
        if item["status"] == 200 and not item["markers"]["skill_md"] and (
            item["markers"]["agent_skills"] or item["markers"]["agents_md"] or item["markers"]["rules_word"]
        ):
            print(f"RULE  | {item['label']} | {item['final_url']} | {item['title']}")
    print("--- failures ---")
    for item in results:
        if item["status"] != 200:
            print(f"FAIL  | {item['label']} | {item['url']} | {item['status']} | {item['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())