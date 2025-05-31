//
// Jenkins CI/CD pipeline for Payload Analyzer microservice.
// Builds, tests, scans, pushes Docker images, deploys to Minikube, runs integration and load tests, and simulates rolling updates.
// Optimized for local development on macOS/Minikube, but can be adapted for other environments.
//
// Main stages: checkout, build, static analysis, security scan, unit/integration/load tests, coverage, push, deploy, rolling update, cleanup.
//

pipeline {
    agent any

    /* --------- Global environment variables --------- */
    environment {
        REGISTRY        = "registry:58640"    // Registry access from Jenkins, this is the MacOs only workaround, should be the same as REGISTRY_INTERNAL
        REGISTRY_INTERNAL = "localhost:5000"  // Registry access from minikube
        IMAGE           = "payload-analyzer"
        TAG             = "${env.BUILD_NUMBER}"
        DOCKER_BUILDKIT = "1"
        KUBECONFIG      = "${env.HOME}/.kube/config"
        K8S_NAMESPACE   = "jenkins-tests"
    }

    options {
        /* Abort the build if it runs for more than 1 hour */
        timeout(time: 1, unit: 'HOURS')
        // timestamps()           // Enable if you want timestamps
        // ansiColor('xterm')     // Enable if you want ANSI colour output
    }

    stages {
        /* --------- 1. Checkout source code --------- */
        stage('Checkout Source') {
            steps {
                checkout scm
            }
        }

        /* --------- 2. Build dev image (setup for parallel tests) --------- */
        stage('Build Dev Image') {
            steps {
                script {
                    // Get short commit SHA
                    def GIT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.GIT_SHA = GIT_SHA
                    // Build dev image once
                    sh '''
                        docker build --target dev -t $IMAGE-dev .
                    '''
                }
            }
        }

        /* --------- 3. Code quality and tests (run in parallel) --------- */
        stage('Quality & Tests') {
            parallel {
                stage('Static Analysis') {
                    steps {
                        sh '''
                            docker run --rm $IMAGE-dev ruff check app/
                            docker run --rm $IMAGE-dev mypy app/
                        '''
                    }
                }
                stage('Security Scan') {
                    steps {
                        sh '''
                            docker save $IMAGE-dev -o payload-analyzer-dev.tar
                            docker pull aquasec/trivy:latest
                            docker run --rm -v $PWD:/tmp \
                                aquasec/trivy image \
                                --input /tmp/payload-analyzer-dev.tar || true
                            docker run --rm -v $PWD:/project -w /project \
                                aquasec/trivy fs . || true
                        '''
                    }
                }
                stage('Unit Tests') {
                    steps {
                        sh '''
                            mkdir -p test-results
                            docker run --rm \
                                -v $WORKSPACE/test-results:/results \
                                $IMAGE-dev pytest tests/unit/ -v \
                                --junitxml=/results/unit.xml
                        '''
                    }
                }
            }
        }
        stage('Build Images') {
            steps {
                script {
                    // Use already built dev image, build prod image with two tags
                    sh '''
                        docker build -t $REGISTRY/$IMAGE:$TAG .
                        docker tag $REGISTRY/$IMAGE:$TAG $REGISTRY/$IMAGE:latest
                        docker tag $REGISTRY/$IMAGE:$TAG $REGISTRY/$IMAGE:$GIT_SHA
                    '''
                }
            }
        }

        /* --------- 4. Coverage report  --------- */
        stage('Coverage Report') {
            steps {
                sh """
                    # Generate coverage reports (XML + HTML)
                    docker run --rm \
                        -v \$WORKSPACE:/app -w /app -e PYTHONPATH=/app \
                        \$IMAGE-dev pytest tests/unit/ \
                        --cov=app \
                        --cov-report=xml:coverage.xml \
                        --cov-report=html:htmlcov

                    # Zip the HTML folder so it can be downloaded as one file
                    zip -qr coverage_html.zip htmlcov
                """

                /* Archive reports as regular artifacts */
                archiveArtifacts artifacts: 'coverage.xml,coverage_html.zip', fingerprint: true
            }
        }

        /* --------- 5. Push image (optional) --------- */
        stage('Push Image') {
            steps {
                sh '''
                    # Push production image to registry (both versioned and latest)
                    docker push $REGISTRY/$IMAGE:$TAG
                    docker push $REGISTRY/$IMAGE:latest
                '''
            }
        }

        /* --------- 6. Deploy to local Minikube cluster --------- */
        stage('Deploy to Minikube') {
            steps {
                script {
                    // Clean up all resources from deploy/ manifests in the test namespace
                    sh '''
                        kubectl delete -n $K8S_NAMESPACE -f deploy/k8s-deployment.yaml --ignore-not-found=true || true
                        kubectl delete -n $K8S_NAMESPACE -f deploy/k8s-service.yaml --ignore-not-found=true || true
                        kubectl delete -f deploy/prometheus-rbac.yaml --ignore-not-found=true || true
                        kubectl delete -n $K8S_NAMESPACE -f deploy/prometheus.yaml --ignore-not-found=true || true
                    '''
                    // Ensure namespace exists
                    sh 'kubectl create namespace $K8S_NAMESPACE || true'
                    // Apply all manifests into the test namespace
                    sh '''
                        kubectl apply -n $K8S_NAMESPACE -f deploy/k8s-deployment.yaml
                        kubectl apply -n $K8S_NAMESPACE -f deploy/k8s-service.yaml
                        kubectl apply -f deploy/prometheus-rbac.yaml
                        kubectl apply -n $K8S_NAMESPACE -f deploy/prometheus.yaml
                    '''
                }
            }
        }

        /* --------- 7. Validation & load testing (sequential) --------- */
        stage('Wait for Service Ready') {
            steps {
                sh '''
                    kubectl rollout status deployment/payload-analyzer -n $K8S_NAMESPACE --timeout=90s
                '''
                echo 'Deployment rollout complete and pods should be Ready.'
            }
        }

        /* ----- Integration tests ----- */
        stage('Integration Tests') {
            steps {
                script {
                    def ext_port = sh(
                        script: '''kubectl get svc payload-analyzer -n $K8S_NAMESPACE -o jsonpath='{.spec.ports[0].port}' || echo''',
                        returnStdout: true
                    ).trim()
                    def svc_url = "http://host.docker.internal:${ext_port}"
                    sh """
                        docker run --rm \
                            --add-host=host.docker.internal:host-gateway \
                            -e BASE_URL=${svc_url} \
                            -v $WORKSPACE/tests/integration:/integration \
                            $IMAGE-dev pytest /integration -v \
                                --junitxml=/integration/integration.xml
                        mv tests/integration/integration.xml test-results/integration.xml
                    """
                }
            }
        }

        /* ----- Lightweight load test ----- */
        stage('Load Test') {
            steps {
                script {
                    def service_port = sh(
                        script: '''kubectl get svc payload-analyzer -n $K8S_NAMESPACE -o json | jq -r '.spec.ports[0].port' ''', returnStdout: true
                    ).trim()
                    def prom_port = sh(
                        script: '''kubectl get svc prometheus -n $K8S_NAMESPACE -o json | jq -r '.spec.ports[0].port' ''', returnStdout: true
                    ).trim()
                    def full_service_url = "http://host.docker.internal:${service_port}"
                    def full_prom_url = "http://host.docker.internal:${prom_port}"
                    echo "Load test will use SERVICE_URL=${full_service_url} and PROMETHEUS_URL=${full_prom_url}"
                    sh """
                        docker run --rm \
                            --add-host=host.docker.internal:host-gateway \
                            -e N_REQUESTS=5000 \
                            -e SERVICE_URL=${full_service_url} \
                            -e PROMETHEUS_URL=${full_prom_url} \
                            -e HEALTH_ENDPOINT=${full_service_url}/health \
                            -v $WORKSPACE/tests/load:/load \
                            $IMAGE-dev python3 /load/test_load.py | tee load_test_report.txt
                    """
                }
                archiveArtifacts artifacts: 'load_test_report.txt', fingerprint: true
            }
        }
        // Prometheus cleanup before rolling update
        stage('Reset Prometheus') {
            steps {
                sh '''
                    kubectl delete -n $K8S_NAMESPACE -f deploy/prometheus.yaml --ignore-not-found=true || true
                    sleep 2
                    kubectl apply -n $K8S_NAMESPACE -f deploy/prometheus.yaml
                    # Wait for prometheus pod to become Ready
                    kubectl wait --for=condition=ready pod -l app=prometheus -n $K8S_NAMESPACE --timeout=60s
                '''
            }
        }
        /* --------- 8. Simulate rolling update and health-check --------- */
        stage('Simulate Rolling Update') {
            steps {
                script {
                    def ext_port = sh(
                        script: '''kubectl get svc payload-analyzer -o jsonpath='{.spec.ports[0].port}' --namespace=$K8S_NAMESPACE || echo''',
                        returnStdout: true
                    ).trim()
                    def svc_url = "http://host.docker.internal:${ext_port}"
                    def prom_port = sh(
                        script: '''kubectl get svc prometheus -n $K8S_NAMESPACE -o json | jq -r '.spec.ports[0].port' ''', returnStdout: true
                    ).trim()
                    def prom_url = "http://host.docker.internal:${prom_port}"
                    withEnv(["SERVICE_URL=${svc_url}", "PROMETHEUS_URL=${prom_url}"]) {
                        try {
                            // Print pods before rollout
                            sh 'kubectl get pods -n $K8S_NAMESPACE -o wide'
                            sh '''
                                # Start rolling update in background
                                kubectl set image deployment/payload-analyzer payload-analyzer=$REGISTRY_INTERNAL/$IMAGE:$TAG --namespace=$K8S_NAMESPACE &
                                rollout_pid=$!
                                # Print pods after rollout command
                                sleep 1
                                kubectl get pods -n $K8S_NAMESPACE -o wide
                                # Start load test in background
                                docker run --rm \
                                    --add-host=host.docker.internal:host-gateway \
                                    -e SERVICE_URL=$SERVICE_URL \
                                    -e PROMETHEUS_URL=$PROMETHEUS_URL \
                                    -e N_REQUESTS=5000 \
                                    -v $WORKSPACE/tests/load:/load \
                                    $IMAGE-dev python3 /load/test_load.py &
                                loadtest_pid=$!
                                # Wait for both background jobs to finish
                                wait $rollout_pid
                                # Print pods after rollout finished
                                kubectl get pods -n $K8S_NAMESPACE -o wide
                                wait $loadtest_pid
                                # Print pods after load test finished
                                kubectl get pods -n $K8S_NAMESPACE -o wide
                            '''
                            // After both are done, check health endpoint (single attempt, via official curl image)
                            sh """
                                docker run --rm \
                                    --add-host=host.docker.internal:host-gateway \
                                    curlimages/curl:8.8.0 \
                                    curl -sf "${svc_url}/health"
                            """
                            echo 'Rolling update and health check succeeded.'
                        } catch (err) {
                            echo 'Rolling update or health check failed. Performing rollback...'
                            sh 'kubectl rollout undo deployment/payload-analyzer --namespace=$K8S_NAMESPACE'
                            error('Rolling update or health check failed (service unhealthy or load test failed after rollout).')
                        }
                    }
                }
            }
        }
    }

    /* --------- Post-steps (always run) --------- */
    post {
        always {
            junit 'test-results/**/*.xml'
            archiveArtifacts artifacts: 'coverage.xml,coverage_html.zip,load_test_report.txt',
                              allowEmptyArchive: true
            cleanWs()
        }
    }
}
