# pr-review setup notes

One-time setup for the GitHub MCP server used by this skill. Not needed at
review time — read only when GitHub access is failing.

1. Use a token from the `gh` command. A freshly minted web token does not get
   enough permissions to work with PR review comments and to read private
   repositories (https://github.com/settings/personal-access-tokens/new).

```
gh auth login
  ? What account do you want to log into? GitHub.com
  ? What is your preferred protocol for Git operations on this host? SSH
  ? Upload your SSH public key to your GitHub account? Skip
  ? How would you like to authenticate GitHub CLI? Login with a web browser
gh auth status
gh auth token
```

2. Copy the token into `~/.claude.json`:

```json
"mcpServers": {
  "github": {
    "type": "stdio",
    "command": "npx",
    "args": [
      "-y",
      "@modelcontextprotocol/server-github"
    ],
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "...<gh auth token>..."
    }
  }
}
```
