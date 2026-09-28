# Exercise 6: Real-Time Operations Monitoring and Alerting (Prometheus, Grafana, Jenkins)

## Objective

As a DevOps engineer at a quick-commerce company, build a monitoring pipeline for a delivery service. A Python app simulates delivery metrics, Prometheus scrapes them and evaluates alert rules, Grafana visualizes them on a dashboard, and a Jenkins pipeline builds and deploys the whole stack.

## Architecture

All containers share one user-defined Docker network (`monitoring-net`) and reach each other by container name.

```
delivery_metrics (:8000)  <--scrape--  prometheus (:9090)  <--query--  grafana (:3000)
        ^                                    ^
        |                                    |
        +---------- rebuilt and redeployed by jenkins (:8080) ----------+
```

## Windows-Specific Changes

The original exercise is written for Linux. These changes were needed on Windows with Docker Desktop.

| Original exercise | What was done instead | Why |
|---|---|---|
| `--network=host` and target `172.17.0.1` | User-defined network `monitoring-net`, targets by container name | Host networking and the docker0 address only exist on Linux. On Docker Desktop, "host" is a hidden VM, not Windows. |
| `python3 delivery_metrics.py` on the host | The app runs in a container built from its own Dockerfile | No Python needed on Windows, and Prometheus reaches it by name. |
| No Dockerfile provided | Added `Dockerfile` for the metrics app | The Jenkinsfile runs `docker build`, which needs one. |
| `alerts_rules.yml`, `alert_rules.yml`, `prometheus.ym` used inconsistently | Standardized on `alert_rules.yml` and `prometheus.yml` | `prometheus.yml` references the rules file by exact name. |
| Default Prometheus intervals | `scrape_interval` and `evaluation_interval` set to 5s | The default evaluation interval is 1 minute, so alerts would take over a minute to appear. |
| Jenkinsfile copies from a placeholder path and runs `docker` | Custom Jenkins image with the docker CLI, Docker socket mounted, project folder mounted at `/src`, Prometheus config baked into an image | See Troubleshooting Notes. |

## Project Structure

```
delivery_monitoring/
├── delivery_metrics.py     # simulates delivery metrics
├── Dockerfile              # image for the metrics app
├── prometheus.yml          # Prometheus scrape configuration
├── alert_rules.yml         # alert rules
├── Dockerfile.prometheus   # Prometheus image with config baked in (used by Jenkins)
├── Dockerfile.jenkins      # Jenkins image with the docker CLI
└── Jenkinsfile             # pipeline definition
```

## Step 1: Metrics Application

**delivery_metrics.py**

```python
from prometheus_client import start_http_server, Summary, Gauge
import random
import time

# Metrics
total_deliveries = Gauge("total_deliveries", "Total number of deliveries")
pending_deliveries = Gauge("pending_deliveries", "Number of pending deliveries")
on_the_way_deliveries = Gauge("on_the_way_deliveries", "Number of deliveries on the way")
average_delivery_time = Summary("average_delivery_time", "Average delivery time in seconds")

# Simulate delivery statuses
def simulate_delivery():
    pending = random.randint(10, 20)  # Ensure values exceed the threshold
    on_the_way = random.randint(5, 20)
    delivered = random.randint(30, 70)
    avg_time = random.uniform(15, 45)

    total = pending + on_the_way + delivered

    print(f"[DEBUG] Total deliveries: {total}")
    print(f"[DEBUG] Pending deliveries: {pending}")
    print(f"[DEBUG] On-the-way deliveries: {on_the_way}")
    print(f"[DEBUG] Average delivery time: {avg_time:.2f} seconds")

    total_deliveries.set(total)
    pending_deliveries.set(pending)
    on_the_way_deliveries.set(on_the_way)
    average_delivery_time.observe(avg_time)

if __name__ == "__main__":
    print("[INFO] Starting the HTTP server on port 8000...")
    start_http_server(8000, addr="0.0.0.0")
    print("[INFO] HTTP server started. Simulating deliveries...")
    while True:
        simulate_delivery()
        print("[INFO] Sleeping for 1 seconds...")
        time.sleep(1)
```

**Dockerfile**

```
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir prometheus-client
COPY delivery_metrics.py .
CMD ["python", "-u", "delivery_metrics.py"]
```

The `-u` flag disables output buffering. Without it, `docker logs` shows nothing because Python buffers stdout when it is not attached to a terminal.

**Build and run:**

```
docker network create monitoring-net
docker build -t delivery_metrics .
docker run -d --name delivery_metrics --network monitoring-net -p 8000:8000 delivery_metrics
docker logs --tail 12 delivery_metrics
curl.exe -s http://localhost:8000/metrics | findstr deliver
```

![Metrics app running, logs, and metrics endpoint](Images/delivery-metrics-app.png)

