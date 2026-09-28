# GitHub Release Publication Report: Prompt Compiler v0.1.0

## Repository Details

- **Repository**: [https://github.com/bhavyaku11/Prompt-Compiler](https://github.com/bhavyaku11/Prompt-Compiler)
- **Tag**: `v0.1.0`
- **Release Title**: `Prompt Compiler v0.1.0`
- **Release URL**: [https://github.com/bhavyaku11/Prompt-Compiler/releases/tag/v0.1.0](https://github.com/bhavyaku11/Prompt-Compiler/releases/tag/v0.1.0)
- **Direct Download URL**: [https://github.com/bhavyaku11/Prompt-Compiler/releases/download/v0.1.0/Prompt.Compiler_0.1.0_aarch64.dmg](https://github.com/bhavyaku11/Prompt-Compiler/releases/download/v0.1.0/Prompt.Compiler_0.1.0_aarch64.dmg)
- **Visibility**: Public
- **Publication Timestamp**: 2026-09-28T06:07:58Z

---

## Release Asset Verification

| Parameter | Local File | Published Asset | Match Status |
| :--- | :--- | :--- | :---: |
| **Filename** | `Prompt Compiler_0.1.0_aarch64.dmg` | `Prompt.Compiler_0.1.0_aarch64.dmg` | **PASS** |
| **File Size** | 36,857,765 bytes (~35.15 MiB) | 36,857,765 bytes (~35.15 MiB) | **PASS** (Exact byte match) |
| **SHA-256 Checksum** | `5c94af29503c5a6416ce2715cf864ae89f8aecfde5bad82b3b06a479a636eb8f` | `5c94af29503c5a6416ce2715cf864ae89f8aecfde5bad82b3b06a479a636eb8f` | **PASS** (Cryptographic match) |
| **Target Architecture** | Apple Silicon (`arm64`) | Apple Silicon (`arm64`) | **PASS** |
| **DMG Internal Content** | `Prompt Compiler.app` + `Applications` symlink | `Prompt Compiler.app` + `Applications` symlink | **PASS** |

---

## GitHub CLI Verification

The release was created and published using GitHub CLI (`gh version 2.100.0`):
```bash
gh release create v0.1.0 \
  "src-tauri/target/release/bundle/dmg/Prompt Compiler_0.1.0_aarch64.dmg" \
  --repo bhavyaku11/Prompt-Compiler \
  --title "Prompt Compiler v0.1.0" \
  --notes-file /tmp/release_notes_v0.1.0.md
```

Verification query via `gh release view v0.1.0 --json ...`:
- **TagName**: `v0.1.0`
- **Name**: `Prompt Compiler v0.1.0`
- **Assets Count**: 1 (`Prompt.Compiler_0.1.0_aarch64.dmg`)
- **IsPrerelease**: `false`

---

## Download & Checksum Verification

1. **HTTP Status & Redirection**:
   - `curl -s -L -o /dev/null -w "%{http_code}" https://github.com/bhavyaku11/Prompt-Compiler/releases/download/v0.1.0/Prompt.Compiler_0.1.0_aarch64.dmg` -> returned `200 OK`.
   - Verified `Content-Disposition: attachment; filename=Prompt.Compiler_0.1.0_aarch64.dmg` header from GitHub asset storage CDN (`release-assets.githubusercontent.com`).

2. **Download & Checksum Validation**:
   - Downloaded published binary asset from GitHub release endpoint to temporary location.
   - Executed SHA-256 digest calculation:
     ```text
     5c94af29503c5a6416ce2715cf864ae89f8aecfde5bad82b3b06a479a636eb8f  /tmp/verify_dmg/downloaded_v010.dmg
     5c94af29503c5a6416ce2715cf864ae89f8aecfde5bad82b3b06a479a636eb8f  src-tauri/target/release/bundle/dmg/Prompt Compiler_0.1.0_aarch64.dmg
     ```
   - **Result**: 100% identical bit-for-bit cryptographic match.

---

## Release Notes Summary

The published release notes on GitHub include:
- Concise product vision and problem definition.
- Direct download button and package specification table.
- Core capabilities (Requirement Extraction, Project Memory, Candidate Confirmation, Local Vector RAG, Interview Mode, Agent Presets).
- System requirements: macOS Sonoma 14+ / Sequoia 15+ on Apple Silicon (`arm64`), local Ollama (`qwen3:0.6b` default).
- First-launch Gatekeeper instructions documenting the safe, app-specific right-click "Open" procedure without disabling global Gatekeeper.
- Transparent known limitations and links to source code and documentation.

---

## README Updates

`README.md` was updated to reflect the official `v0.1.0` release:
- Prominent 1-click Download button in the centered hero header pointing directly to `https://github.com/bhavyaku11/Prompt-Compiler/releases/download/v0.1.0/Prompt.Compiler_0.1.0_aarch64.dmg`.
- Updated release badge pointing to `https://github.com/bhavyaku11/Prompt-Compiler/releases/tag/v0.1.0`.
- Dedicated `## Download` section table with direct link, file size (35.15 MiB), and architecture specification.
- Updated project roadmap status from `v0.1.0-rc1` to official `v0.1.0`.

---

## Known Limitations

1. **Ad-hoc Signing (`PC-005`)**: Binaries are ad-hoc signed (`Signature=adhoc`) without an Apple Developer ID certificate. Initial launch requires user confirmation via right-click "Open" or System Settings > Privacy & Security.
2. **Platform Support**: Native Apple Silicon (`arm64`) target only.
3. **Local Ollama Dependency**: Ollama is an external local service and must be running on the host machine (`qwen3:0.6b`).

---

## Final Status

**CONFIRMED**: Prompt Compiler v0.1.0 is successfully published on GitHub Releases with verified direct download links, matching SHA-256 cryptographic checksums, and complete documentation.
