# Exercise 3: Scaling a Flask App Using ReplicaSets

## Real-Life Use Case: E-commerce Flash Sale

During a flash sale (e.g. Big Billion Days, Prime Day), traffic can spike from ~100 requests/minute to 10,000+ requests/minute. A single Pod would crash under this load. ReplicaSets let Kubernetes scale out to many identical Pods to distribute traffic, then scale back down once demand drops.

## Objective

- Understand ReplicaSets and Pods
- Scale a Flask app deployment
- Observe pod distribution and self-healing

## App: Flash Sale Checkout Service

```
from flask import Flask, request
import socket, time, random

app = Flask(__name__)

@app.get("/")
def homepage():
    return {"message": "Welcome to Big Sale!", "pod": socket.gethostname(), "ts": time.time()}

@app.get("/buy")
def buy():
    item = random.choice(["Smartphone", "Shoes", "Headphones", "Laptop"])
    user = request.args.get("user", f"user{random.randint(1,1000)}")
    return {"status": "success", "item": item, "user": user, "served_by_pod": socket.gethostname(), "time": time.strftime("%H:%M:%S")}

@app.get("/health")
def health():
    return {"status": "healthy", "pod": socket.gethostname()}
```

## Dockerfile

```
FROM python:3.11-slim
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir flask gunicorn
CMD ["gunicorn","-b","0.0.0.0:5000","app:app","--workers","1","--threads","2"]
```

## Step 1: Confirm Minikube is running

```
minikube status
```

## Step 2: Build the image (Windows-specific step)

On Windows, `eval $(minikube docker-env)` fails because it requires an SSH agent that isn't supported on Windows. Instead, build the image on the host's Docker Desktop, then load it into Minikube directly:

```
docker build -t flashsale:1.0 .
```

![Docker build](Images/flashsale-docker-build.png)

```
minikube image load flashsale:1.0
```

## Step 3: ReplicaSet + Service YAML

```
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: flashsale-rs
  labels:
    app: flashsale
spec:
  replicas: 3
  selector:
    matchLabels:
      app: flashsale
  template:
    metadata:
      labels:
        app: flashsale
    spec:
      containers:
      - name: flashsale-container
        image: flashsale:1.0
        imagePullPolicy: Never
        ports:
        - containerPort: 5000
        readinessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 2
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: flashsale-svc
spec:
  selector:
    app: flashsale
  ports:
  - name: http
    port: 80
    targetPort: 5000
  type: ClusterIP
```

## Step 4: Apply the ReplicaSet

```
kubectl apply -f flashsale-replicaset.yaml
```

![ReplicaSet and Service applied](Images/flashsale-apply.png)

## Step 5: Verify initial pods and ReplicaSet

```
kubectl get pods
kubectl get rs
```

![Initial pods running](Images/flashsale-initial-pods.png)

3 Pods come up, all `Running`.

## Step 6: Scale up to 5 replicas

```
kubectl scale rs flashsale-rs --replicas=5
kubectl get rs
kubectl get pods
```

Kubernetes created 2 additional pods within seconds to reach the desired count of 5, all `Running`.

## Step 7: Delete a pod and observe self-healing

```
kubectl delete pod <pod-name>
kubectl get pods -o wide
```

![Pod deletion, self-healing, and distribution](Images/flashsale-self-heal.png)

Kubernetes immediately terminates the deleted pod and spins up a replacement to maintain the desired replica count. All pods run on the single Minikube node (`minikube`), each with a unique internal IP.

## Key Observations

- **Pod Distribution** — each Pod is an identical worker; scaling creates clones of the app.
- **Resiliency** — deleting a pod triggers automatic replacement, so users see no downtime.
- **Efficiency** — Pods are added under load and removed when demand drops, avoiding over-provisioning.
- **Real-World Parallel** — this is how Netflix, YouTube, and Swiggy scale microservices during peak traffic.

## Windows-Specific Notes

`eval $(minikube docker-env)` fails on Windows with `SSH_AGENT_START: starting an SSH agent on Windows is not yet supported`, since it relies on SSH tunnel setup that Windows doesn't support the same way Linux/macOS do. The workaround used throughout this exercise series is to build images normally on host Docker Desktop, then explicitly transfer them into Minikube's image store with `minikube image load <image>:<tag>`, keeping `imagePullPolicy: Never` in the pod spec so Kubernetes uses the locally loaded image instead of attempting a registry pull.

## Q&A

**Q1: What is the initial number of replicas?** A: 3

**Q2: What happens when scaling to 5 replicas?** A: Kubernetes creates 2 additional pods to reach the desired count of 5.

**Q3: What happens when a pod is deleted?** A: Kubernetes automatically creates a new pod to replace it, maintaining the desired replica count.

**Q4: How does Kubernetes maintain the desired replica count?** A: It continuously compares actual running pods to the desired count and creates or deletes pods to reconcile any difference.

**Q5: How many nodes were used?** A: 1 (single-node Minikube cluster) — all pods scheduled on the same node.