The `/metrics` endpoint is created automatically by `start_http_server` from the `prometheus_client` library. The four metrics defined in the code appear in it: three Gauges (values that go up and down) and one Summary, which exposes `average_delivery_time_sum` and `average_delivery_time_count`.

## Step 2: Prometheus

**prometheus.yml**

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "delivery_service"
    static_configs:
      - targets: ["delivery_metrics:8000"]

rule_files:
  - /etc/prometheus/alert_rules.yml
```

**alert_rules.yml**

```yaml
groups:
  - name: delivery_alerts
    rules:
      - alert: HighPendingDeliveries
        expr: pending_deliveries > 10
        for: 15s
        labels:
          severity: warning
        annotations:
          summary: "High pending deliveries"
          description: "Pending deliveries are above 10 for the last 15 second."

      - alert: HighAverageDeliveryTime
        expr: (average_delivery_time_sum / average_delivery_time_count) > 30
        labels:
          severity: critical
        annotations:
          summary: "High average delivery time"
          description: "Average delivery time is above 30 seconds for the last 15 seconds."
```

**Run Prometheus** (Command Prompt; in PowerShell replace `%cd%` with `${PWD}`):

```
docker run -d --name prometheus --network monitoring-net -p 9090:9090 -v "%cd%\prometheus.yml:/etc/prometheus/prometheus.yml" -v "%cd%\alert_rules.yml:/etc/prometheus/alert_rules.yml" prom/prometheus
docker ps
docker logs --tail 8 prometheus
```

![Prometheus container running](Images/prometheus-run.png)

The logs end with "Server is ready to receive web requests" and no configuration errors, so both the config and the rules file loaded.

**Targets** (`http://localhost:9090/targets`): both scrape jobs are UP. The delivery service is reached by container name at `delivery_metrics:8000`.

![Prometheus targets](Images/prometheus-targets.png)

**Alerts** (`http://localhost:9090/alerts`): `HighPendingDeliveries` is firing, because the simulated pending values of 10 to 20 are almost always above the threshold of 10. `HighAverageDeliveryTime` was inactive when this was captured. Its simulated average (uniform between 15 and 45) hovers right around the threshold of 30, so it can flicker.

![Prometheus alerts](Images/prometheus-alerts.png)

## Step 3: Grafana

```
docker run -d --name grafana --network monitoring-net -p 3000:3000 grafana/grafana
```

Open `http://localhost:3000` and log in with `admin` / `admin` (skip the password change).

**Add the data source:** Connections, Data sources, Add data source, Prometheus. Set the URL to `http://prometheus:9090` and click Save & test.

The URL uses the container name, not `localhost` or an IP address. Inside Grafana's container, `localhost` refers to Grafana itself.

![Prometheus data source test succeeded](Images/grafana-datasource-test.png)

