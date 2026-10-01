# Exercise 7: Introduction to Continuous Integration (CI) and Jenkins Installation

## Problem Statement

Understand what Continuous Integration (CI) is and how a CI server fits into the development workflow, then install Jenkins using Docker, retrieve the initial admin password, and access the Jenkins web interface on port 8082.

**Environment:** Windows, VS Code integrated terminal (Command Prompt), Docker Desktop

---

## Concepts (Brief)

**Continuous Integration (CI)** is a practice where developers frequently merge code changes into a shared repository. Every commit triggers an automated build and automated tests, so errors are detected early and developers get immediate feedback.

**CI workflow:**
1. A developer pushes code to a Git repository.
2. The CI server detects the push and triggers a build.
3. Automated tests validate the code.
4. Results (success or failure) are reported back to the developers.

**Jenkins** is an open-source automation server used to build, test, and deploy software, enabling CI and Continuous Delivery (CD). Key concepts: Job/Project, Build, Pipeline, Plugins, and Nodes (master/agent).

---

## Solution (Brief)

1. Check Docker and any existing Jenkins container.
2. Run Jenkins in a Docker container, exposing the web interface on port 8082 and the agent port 50000.
3. Retrieve the initial admin password from inside the container.
4. Open `http://localhost:8082`, unlock Jenkins, and complete the setup wizard.

---

## Commands Executed and Output

### Step 1: Check Docker and existing containers

```cmd
docker --version
```

```
Docker version 29.8.2, build 7fc2dff
```


### Step 2: Install Jenkins using Docker

```cmd
docker run -d --name jenkins -p 8082:8080 -p 50000:50000 jenkins/jenkins:lts
```

- `-d`: runs the container in the background
- `-p 8082:8080`: exposes the Jenkins web interface on host port 8082
- `-p 50000:50000`: exposes the agent communication port

```
f648938b19fe0da577ac2f3b19f4f9fc927f6c2ec4b5b6039a0b5d78d9f3f8dc
```

### Step 3: Verify that Jenkins is running

```cmd
docker ps -a
```

```
CONTAINER ID   IMAGE                                 COMMAND                  CREATED          STATUS                      PORTS                                                                                          NAMES
f648938b19fe   jenkins/jenkins:lts                   "/usr/bin/tini -- /u…"   32 seconds ago   Up 31 seconds               0.0.0.0:50000->50000/tcp, [::]:50000->50000/tcp, 0.0.0.0:8082->8080/tcp, [::]:8082->8080/tcp   jenkins
e812b3e0d6bc   gcr.io/k8s-minikube/kicbase:v0.0.50   "/usr/local/bin/entr…"   27 hours ago     Exited (130) 24 hours ago                                                                                                  minikube
```


### Step 4: Get the Jenkins initial admin password

```cmd
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

```
Password :)
```

### Step 5: Access Jenkins on port 8082

Open the following URL in the browser:

```
http://localhost:8082/
```

**Unlock Jenkins** by pasting the initial admin password:

![Jenkins - Unlock Jenkins](screenshots/jenkins-unlock.png)

**Customize Jenkins** by choosing *Install suggested plugins*:

![Jenkins - Getting Started](screenshots/jenkins-getting-started.png)


**Create the first admin user** and confirm the Jenkins URL:

![Jenkins - Create admin user](screenshots/jenkins-create-admin.png)

**Jenkins landing page (dashboard):**

![Jenkins - Landing page](screenshots/jenkins-landing-page.png)

---

## Result

Jenkins was installed using the `jenkins/jenkins:lts` Docker image, the initial admin password was retrieved from the container, and the Jenkins dashboard is accessible at `http://localhost:8082`.