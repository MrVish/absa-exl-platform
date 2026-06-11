// code-intake.Jenkinsfile
//
// Port of .github/workflows/code-intake.yml.
//
// Validates every package under packages/ via the code-intake CLI:
//   1. Run code-intake/tests
//   2. For each package: `code-intake validate --strict` then
//      `code-intake generate-manifest`
//   3. Assert no drift in packages/ (the regeneration was a no-op for
//      manifests that should be byte-stable)
//
// No AWS — purely local validation. Reports a single commit status
// `ci/code-intake`.

@Library('absa-ci@main') _

pipeline {
    agent {
        label 'linux-docker'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    environment {
        UV_VERSION   = '0.5.11'
        UV_CACHE_DIR = "${WORKSPACE}/.uv-cache"
    }

    stages {
        stage('Path filter') {
            when {
                anyOf {
                    changeset 'code-intake/**'
                    changeset 'packages/**'
                    changeset 'platform-contracts/**'
                    changeset 'pyproject.toml'
                    changeset 'uv.lock'
                    changeset 'ci/jenkins/examples/code-intake.Jenkinsfile'
                    branch 'main'
                }
            }
            steps {
                echo 'Triggered by changes in code-intake / packages / platform-contracts.'
            }
        }

        stage('Setup') {
            steps {
                publishStatus('ci/code-intake', 'IN_PROGRESS')
                checkout scm
                setupUv(uvVersion: env.UV_VERSION)
            }
        }

        stage('code-intake tests') {
            steps {
                sh 'uv run pytest code-intake/tests -v --timeout=60 --timeout-method=thread --junitxml=junit-code-intake.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'junit-code-intake.xml'
                }
            }
        }

        stage('Validate + regenerate manifest for every package, assert byte-stability') {
            steps {
                sh '''
                    set -euo pipefail
                    for pkg in packages/*/*/; do
                        echo "[code-intake] validating $pkg"
                        uv run code-intake validate --package "$pkg" --strict
                        uv run code-intake generate-manifest --package "$pkg"
                    done
                    git diff --exit-code packages/
                '''
            }
        }
    }

    post {
        success { publishStatus('ci/code-intake', 'SUCCESS', description: 'all packages validate clean') }
        failure { publishStatus('ci/code-intake', 'FAILURE', description: 'see Jenkins build log') }
        unstable { publishStatus('ci/code-intake', 'FAILURE', description: 'unstable — likely test failures') }
        aborted { publishStatus('ci/code-intake', 'CANCELLED') }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true, patterns: [
                [pattern: '.uv-cache/**', type: 'EXCLUDE'],
            ])
        }
    }
}
