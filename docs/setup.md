## Installation steps
uv/uvx needs to be installed:
run the following command depending on your OS
**Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows**
```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Claude Code (CLI)**
```bash
claude mcp add [--scope user] cascade-cms -e CASCADE_API_KEY=<API_key> -e CASCADE_URL=<cascade-url> -- uvx --no-cache cascade-cms-rest-mcp
```
`--scope user` is optional and can be omitted. It determines whether it's installed at user scope (accessible across all projects) vs. project scope.

## Updating credentials
1. Open `~/.claude.json`
2. > project scope:
   > ```json
   > {
   > ....,
   > "projects": {
   >       "/your/project/path": {
   >       "allowedTools": [],
   >       "mcpContextUris": [],
   >       "mcpServers": {
   >           "cascade-cms": {
   >               "type": "stdio",
   >               "command": "uvx",
   >               "args": [
   >                   "--no-cache",
   >                   "cascade-cms-rest-mcp"
   >               ],
   >               "env": {
   >                     "CASCADE_API_KEY": "xxxxxx-xxx-xxxx-xxxx-xxxxxxxxxxx",
   >                     "CASCADE_URL": "https://example.server:8080"
   >               }
   >           }
   >       },
   >       "enabledMcpjsonServers": [],
   >       "disabledMcpjsonServers": [],
   >       "hasTrustDialogAccepted": false,
   >       "hasClaudeMdExternalIncludesApproved": false,
   >       "hasClaudeMdExternalIncludesWarningShown": false,
   >       "hasUnseenTeamArtifacts": false
   >       }, ....
   > }
   > ```
   > user scope:
   > ```json
   > {
   >     ....,
   >     "mcpServers": {
   >           "cascade-cms": {
   >               "type": "stdio",
   >               "command": "uvx",
   >               "args": [
   >                   "--no-cache",
   >                   "cascade-cms-rest-mcp"
   >               ],
   >               "env": {
   >                     "CASCADE_API_KEY": "xxxxxx-xxx-xxxx-xxxx-xxxxxxxxxxx",
   >                     "CASCADE_URL": "https://example.server:8080"
   >               }
   >           }
   >       },....
   > }
   > ```
3. Save the file then close
4. Close & re-open any open sessions
5. Run `/mcp` and select the cascade-cms
6. Select the reconnect option
7. Ready to use the MCP!
