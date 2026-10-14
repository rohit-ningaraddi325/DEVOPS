# Exercise 10: Multi-Node Kubernetes Cluster with Multiple Applications and ReplicaSets

## Objective

Deploy two Flask microservices on a 3-node Minikube cluster and use pod anti-affinity so that replicas of the same service run on different nodes, improving availability.

## Scenario

An e-commerce platform with two microservices:

- **Product Catalog:** 2 replicas, lists products.
- **Shopping Cart:** 3 replicas, manages carts.

**Environment:** Windows 11, Command Prompt in the VS Code terminal, Docker Desktop, Minikube (docker driver), kubectl, Python 3.9 base image, Flask.

## Windows-Specific Changes

| Original exercise | What was done instead | Why |
|---|---|---|
| `minikube stop` then `minikube delete` | A separate profile, `devops-multinode`, with the earlier cluster left alone | Deleting the default profile is unnecessary. A named profile keeps the single-node cluster from earlier exercises intact. |
| Registry addon, then `image load` | `minikube image load` only | `image load` copies images straight into every node's container runtime, so the registry addon is not needed. |
| Image pull default for the `latest` tag | `imagePullPolicy: Never` in both Deployments | With the `latest` tag Kubernetes tries to pull from a registry by default, which fails for images that only exist locally. |
| `curl` with single quotes around JSON | `curl.exe` with escaped double quotes | In Command Prompt, single quotes do not group arguments and `curl` is a PowerShell alias for a different command. |
| Service URLs from `minikube service` | `minikube service ... --url`, each in its own window | With the docker driver on Windows, the command prints a tunnel URL and must keep running. |

## Step 1: Start a 3-node Cluster

```cmd
minikube stop
minikube start --nodes 3 -p devops-multinode --driver=docker
kubectl config use-context devops-multinode
kubectl get nodes
```

`minikube stop` stops the earlier single-node cluster to free memory. Each node of the new cluster is created as a Docker container with 2 CPUs and 3072 MB of memory.

![Cluster start and three Ready nodes](Images/multinode-cluster-nodes.png)

All three nodes are `Ready`: `devops-multinode` (control-plane), `devops-multinode-m02` and `devops-multinode-m03`, running Kubernetes v1.37.0.

## Step 2: Create the Applications

**product_catalog.py**

```python
from flask import Flask, jsonify

app = Flask(__name__)

products = [
    {"id": 1, "name": "Laptop", "price": 1000},
    {"id": 2, "name": "Phone", "price": 500},
    {"id": 3, "name": "Headphones", "price": 100},
]

@app.route("/products", methods=["GET"])
def get_products():
    return jsonify(products)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
```

**shopping_cart.py**

```python
from flask import Flask, jsonify, request

app = Flask(__name__)

cart = []

@app.route("/cart", methods=["GET"])
def get_cart():
    return jsonify(cart)

@app.route("/cart", methods=["POST"])
def add_to_cart():
    item = request.get_json()
    cart.append(item)
    return jsonify({"status": "added", "item": item}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
```

## Step 3: Dockerize Both Applications

**Dockerfile.product**

```
FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir flask
COPY product_catalog.py .
CMD ["python", "-u", "product_catalog.py"]
```

**Dockerfile.shopping**

```
FROM python:3.9-slim
WORKDIR /app
RUN pip install --no-cache-dir flask
COPY shopping_cart.py .
CMD ["python", "-u", "shopping_cart.py"]
```

```cmd
docker build -t product-catalog:latest -f Dockerfile.product .
docker build -t shopping-cart:latest -f Dockerfile.shopping .
```

## Step 4: Load the Images into the Cluster

```cmd
minikube -p devops-multinode image load product-catalog:latest
minikube -p devops-multinode image load shopping-cart:latest
minikube -p devops-multinode image ls
```

`image load` copies each image onto all three nodes, so a pod can start wherever it is scheduled. `image ls` lists `docker.io/library/product-catalog:latest` and `docker.io/library/shopping-cart:latest` alongside the Kubernetes system images.

## Step 5: Deploy with Required Pod Anti-Affinity

Each file contains a Deployment and a Service. The anti-affinity rule says a pod must not be scheduled on a node that already runs a pod with the same `app` label. `topologyKey: kubernetes.io/hostname` makes each node its own scheduling domain.

**product_catalog.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-catalog
spec:
  replicas: 2
  selector:
    matchLabels:
      app: product-catalog
  template:
    metadata:
      labels:
        app: product-catalog
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - product-catalog
            topologyKey: kubernetes.io/hostname
      containers:
      - name: product-catalog
        image: product-catalog:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: product-catalog-service
spec:
  type: NodePort
  selector:
    app: product-catalog
  ports:
  - port: 80
    targetPort: 80
