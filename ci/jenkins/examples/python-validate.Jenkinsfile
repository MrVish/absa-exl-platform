// python-validate.Jenkinsfile
//
// Port of .github/workflows/python-validate.yml.
//
// Triggered on every PR that touches Python source or the lockfile. Runs
// ruff (lint + format), mypy, pytest, and the contract-model drift check.
// Posts a single commit status `ci/python-validate` back to GitHub.
//
// Wire-up:
//   - Place this file at the path Jenkins is configured to pick up for this
//     job (multibranch pipeline → script path `ci/jenkins/examples/python-validate.Jenkinsfile`).
//   - Branch protection on `main` requires status `ci/python-validate`.

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

    triggers {
        // Multibranch picks up PR + push automatically; this is documentation only.
        // pollSCM('H/5 * * * *')  // Use webhook in production
    }

    environment {
        UV_VERSION = '0.5.11'
        UV_CACHE_DIR = "${WORKSPACE}/.uv-cache"
    }

    stages {
        stage('Path filter') {
            // Mirrors GHA `paths:` filter — skip if no Python or lockfile changed.
            when {
                anyOf {
                    changeset 'platform-contracts/**'
                    changeset 'registry/**'
                    changeset 'pipeline-factory/**'
                    changeset 'pipelines/**'
                    changeset 'manifest-signer/**'
                    changeset 'code-intake/**'
                    changeset 'pyproject.toml'
                    changeset 'uv.lock'
                    changeset '.python-version'
                    changeset 'ci/jenkins/examples/python-validate.Jenkinsfile'
                    branch 'main'
                }
            }
            steps {
                echo "Triggered by changes in Python paths or scheduled run."
            }
        }

        stage('Setup') {
            steps {
                publishStatus('ci/python-validate', 'IN_PROGRESS', description: 'starting')
                checkout scm
                setupUv(uvVersion: env.UV_VERSION)
            }
        }

        stage('Lint') {
            steps {
                sh 'uv run ruff check .'
            }
        }

        stage('Format check') {
            steps {
                sh 'uv run ruff format --check .'
            }
        }

        stage('Types') {
            steps {
                sh '''
                    set -euo pipefail
                    uv run mypy \
                      platform-contracts/src \
                      registry/api/src \
                      pipeline-factory/src \
                      manifest-signer/src \
                      code-intake/src
                '''
            }
        }

        stage('Tests') {
            steps {
                sh 'uv run pytest -v --timeout=60 --timeout-method=thread --junitxml=junit.xml'
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'junit.xml'
                }
            }
        }

        stage('Contract model drift check') {
            steps {
                sh '''
                    set -euo pipefail
                    bash platform-contracts/regenerate-models.sh
                    git diff --exit-code platform-contracts/src/platform_contracts/models.py
                '''
            }
        }
    }

    post {
        success {
            publishStatus('ci/python-validate', 'SUCCESS', description: 'all checks passed')
        }
        failure {
            publishStatus('ci/python-validate', 'FAILURE', description: 'see Jenkins build log')
        }
        unstable {
            publishStatus('ci/python-validate', 'FAILURE', description: 'unstable — likely test failures')
        }
        aborted {
            publishStatus('ci/python-validate', 'CANCELLED')
        }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true, patterns: [
                [pattern: '.uv-cache/**', type: 'EXCLUDE'],
            ])
        }
    }
}
