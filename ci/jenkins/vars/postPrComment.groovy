// postPrComment(body) — find-or-create a PR comment.
//
// Mirrors actions/github-script behaviour in terraform-validate.yml: post a
// comment on the open PR, update if a previous comment with the same marker
// exists. The marker is an HTML comment included in the body so future calls
// can locate it idempotently.
//
// Usage:
//   postPrComment(
//       marker:  'tf-plan',
//       body:    "### Terraform plan\n```\n${planOutput}\n```",
//   )
//
// Requires:
//   - The Jenkinsfile running under a multibranch PR build (env.CHANGE_ID set)
//   - A `github-bot-token` credential (Username + PAT, or GitHub App)

def call(Map args) {
    final marker = args.marker ?: 'jenkins-comment'
    final body   = args.body   ?: error("postPrComment: 'body' is required")

    if (!env.CHANGE_ID) {
        echo "[postPrComment] not a PR build (CHANGE_ID unset) — skipping"
        return
    }
    if (!env.CHANGE_URL) {
        echo "[postPrComment] CHANGE_URL unset — skipping"
        return
    }

    // Derive owner/repo/pr-number from CHANGE_URL
    // e.g. https://github.com/MrVish/absa-exl-platform/pull/123
    final match = (env.CHANGE_URL =~ /github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/)
    if (!match) {
        echo "[postPrComment] could not parse CHANGE_URL=${env.CHANGE_URL} — skipping"
        return
    }
    final owner = match[0][1]
    final repo  = match[0][2]
    final pr    = match[0][3]

    final tag = "<!-- jenkins-marker:${marker} -->"
    final fullBody = "${tag}\n${body}"

    withCredentials([usernamePassword(
        credentialsId: 'github-bot-token',
        usernameVariable: 'GH_USER',
        passwordVariable: 'GH_TOKEN',
    )]) {
        // Look for an existing comment carrying our marker
        final existingId = sh(
            returnStdout: true,
            script: """
                set -euo pipefail
                curl -sSL \
                  -H "Authorization: Bearer \$GH_TOKEN" \
                  -H 'Accept: application/vnd.github+json' \
                  'https://api.github.com/repos/${owner}/${repo}/issues/${pr}/comments?per_page=100' \
                | python3 -c "import sys,json; c=[x for x in json.load(sys.stdin) if '${tag}' in (x.get('body') or '')]; print(c[0]['id'] if c else '')"
            """,
        ).trim()

        // Body must be JSON-escaped — round-trip through python3 for safety
        writeFile file: '.jenkins-comment.txt', text: fullBody
        final escapedBody = sh(
            returnStdout: true,
            script: "python3 -c \"import json,sys; print(json.dumps({'body': open('.jenkins-comment.txt').read()}))\"",
        ).trim()

        if (existingId) {
            sh """
                set -euo pipefail
                curl -sSL -X PATCH \
                  -H "Authorization: Bearer \$GH_TOKEN" \
                  -H 'Accept: application/vnd.github+json' \
                  -H 'Content-Type: application/json' \
                  -d '${escapedBody.replace("'", "'\\''")}' \
                  'https://api.github.com/repos/${owner}/${repo}/issues/comments/${existingId}' \
                  -o /dev/null -w '%{http_code}\\n'
            """
        } else {
            sh """
                set -euo pipefail
                curl -sSL -X POST \
                  -H "Authorization: Bearer \$GH_TOKEN" \
                  -H 'Accept: application/vnd.github+json' \
                  -H 'Content-Type: application/json' \
                  -d '${escapedBody.replace("'", "'\\''")}' \
                  'https://api.github.com/repos/${owner}/${repo}/issues/${pr}/comments' \
                  -o /dev/null -w '%{http_code}\\n'
            """
        }
    }
}
