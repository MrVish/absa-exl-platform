// awsLogin() — establish AWS credentials for the current stage.
//
// Three modes:
//   1. IRSA (recommended)     — no-op; the K8s pod ServiceAccount already
//                                holds an IAM role via the projected token.
//                                Detected by presence of $AWS_WEB_IDENTITY_TOKEN_FILE.
//   2. Explicit assume-role   — call `aws sts assume-role-with-web-identity` if
//                                a token file path is set; otherwise
//                                `aws sts assume-role`. Exports AWS_* env vars
//                                into the closure block.
//   3. Instance profile       — also no-op when running under EC2 instance
//                                profile (legacy fallback).
//
// Usage:
//
//   awsLogin(region: 'eu-west-1') {
//       sh 'aws sts get-caller-identity'
//   }
//
//   awsLogin(roleArn: env.SIGNER_ROLE_ARN, region: 'eu-west-1') {
//       sh 'uv run manifest-signer sign-all ...'
//   }

def call(Map args = [:], Closure body) {
    final region   = args.region ?: 'eu-west-1'
    final roleArn  = args.roleArn
    final sessName = args.sessionName ?: "jenkins-${env.BUILD_TAG ?: 'local'}"

    final irsaToken = env.AWS_WEB_IDENTITY_TOKEN_FILE
    final hasIrsa   = irsaToken && fileExists(irsaToken)

    if (!roleArn || hasIrsa) {
        // IRSA or instance profile: nothing to do — SDK picks creds up
        // from the default chain.
        echo "[awsLogin] using ambient identity (IRSA=${hasIrsa ? 'yes' : 'no'}, region=${region})"
        withEnv(["AWS_DEFAULT_REGION=${region}", "AWS_REGION=${region}"]) {
            body()
        }
        return
    }

    // Explicit assume-role path. Uses the Jenkins agent's ambient identity
    // to call sts:AssumeRole, then exports the resulting session creds for
    // the body block.
    echo "[awsLogin] assuming role ${roleArn} (session=${sessName}, region=${region})"
    final creds = sh(
        returnStdout: true,
        script: """
            set -euo pipefail
            aws sts assume-role \
              --role-arn '${roleArn}' \
              --role-session-name '${sessName}' \
              --duration-seconds 3600 \
              --query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken]' \
              --output text
        """,
    ).trim().split(/\s+/)

    withEnv([
        "AWS_ACCESS_KEY_ID=${creds[0]}",
        "AWS_SECRET_ACCESS_KEY=${creds[1]}",
        "AWS_SESSION_TOKEN=${creds[2]}",
        "AWS_DEFAULT_REGION=${region}",
        "AWS_REGION=${region}",
    ]) {
        body()
    }
}
