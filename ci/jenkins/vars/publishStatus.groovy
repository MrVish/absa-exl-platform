// publishStatus(context, state) — POST a commit status to GitHub.
//
// Wrapper around the GitHub Branch Source plugin's `publishChecks` step so
// branch protection's "required status checks" list can name our jobs by
// stable context strings (e.g. `ci/python-validate`, `ci/pipeline-factory/sign`).
//
// Usage:
//
//   publishStatus('ci/python-validate', 'IN_PROGRESS')
//   try {
//       runTheJob()
//       publishStatus('ci/python-validate', 'SUCCESS', description: 'all checks passed')
//   } catch (e) {
//       publishStatus('ci/python-validate', 'FAILURE', description: e.message)
//       throw e
//   }
//
// States accepted: IN_PROGRESS, SUCCESS, FAILURE, NEUTRAL, CANCELLED, SKIPPED,
// TIMED_OUT, ACTION_REQUIRED. Conclusion (SUCCESS/FAILURE/etc) maps to the
// `state` parameter of GitHub's classic Commit Statuses API; IN_PROGRESS maps
// to "pending".

def call(String context, String state, Map opts = [:]) {
    final desc      = opts.description ?: "Jenkins build ${env.BUILD_NUMBER ?: '?'}"
    final targetUrl = opts.targetUrl  ?: env.BUILD_URL

    publishChecks(
        name:        context,
        status:      state == 'IN_PROGRESS' ? 'IN_PROGRESS' : 'COMPLETED',
        conclusion:  state == 'IN_PROGRESS' ? null : state,
        summary:     desc,
        detailsURL:  targetUrl,
    )
}
