# craft.kaleb.one

Operating procedures & craft knowledge base for the kaleb.one ecosystem.

Reads from `second-brain-vault/domains/ai-tooling/craft/` and generates a Liquid Glass knowledge base with expandable article cards.

## Architecture

- **Source**: `triursa/second-brain-vault` → `domains/ai-tooling/craft/`
- **Build**: Python SSG (`scripts/build.py`) parses vault markdown, generates static HTML
- **Deploy**: Cloudflare Pages → `craft.kaleb.one` (Zero Trust Access)

## Local Build

```bash
VAULT_DIR=/path/to/vault/domains/ai-tooling OUTPUT_DIR=/tmp/craft-site python3 scripts/build.py
```

## CI/CD

Vault push to `domains/ai-tooling/craft/**` triggers automatic rebuild via `repository_dispatch`.