![Prometheus data source listed with URL http://prometheus:9090](Images/grafana-datasource.png)

**Create the dashboard** `Delivery Monitoring` with four panels (data source Prometheus, query mode Code):

| Panel | Query |
|---|---|
| Total Deliveries | `total_deliveries` |
| Pending Deliveries | `pending_deliveries` |
| On-the-Way Deliveries | `on_the_way_deliveries` |
| Average Delivery Time | `average_delivery_time_sum / average_delivery_time_count` |

Set the time range to the last 5 minutes with a 5 second refresh.

![Grafana dashboard](Images/grafana-dashboard.png)

## Step 4: Jenkins Pipeline

The stock Jenkins image has no `docker` command, so the pipeline needs a custom image and access to the host's Docker daemon through its socket.

**Dockerfile.prometheus** bakes the config into the image. Bind-mounting files from inside a pipeline fails, because the Docker daemon resolves mount paths on its own side, where the Jenkins workspace path does not exist.

```
FROM prom/prometheus
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY alert_rules.yml /etc/prometheus/alert_rules.yml
```

**Dockerfile.jenkins** adds the docker CLI:

```
FROM jenkins/jenkins:lts
USER root
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker
```

Jenkins runs as root so it can use the mounted Docker socket. This is acceptable for a local lab but should not be done on a shared machine, since access to the Docker socket is equivalent to root on the host.

**Jenkinsfile**

```groovy
pipeline {
    agent any
    stages {
        stage('Pre-check Docker') {
            steps {
                sh 'docker --version'
                sh 'docker info > /dev/null'
                echo 'Docker is available and running'
            }
        }
        stage('Setup Workspace') {
            steps {
                // /src is the delivery_monitoring folder mounted into the Jenkins container
                sh 'cp /src/delivery_metrics.py /src/Dockerfile /src/Dockerfile.prometheus /src/prometheus.yml /src/alert_rules.yml .'
                sh 'ls -l'
            }
        }
        stage('Build Docker Images') {
            steps {
                sh 'docker build -t delivery_metrics .'
                sh 'docker build -t prometheus_delivery -f Dockerfile.prometheus .'
            }
        }
        stage('Run Application') {
            steps {
                sh '''
                docker network inspect monitoring-net >/dev/null 2>&1 || docker network create monitoring-net
                docker rm -f delivery_metrics || true
                docker run -d --name delivery_metrics --network monitoring-net -p 8000:8000 delivery_metrics
                '''
            }
        }
        stage('Run Prometheus & Grafana') {
            steps {
                sh '''
                docker rm -f prometheus || true
                docker run -d --name prometheus --network monitoring-net -p 9090:9090 prometheus_delivery
                docker inspect grafana >/dev/null 2>&1 || docker run -d --name grafana --network monitoring-net -p 3000:3000 grafana/grafana
                docker start grafana || true
                '''
            }
        }
    }
}
```

Changes from the original Jenkinsfile: it copies from `/src` instead of a placeholder path, removes old containers before recreating them so names do not clash, and creates Grafana only if it does not already exist so the saved dashboard survives a pipeline run.

**Start Jenkins:**

```
docker build -t jenkins-docker -f Dockerfile.jenkins .
docker run -d --name jenkins -p 8080:8080 -p 50000:50000 -v jenkins_home:/var/jenkins_home -v /var/run/docker.sock:/var/run/docker.sock -v E:/devops/DEVOPS/delivery_monitoring:/src:ro --user root jenkins-docker
docker exec jenkins docker ps
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

`docker exec jenkins docker ps` confirms Jenkins can see the host's containers through the socket. The last command prints the one-time unlock password.

![Jenkins started and able to see the host's containers](Images/jenkins-start.png)

**Create the pipeline job:** open `http://localhost:8080`, unlock with the password, install the suggested plugins, create an admin user, then New Item, name it `delivery-monitoring-pipeline`, choose Pipeline, paste the Jenkinsfile into the Pipeline script box, save, and click Build Now.

The build finishes with `Finished: SUCCESS`. The console shows each Docker command the pipeline ran: it removed and recreated `delivery_metrics` and `prometheus`, and started the existing `grafana` container instead of creating a new one.

![Jenkins console output, Finished: SUCCESS](Images/jenkins-console-output.png)

## Step 5: Simulate an Alert

In `delivery_metrics.py`, increase the pending range:

```python
pending = random.randint(50, 100)  # Increase range to exceed alert threshold
```

Run the Jenkins pipeline again with Build Now. It copies the changed file, rebuilds the image and recreates the `delivery_metrics` container. Prometheus does not need a restart because its rules did not change.

```
curl.exe -s http://localhost:8000/metrics | findstr pending_deliveries
```

Check that the value is now between 50 and 100, that the Pending Deliveries panel on the dashboard moves up to that range, and that `HighPendingDeliveries` is still firing on `http://localhost:9090/alerts`.

## Troubleshooting Notes

**Host networking does not work on Docker Desktop for Windows.** `--network=host` attaches a container to the hidden Linux VM's network, not to Windows, and `172.17.0.1` is the Linux `docker0` bridge address. The fix is a user-defined bridge network, where containers resolve each other by name.

**`docker logs` was empty for the Python app.** Python buffers stdout when it is not attached to a terminal. Running it with `python -u` in the Dockerfile fixes it.

**Alerts took over a minute to appear.** Prometheus evaluates rules every 1 minute by default. Setting `evaluation_interval: 5s` in `prometheus.yml` makes the alert visible within about 20 seconds (5 seconds of evaluation plus the 15 second `for` duration).

**The Jenkinsfile in the original exercise cannot succeed as written.** It builds an image without a Dockerfile, runs `docker` inside a Jenkins image that does not contain the CLI, copies from a placeholder path, and starts containers named `prometheus` and `grafana` that already exist. The version above fixes each of these.

**Bind mounts from a pipeline do not work through the Docker socket.** The Docker daemon resolves `-v` source paths on its own side, where the Jenkins workspace does not exist, so it would mount an empty directory. Baking the config into the Prometheus image avoids this.

**Do not remove the Grafana container to "clean up".** It has no volume, so removing it deletes the data source and dashboard.

**Filenames in the original exercise are inconsistent** (`alerts_rules.yml`, `alert_rules.yml`, `prometheus.ym`). `prometheus.yml` refers to `/etc/prometheus/alert_rules.yml` by exact name, so use that name everywhere.

## Key Observations

- **Pull-based monitoring:** Prometheus scrapes `/metrics` from the app on a schedule. The app never pushes data.
- **Metric types:** a Gauge goes up and down (pending deliveries). A Summary tracks the sum and count of observations, which gives an average when divided.
- **Alert lifecycle:** an alert goes inactive, then pending while the condition holds for the `for` duration, then firing.
- **Service discovery by name:** on a user-defined Docker network, container names resolve through Docker's built-in DNS. This is the same mechanism as Exercise 4.
- **CI/CD for monitoring:** the Jenkins pipeline turns a code change into a redeployed, monitored service with one click.
