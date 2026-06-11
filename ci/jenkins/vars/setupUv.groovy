// setupUv() — install `uv` and sync the workspace.
//
// Mirrors astral-sh/setup-uv@v5 + `uv sync --frozen` from GHA.
// Idempotent: a second call in the same build is a no-op.
//
// Usage:
//   setupUv()                                  // default: pin via .python-version, --frozen
//   setupUv(uvVersion: '0.5.11', frozen: false)
//
// Caches:
//   The uv cache lives at $WORKSPACE/.uv-cache. Persist this across builds
//   via Jenkins' "Workspace Cleanup" exclusion or a sidecar EBS volume on
//   the agent template.

def call(Map args = [:]) {
    final uvVersion = args.uvVersion ?: '0.5.11'
    final frozen    = args.containsKey('frozen') ? args.frozen : true
    final cacheDir  = args.cacheDir ?: "${env.WORKSPACE}/.uv-cache"

    sh """
        set -euo pipefail
        export UV_CACHE_DIR='${cacheDir}'
        if ! command -v uv >/dev/null 2>&1 || [ "\$(uv --version | awk '{print \$2}')" != '${uvVersion}' ]; then
            echo '[setupUv] installing uv ${uvVersion}'
            curl -LsSf https://astral.sh/uv/${uvVersion}/install.sh | sh
            export PATH="\$HOME/.local/bin:\$PATH"
        fi
        uv --version
        uv sync ${frozen ? '--frozen' : ''}
    """
}
