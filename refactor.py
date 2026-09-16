import re

files = [
    'etl/src/extractors/devto.py', 
    'etl/src/extractors/github.py', 
    'etl/src/extractors/gnews.py', 
    'etl/src/extractors/google_trends.py', 
    'etl/src/extractors/reddit.py', 
    'etl/src/extractors/stackoverflow.py',
    'etl/src/extractors/arxiv.py'
]

agents = [
    '\"Codex\"', '\"GitHub Copilot\"', '\"Cursor\"', '\"Windsurf\"', 
    '\"Devin\"', '\"OpenCode\"', '\"Aider\"', '\"Claude Code\"', 
    '\"Cline\"', '\"Antigravity\"'
]
agent_str = ', '.join(agents)

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    content = re.sub(r'AGENT_TERMS\s*=\s*\[.*?\]', f'AGENT_TERMS = [{agent_str}]', content, flags=re.DOTALL)
    content = re.sub(r'AGENT_QUERIES\s*=\s*\[.*?\]', f'AGENT_QUERIES = [{agent_str}]', content, flags=re.DOTALL)
    content = re.sub(r'AGENTS\s*=\s*\[.*?\]', f'AGENTS = [{agent_str}]', content, flags=re.DOTALL)
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
print('Updated python extractors')