```

**shopping_cart.yaml**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shopping-cart
spec:
  replicas: 3
  selector:
    matchLabels:
      app: shopping-cart
  template:
    metadata:
      labels:
        app: shopping-cart
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - shopping-cart
            topologyKey: kubernetes.io/hostname
      containers:
      - name: shopping-cart
        image: shopping-cart:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: shopping-cart-service
spec:
  type: NodePort
  selector:
    app: shopping-cart
  ports:
  - port: 80
    targetPort: 80
```

Both manifests use the `default` namespace, so the Deployments and Services are created together.

```cmd
kubectl apply -f product_catalog.yaml
kubectl apply -f shopping_cart.yaml
kubectl get pods -o wide
```

![Image load, deployments applied and pod distribution](Images/multinode-deploy-pods.png)

All five pods are `Running`, and each is on a different node from the other pods of the same service:

| Pod | Node |
|---|---|
| product-catalog-6f777c4c78-8trfr | devops-multinode-m02 |
| product-catalog-6f777c4c78-v8lp2 | devops-multinode-m03 |
| shopping-cart-68655875d6-hjxdm | devops-multinode (control-plane) |
| shopping-cart-68655875d6-j5s2f | devops-multinode-m02 |
| shopping-cart-68655875d6-tlhk8 | devops-multinode-m03 |

The same `apply` and `get pods -o wide` output as captured in the narrower terminal (the columns wrap, but the pod names, `Running` status and nodes are the same):

![Deployments applied and pods spread across nodes](Images/multinode-pods-distribution.png)

The 3 shopping-cart replicas use all three nodes, including the control-plane node. A Product Catalog pod and a Shopping Cart pod can share a node, because the anti-affinity rule only compares pods with the same `app` label.

## Step 6: Access and Test the Services

Each service was exposed in its own Command Prompt window, which has to stay open:

```cmd
minikube -p devops-multinode service product-catalog-service --url
minikube -p devops-multinode service shopping-cart-service --url
```

Each command prints a local tunnel URL (`http://127.0.0.1:<port>`). Then, from a third window:

```cmd
curl.exe http://127.0.0.1:<product-port>/products
curl.exe http://127.0.0.1:<cart-port>/cart
curl.exe -X POST http://127.0.0.1:<cart-port>/cart -H "Content-Type: application/json" -d "{\"id\": 1, \"name\": \"Laptop\", \"quantity\": 1}"
curl.exe http://127.0.0.1:<cart-port>/cart
```

![curl tests against both services](Images/multinode-service-test.png)

- `/products` returns the three products (Laptop, Phone, Headphones) as JSON.
- The first `/cart` returns `[]`.
- The POST returns `{"item":{"id":1,"name":"Laptop","quantity":1},"status":"added"}`.
- The next four `GET /cart` calls returned `[]`, and the fifth returned `[{"id":1,"name":"Laptop","quantity":1}]`.

## Observations

- **Anti-affinity works.** The scheduler placed the two Product Catalog pods on two different nodes and the three Shopping Cart pods on three different nodes. Losing one node would not take out every replica of a service.
- **The cart data is inconsistent across requests.** The cart is a Python list stored in each pod's memory. The POST was handled by one of the three Shopping Cart pods, so only that pod holds the Laptop. The Service sends each request to a pod, so most GETs reached a different pod and returned `[]`, and one reached the pod that had the item. This is a limit of the application design, not a Kubernetes fault. A real cart needs a shared store such as Redis or a database.
- **A Service load-balances across replicas.** The mixed results confirm that requests were spread across different pods.
- **`required` anti-affinity needs enough nodes.** With 3 replicas and a hard rule, the cluster needs at least 3 schedulable nodes. Minikube leaves the control-plane node schedulable, which is why one cart replica runs on it.
- **`image load` does not depend on the registry addon.** It copies the image directly into each node's container runtime.

## Review Questions

**Q1: How does a `required` anti-affinity rule differ from a `preferred` one?**
A `required` rule is a hard constraint. If no node satisfies it, the pod stays `Pending`. A `preferred` rule is a soft preference. The scheduler tries to follow it but will still place the pod on a node that breaks it.

**Q2: Why does `minikube image load` work without the registry addon?**
It exports the image from the host's Docker and imports it directly into each node's container runtime. No registry is involved.

**Q3: What happens to service availability if one node fails?**
Pods on the other nodes keep serving, because each service has replicas on several nodes. The Deployment tries to recreate the lost pods, but with `required` anti-affinity and only three nodes, the replacement for a 3-replica service has no valid node and stays `Pending` until the node returns.

**Q4: Why do mismatched namespaces between related manifests cause failures?**
Kubernetes objects are namespaced, and a Service only selects pods in its own namespace. If one manifest references a namespace that was never created, applying it fails. Using `default` for both removes the problem.

## Result

A 3-node Minikube cluster (`devops-multinode`) ran two Flask microservices. Required pod anti-affinity spread the 2 Product Catalog replicas and the 3 Shopping Cart replicas across different nodes. Both services answered through NodePort tunnels, and the cart tests showed that in-memory state is not shared between replicas.
