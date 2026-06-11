// terraform-validate.Jenkinsfile
//
// Port of .github/workflows/terraform-validate.yml.
//
// Seven jobs in the original — preserved as seven stages here with two
// parallel matrix expansions:
//   1. fmt           — terraform fmt -check -recursive (gate)
//   2. validate-modules  — matrix of 6 modules, parallel
//   3. validate-stacks   — matrix of 14 stacks, parallel
//   4. tflint        — recursive tflint with --init
//   5. tfsec         — soft-fail, minimum-severity MEDIUM
//   6. checkov       — soft-fail across all severities
//   7. gitleaks      — secret scan with fetch-depth=0 (full history)
//
// No AWS at runtime — `terraform test` is plan-only and uses dummy
// AWS_ACCESS_KEY_ID/SECRET to satisfy the provider's pre-init credential
// check (same as GHA). Reports a single commit status
// `ci/terraform-validate` covering the entire pipeline; individual
// stage names appear in Jenkins' blue-ocean view for debugging.

@Library('absa-ci@main') _

def TF_MODULES = [
    'landing-zone',
    's3-replication-source',
    's3-replication-destination',
    'kms-hierarchy',
    'iam-federation',
    'pipeline-registry',
]

def TF_STACKS = [
    'terraform/envs/dev/source',
    'terraform/envs/dev/destination',
    'terraform/envs/stg/source',
    'terraform/envs/stg/destination',
    'terraform/envs/prod/source',
    'terraform/envs/prod/destination',
    'terraform/envs/dev/registry',
    'terraform/envs/stg/registry',
    'terraform/envs/prod/registry',
    'terraform/envs/prod/signing',
    'terraform/account-bootstrap/exl-dev',
    'terraform/account-bootstrap/exl-stg',
    'terraform/account-bootstrap/exl-prod',
    'pipelines/credit-risk-pd/1.0.0/terraform',
]

pipeline {
    agent {
        label 'linux-docker'
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }

    environment {
        TERRAFORM_VERSION = '1.9.5'
        TFLINT_VERSION    = 'v0.51.0'
    }

    stages {
        stage('Setup') {
            steps {
                publishStatus('ci/terraform-validate', 'IN_PROGRESS')
                checkout scm
                // Install terraform + tflint into a workspace-local bin dir
                // so we don't depend on system-managed package versions.
                sh '''
                    set -euo pipefail
                    mkdir -p .bin
                    if [ ! -x .bin/terraform ] || [ "$(.bin/terraform version -json | python3 -c 'import sys,json; print(json.load(sys.stdin)["terraform_version"])')" != "$TERRAFORM_VERSION" ]; then
                        curl -fsSL -o /tmp/terraform.zip \
                          "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip"
                        unzip -o /tmp/terraform.zip -d .bin/
                    fi
                    if [ ! -x .bin/tflint ]; then
                        curl -fsSL https://raw.githubusercontent.com/terraform-linters/tflint/master/install_linux.sh | \
                          TFLINT_INSTALL_PATH="$(pwd)/.bin" bash
                    fi
                    echo "${WORKSPACE}/.bin" > .path
                '''
            }
        }

        stage('fmt') {
            steps {
                sh '''
                    set -euo pipefail
                    export PATH="${WORKSPACE}/.bin:$PATH"
                    terraform fmt -check -recursive
                '''
            }
        }

        stage('validate (modules)') {
            steps {
                script {
                    def jobs = [:]
                    TF_MODULES.each { mod ->
                        jobs["module:${mod}"] = {
                            dir("terraform/modules/${mod}") {
                                withEnv([
                                    "PATH+TF=${env.WORKSPACE}/.bin",
                                    'AWS_REGION=af-south-1',
                                    'AWS_ACCESS_KEY_ID=testing',
                                    'AWS_SECRET_ACCESS_KEY=testing',
                                ]) {
                                    sh '''
                                        set -euo pipefail
                                        terraform init -backend=false
                                        terraform validate
                                        terraform test
                                    '''
                                }
                            }
                        }
                    }
                    parallel(jobs)
                }
            }
        }

        stage('validate (env + bootstrap stacks)') {
            steps {
                script {
                    def jobs = [:]
                    TF_STACKS.each { st ->
                        jobs["stack:${st}"] = {
                            dir(st) {
                                withEnv(["PATH+TF=${env.WORKSPACE}/.bin"]) {
                                    sh '''
                                        set -euo pipefail
                                        terraform init -backend=false
                                        terraform validate
                                    '''
                                }
                            }
                        }
                    }
                    parallel(jobs)
                }
            }
        }

        stage('lint + scan (parallel)') {
            steps {
                script {
                    parallel(
                        tflint: {
                            withEnv(["PATH+TF=${env.WORKSPACE}/.bin"]) {
                                withCredentials([usernamePassword(
                                    credentialsId: 'github-bot-token',
                                    usernameVariable: 'GH_USER',
                                    passwordVariable: 'GITHUB_TOKEN',
                                )]) {
                                    sh '''
                                        set -euo pipefail
                                        tflint --init
                                        tflint --recursive --config="${WORKSPACE}/.tflint.hcl"
                                    '''
                                }
                            }
                        },
                        tfsec: {
                            // Soft-fail mirrors GHA: findings still surface in
                            // the build log but the stage doesn't fail.
                            // Documented Allow-* patterns + interim AES256 are
                            // tolerated until kms-hierarchy lands SSE-KMS.
                            sh '''
                                set +e
                                docker run --rm -v "${WORKSPACE}:/src" aquasec/tfsec:latest \
                                  /src --minimum-severity MEDIUM
                                echo "[tfsec] soft-fail — exit code ignored on purpose."
                                exit 0
                            '''
                        },
                        checkov: {
                            // Soft-fail across all severities — same rationale
                            // as tfsec.
                            sh '''
                                set +e
                                docker run --rm -v "${WORKSPACE}:/src" bridgecrew/checkov:latest \
                                  -d /src/terraform --framework terraform
                                echo "[checkov] soft-fail — exit code ignored on purpose."
                                exit 0
                            '''
                        },
                        gitleaks: {
                            sh '''
                                set -euo pipefail
                                # fetch full history for secret scan
                                git fetch --unshallow 2>/dev/null || true
                                docker run --rm -v "${WORKSPACE}:/path" zricethezav/gitleaks:latest \
                                  detect --source=/path --redact
                            '''
                        },
                    )
                }
            }
        }
    }

    post {
        success { publishStatus('ci/terraform-validate', 'SUCCESS') }
        failure { publishStatus('ci/terraform-validate', 'FAILURE') }
        unstable { publishStatus('ci/terraform-validate', 'FAILURE', description: 'unstable') }
        aborted { publishStatus('ci/terraform-validate', 'CANCELLED') }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true, patterns: [
                [pattern: '.bin/**', type: 'EXCLUDE'],
            ])
        }
    }
}
