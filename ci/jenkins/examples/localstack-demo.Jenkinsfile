// localstack-demo.Jenkinsfile
//
// Port of .github/workflows/localstack-demo.yml.
//
// Runs the end-to-end producer + verifier chain against a LocalStack CE
// container on the build agent. Demo CLI exits with:
//   0 — chain verified end-to-end (GATE PASS)
//   1 — platform regression (GATE FAIL — blocks merge)
//   2 — infrastructure failure on the agent (warning, doesn't block)
//   3 — teardown leak (warning, doesn't block)
//
// To preserve those semantics in Jenkins we keep the demo step from
// failing the build directly and let an explicit "Gate" stage decide.
// Otherwise Jenkins would aggregate any non-zero exit into FAILURE and
// we'd lose the distinction between platform-regression and infra-flake.
//
// Reports a single commit status `ci/localstack-demo`.
//
// Agent requirements:
//   - Docker available on the agent
//   - terraform binary (or we install it like terraform-validate does)
//   - Network egress to docker.io for the localstack image

@Library('absa-ci@main') _

pipeline {
    agent {
        label 'linux-docker'
    }

    options {
        timeout(time: 12, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '30'))
        // Mirror GHA `concurrency: localstack-demo-${{ github.ref }} cancel-in-progress`.
        // One run per branch — newer PR push cancels the in-flight build.
        disableConcurrentBuilds(abortPrevious: true)
    }

    environment {
        UV_VERSION        = '0.5.11'
        UV_CACHE_DIR      = "${WORKSPACE}/.uv-cache"
        TERRAFORM_VERSION = '1.9.5'
        PYTHONPATH        = 'scripts'
        LOCALSTACK_IMAGE  = 'localstack/localstack:3.8.1'
    }

    stages {
        stage('Path filter') {
            when {
                anyOf {
                    changeset 'code-intake/**'
                    changeset 'pipeline-factory/**'
                    changeset 'manifest-signer/**'
                    changeset 'registry/api/**'
                    changeset 'terraform/modules/pipeline-registry/**'
                    changeset 'terraform/modules/signing-foundation/**'
                    changeset 'platform-contracts/**'
                    changeset 'packages/credit-risk-pd/**'
                    changeset 'pipelines/credit-risk-pd/**'
                    changeset 'pipeline-factory/configs/credit-risk-pd/**'
                    changeset 'scripts/demo/**'
                    changeset 'infra/localstack/**'
                    changeset 'ci/jenkins/examples/localstack-demo.Jenkinsfile'
                    changeset 'pyproject.toml'
                    changeset 'uv.lock'
                    branch 'main'
                }
            }
            steps {
                echo 'Triggered by changes that touch the producer/verifier chain.'
            }
        }

        stage('Setup') {
            steps {
                publishStatus('ci/localstack-demo', 'IN_PROGRESS')
                checkout scm
                setupUv(uvVersion: env.UV_VERSION, frozen: true)

                sh '''
                    set -euo pipefail
                    mkdir -p .bin
                    if [ ! -x .bin/terraform ]; then
                        curl -fsSL -o /tmp/terraform.zip \
                          "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
                        unzip -o /tmp/terraform.zip -d .bin/
                    fi
                '''

                sh '''
                    set -euo pipefail
                    docker pull "${LOCALSTACK_IMAGE}"
                '''
            }
        }

        stage('Run demo') {
            steps {
                script {
                    env.DEMO_EXIT_CODE = sh(
                        returnStdout: true,
                        script: '''
                            set +e
                            export PATH="${WORKSPACE}/.bin:$PATH"
                            uv sync --frozen --all-extras
                            uv run python -m demo run \
                              --no-color --no-cleanup \
                              --transcript demo-transcript.md
                            ec=$?
                            echo "$ec"
                        ''',
                    ).trim().readLines().last()
                    echo "demo exit code = ${env.DEMO_EXIT_CODE}"
                }
            }
        }

        stage('Archive transcript') {
            when { expression { env.DEMO_EXIT_CODE == '0' } }
            steps {
                archiveArtifacts artifacts: 'demo-transcript.md',
                                 allowEmptyArchive: false,
                                 fingerprint: true
            }
        }

        stage('Archive failure bundle') {
            when { expression { env.DEMO_EXIT_CODE != '0' } }
            steps {
                archiveArtifacts artifacts: '''
                    demo-transcript.md,
                    infra/localstack/terraform/terraform.tfstate,
                    infra/localstack/.uvicorn.log
                '''.replaceAll('\\s+', ''),
                                 allowEmptyArchive: true
            }
        }

        stage('Gate on demo exit code') {
            steps {
                script {
                    switch (env.DEMO_EXIT_CODE) {
                        case '0':
                            echo 'Demo passed (chain verified end-to-end).'
                            break
                        case '1':
                            error('Chain verification failed (platform regression). See archived demo-failure-bundle.')
                            break
                        case '2':
                            unstable('Demo infrastructure failure (not a platform regression); not blocking merge.')
                            break
                        case '3':
                            unstable('Demo teardown failed (CI runner discarded); not blocking merge.')
                            break
                        default:
                            error("Demo failed with unexpected exit code ${env.DEMO_EXIT_CODE}.")
                    }
                }
            }
        }
    }

    post {
        always {
            // Always tear down LocalStack and the uvicorn sidecar so a
            // re-build on the same agent doesn't see leftover state.
            sh '''
                docker compose -f infra/localstack/docker-compose.yml down -v || true
                rm -f infra/localstack/.uvicorn.pid infra/localstack/.uvicorn.log
            '''
        }
        success { publishStatus('ci/localstack-demo', 'SUCCESS', description: 'chain verified') }
        failure { publishStatus('ci/localstack-demo', 'FAILURE', description: 'platform regression') }
        unstable { publishStatus('ci/localstack-demo', 'NEUTRAL', description: 'infra flake — not blocking') }
        aborted { publishStatus('ci/localstack-demo', 'CANCELLED') }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true, patterns: [
                [pattern: '.uv-cache/**', type: 'EXCLUDE'],
                [pattern: '.bin/**',      type: 'EXCLUDE'],
            ])
        }
    }
}
