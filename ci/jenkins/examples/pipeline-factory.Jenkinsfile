// pipeline-factory.Jenkinsfile
//
// Port of .github/workflows/pipeline-factory.yml.
//
// Three stages:
//   1. validate-and-generate  (PR + push) — drift gate; regenerates every
//                              pipeline fixture, asserts byte-stability.
//   2. sign                   (push to main only) — assume signer role,
//                              kms:Sign every unsigned manifest, upload to S3.
//   3. register               (push to main only, after sign) — assume
//                              registrar role, POST to Registry API.
//
// Reports three commit status contexts to GitHub:
//   - ci/pipeline-factory/validate
//   - ci/pipeline-factory/sign
//   - ci/pipeline-factory/register
//
// AWS auth: under IRSA on EKS, awsLogin() is a no-op (pod ServiceAccount
// already holds the role). For non-IRSA agents pass `roleArn:` explicitly.

@Library('absa-ci@main') _

pipeline {
    agent {
        label 'linux-docker'
    }

    options {
        timeout(time: 45, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '60'))
    }

    environment {
        UV_VERSION   = '0.5.11'
        UV_CACHE_DIR = "${WORKSPACE}/.uv-cache"
        AWS_REGION   = 'eu-west-1'

        // Secrets — backed by AWS Secrets Manager via the credentials plugin.
        // Empty value is the explicit "not configured yet" signal mirroring the
        // GHA "Skip if not configured" no-op step.
        SIGNER_ROLE_ARN          = credentials('aws-signer-role-arn')
        KMS_KEY_ARN              = credentials('aws-kms-signing-key-arn')
        SIGNED_MANIFESTS_BUCKET  = credentials('aws-signed-manifests-bucket')
        REGISTRAR_ROLE_ARN       = credentials('aws-registrar-role-arn')
        REGISTRY_API_ENDPOINT    = credentials('registry-api-endpoint')
    }

    stages {

        // -----------------------------------------------------------------
        // STAGE 1 — Validate + drift gate (runs on PR + push)
        // -----------------------------------------------------------------
        stage('validate + generate (drift gate)') {
            when {
                anyOf {
                    changeset 'pipeline-factory/**'
                    changeset 'packages/**'
                    changeset 'pipelines/**'
                    changeset 'platform-contracts/**'
                    changeset 'manifest-signer/**'
                    changeset 'pyproject.toml'
                    changeset 'uv.lock'
                    changeset 'ci/jenkins/examples/pipeline-factory.Jenkinsfile'
                    branch 'main'
                }
            }
            steps {
                publishStatus('ci/pipeline-factory/validate', 'IN_PROGRESS')
                checkout scm
                setupUv(uvVersion: env.UV_VERSION)

                sh 'uv run pytest pipeline-factory/tests -v --timeout=60 --timeout-method=thread'

                // Regenerate every fixture and assert byte-stability — the
                // drift gate. Same as the GHA loop.
                sh '''
                    set -euo pipefail
                    for config in pipeline-factory/configs/*/*/model_config.yaml; do
                        uv run generate-pipeline generate --config "$config" --force
                    done
                    git diff --exit-code pipelines/
                '''
            }
            post {
                success { publishStatus('ci/pipeline-factory/validate', 'SUCCESS') }
                failure { publishStatus('ci/pipeline-factory/validate', 'FAILURE',
                                         description: 'drift gate or pipeline-factory tests failed') }
            }
        }

        // -----------------------------------------------------------------
        // STAGE 2 — Sign (push to main only)
        // -----------------------------------------------------------------
        stage('sign (kms:Sign + upload to S3)') {
            when {
                allOf {
                    branch 'main'
                    not { changeRequest() }
                    expression { return env.SIGNER_ROLE_ARN?.trim() }
                }
            }
            options {
                // Singleton — only one signer build at a time across the cluster,
                // matching `concurrency: pipeline-factory-sign` from GHA.
                lock(resource: 'pipeline-factory-sign', inversePrecedence: false)
            }
            steps {
                publishStatus('ci/pipeline-factory/sign', 'IN_PROGRESS')

                awsLogin(roleArn: env.SIGNER_ROLE_ARN, region: env.AWS_REGION) {
                    sh '''
                        set -euo pipefail
                        # Build the assumed-role STS session ARN to record as signer_principal
                        CALLER=$(aws sts get-caller-identity --query Arn --output text)
                        for root in packages pipelines; do
                            uv run manifest-signer sign-all \
                              --root "$root" \
                              --key-arn "$KMS_KEY_ARN" \
                              --upload-to-bucket "$SIGNED_MANIFESTS_BUCKET" \
                              --signer-principal "$CALLER"
                        done
                    '''
                }
            }
            post {
                success { publishStatus('ci/pipeline-factory/sign', 'SUCCESS') }
                failure { publishStatus('ci/pipeline-factory/sign', 'FAILURE') }
            }
        }

        // -----------------------------------------------------------------
        // STAGE 3 — Register (push to main only, after sign)
        // -----------------------------------------------------------------
        stage('register (POST to Registry API)') {
            when {
                allOf {
                    branch 'main'
                    not { changeRequest() }
                    expression { return env.REGISTRAR_ROLE_ARN?.trim() }
                }
            }
            steps {
                publishStatus('ci/pipeline-factory/register', 'IN_PROGRESS')

                awsLogin(roleArn: env.REGISTRAR_ROLE_ARN, region: env.AWS_REGION) {
                    sh '''
                        set -euo pipefail
                        for reg in pipelines/*/*/registration.json; do
                            pipeline=$(echo "$reg" | sed -E 's|pipelines/([^/]+)/([^/]+)/registration.json|\\1@\\2|')
                            echo "Registering $pipeline"
                            uv run generate-pipeline register --pipeline "$pipeline"
                        done
                    '''
                }
            }
            post {
                success { publishStatus('ci/pipeline-factory/register', 'SUCCESS') }
                failure { publishStatus('ci/pipeline-factory/register', 'FAILURE') }
            }
        }
    }

    post {
        // Signal the unconfigured state — matches the "Skip if not configured"
        // GHA no-op so first runs don't fail before real ARNs land.
        always {
            script {
                if (!env.SIGNER_ROLE_ARN?.trim()) {
                    echo "[pipeline-factory] SIGNER_ROLE_ARN unset — sign stage was a no-op."
                    publishStatus('ci/pipeline-factory/sign', 'NEUTRAL',
                                  description: 'AWS creds not configured')
                }
                if (!env.REGISTRAR_ROLE_ARN?.trim()) {
                    echo "[pipeline-factory] REGISTRAR_ROLE_ARN unset — register stage was a no-op."
                    publishStatus('ci/pipeline-factory/register', 'NEUTRAL',
                                  description: 'AWS creds not configured')
                }
            }
        }
        cleanup {
            cleanWs(deleteDirs: true, notFailBuild: true, patterns: [
                [pattern: '.uv-cache/**', type: 'EXCLUDE'],
            ])
        }
    }
}
