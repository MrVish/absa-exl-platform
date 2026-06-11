package com.absa.ci

/**
 * BuildContext — fields commonly threaded through the absa-ci shared library.
 *
 * Populated by Jenkinsfiles in the agent block; passed to library steps that
 * need to know identifiers without re-reading env vars.
 *
 * Usage:
 *
 *   import com.absa.ci.BuildContext
 *
 *   def ctx = new BuildContext(
 *       jobName:    env.JOB_NAME,
 *       buildId:    env.BUILD_NUMBER,
 *       branch:     env.BRANCH_NAME,
 *       prNumber:   env.CHANGE_ID,
 *       gitSha:     env.GIT_COMMIT,
 *       statusContext: 'ci/python-validate',
 *   )
 */
class BuildContext implements Serializable {
    String jobName
    String buildId
    String branch
    String prNumber
    String gitSha
    String statusContext

    boolean isPullRequest() { prNumber != null }
    boolean isMain()        { branch == 'main' }
}
