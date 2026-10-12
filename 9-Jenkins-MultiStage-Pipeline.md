# Exercise 9: Jenkins Multi-Stage Pipeline, Deploying a Python Application

## Problem Statement

Automate the CI/CD pipeline for a Python Flask application using a Jenkins **Pipeline** with multiple stages:

1. **Build:** prepare the environment and confirm the tools are available.
2. **Test:** run unit tests to make sure the application works as expected.
3. **Deploy:** deploy the application by copying it to a mock deployment directory.
4. **Run Application / Test Application:** start the deployed app and run the tests again.

**Environment:** Windows 11, Command Prompt in the VS Code terminal, Docker Desktop, Jenkins running in Docker (`jenkins-docker` container from Exercise 6) on port **8080**.

## Setup Notes

- The application files and the `Jenkinsfile` are stored in the `Jenkins-MultiStage-Pipeline` sub-directory of the lab repository (`https://github.com/rohit-ningaraddi325/DEVOPS.git`).
- Because the files are in a sub-directory, the `Jenkinsfile` runs its steps inside `dir('Jenkins-MultiStage-Pipeline')`, and the job's **Script Path** is `Jenkins-MultiStage-Pipeline/Jenkinsfile`.
- The Jenkins image does not include Python, so Python 3, pip, venv and Flask are installed inside the Jenkins container.
- The job is created through Jenkins' REST API with `curl.exe`, the same approach as Exercise 8.

## Solution (Brief)

1. Create the Flask app, its unit test, and the `Jenkinsfile` in the `Jenkins-MultiStage-Pipeline` folder and push them to GitHub.
2. Create a Pipeline job that reads the `Jenkinsfile` from the Git repository (Pipeline script from SCM).
3. Run the build once. It fails in the Build stage because Python is missing from the Jenkins image.
4. Install Python 3 and Flask inside the Jenkins container.
5. Run the build again and verify that all stages pass.

## Files Created

```
Jenkins-MultiStage-Pipeline/
├── app.py
├── requirements.txt
├── test_app.py
└── Jenkinsfile
```

All four files are saved with LF line endings. The `sh '''...'''` blocks in the `Jenkinsfile` run on Linux, so CRLF endings from Windows would break them.

**app.py**

```python
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello, Jenkins Multi-Stage Pipeline!"

if __name__ == "__main__":
    app.run(debug=True)
```

**requirements.txt**

```
flask==2.1.2
```

**test_app.py**

```python
import unittest
from app import app

class TestApp(unittest.TestCase):
    def test_home(self):
        tester = app.test_client()
        response = tester.get("/")
        print(response.data.decode("utf-8"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode("utf-8"), "Hello, Jenkins Multi-Stage Pipeline!")

if __name__ == "__main__":
    unittest.main()
```

**Jenkinsfile**

```groovy
pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                echo 'Creating virtual environment and installing dependencies...'
                dir('Jenkins-MultiStage-Pipeline') {
                    sh 'python3 --version'
                }
            }
        }
        stage('Test') {
            steps {
                echo 'Running tests...'
                dir('Jenkins-MultiStage-Pipeline') {
                    sh 'python3 -m unittest discover -s .'
                }
            }
        }
        stage('Deploy') {
            steps {
                echo 'Deploying application...'
                dir('Jenkins-MultiStage-Pipeline') {
                    sh '''
                    mkdir -p python-app-deploy
                    cp app.py python-app-deploy/
                    '''
                }
            }
        }
        stage('Run Application') {
            steps {
                echo 'Running application...'
                dir('Jenkins-MultiStage-Pipeline') {
                    sh '''
                    nohup python3 python-app-deploy/app.py > python-app-deploy/app.log 2>&1 &
                    echo $! > python-app-deploy/app.pid
                    '''
                }
            }
        }
        stage('Test Application') {
            steps {
                echo 'Testing application...'
                dir('Jenkins-MultiStage-Pipeline') {
                    sh 'python3 test_app.py'
                }
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully!'
        }
        failure {
            echo 'Pipeline failed. Check the logs for more details.'
        }
    }
}
```

## Commands Executed

### Step 1: Push the application and Jenkinsfile to GitHub

Jenkins reads the `Jenkinsfile` from GitHub, so the folder must be pushed before the pipeline is run. Only this folder was added, so other unpushed folders were not included:

```cmd
cd /d E:\devops\DEVOPS
git add Jenkins-MultiStage-Pipeline
git status
git commit -m "Add Exercise 9 Jenkins multi-stage pipeline"
git push origin main
```

### Step 2: Create the Pipeline job through the REST API

An API token was created in Jenkins (user page, Security, Add new token). The job definition was saved as `job9.xml` in `E:\devops`, one level above the repository so it is never committed:

```xml
<?xml version='1.1' encoding='UTF-8'?>
<flow-definition>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition">
    <scm class="hudson.plugins.git.GitSCM">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>https://github.com/rohit-ningaraddi325/DEVOPS.git</url>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec>
      </branches>
    </scm>
    <scriptPath>Jenkins-MultiStage-Pipeline/Jenkinsfile</scriptPath>
    <lightweight>false</lightweight>
  </definition>
</flow-definition>
```

`lightweight` is false so the whole repository is checked out, which `dir('Jenkins-MultiStage-Pipeline')` needs.

```cmd
cd /d E:\devops
set J=http://localhost:8080
set JAUTH=admin:<api-token>
curl.exe -s -u "%JAUTH%" -X POST "%J%/createItem?name=Python-MultiStage-Pipeline" -H "Content-Type: application/xml" --data-binary @job9.xml
```

The command prints nothing when the job is created.

### Step 3: Install Python and Flask inside the Jenkins container

The Jenkins image has no Python, so the Build stage fails with `python3: not found` until it is installed. The install runs as `root` inside the container:

```cmd
docker exec -u root jenkins bash -c "apt-get update && apt-get install -y python3 python3-pip python3-venv python3-flask"
```

Verify the installation:

```cmd
docker exec jenkins python3 --version
docker exec jenkins python3 -c "import flask; print('Flask OK')"
```

Flask is installed from `apt` because current Debian-based images refuse `pip install` into the system Python. This install lives in the container's writable layer and is lost if the container is recreated. A permanent fix is to add the same `apt-get` line to `Dockerfile.jenkins` from Exercise 6 and rebuild the image.

### Step 4: Run the pipeline

```cmd
curl.exe -s -u "%JAUTH%" -X POST "%J%/job/Python-MultiStage-Pipeline/build"
timeout /t 40
curl.exe -s -u "%JAUTH%" "%J%/job/Python-MultiStage-Pipeline/lastBuild/consoleText"
```

The end of the console output shows the last stages of the successful build:

![Jenkins console output, end of the successful pipeline run](Images/pipeline-console-output.png)

What the console shows:

- **Run Application:** `nohup python3 python-app-deploy/app.py` starts the deployed app in the background, and `echo 3212` records its process ID in `app.pid`.
- **Test Application:** `python3 test_app.py` runs one test (`Ran 1 test`) and reports `OK`. The test prints `Hello, Jenkins Multi-Stage Pipeline!`, the text returned by the `/` route.
- **Post Actions:** the `post` block prints `Pipeline completed successfully!`.
- The build ends with `Finished: SUCCESS`.

## Observations

- **Test Application does not hit the running app.** `test_app.py` uses Flask's test client, which calls the app in-process, so this stage passes even if the app started in Run Application has stopped. It works as a repeat of the unit test, not as a check of the live deployment.
- **Reruns start another copy of the app.** Each build launches a new background process on port 5000. Extra copies fail with "address already in use" in `app.log`, but the pipeline still passes because the process is backgrounded.
- **Jenkins may stop background processes.** Jenkins can clean up processes started during a build when it ends, so the app is not guaranteed to still be running afterwards.
- **A separate folder needs a matching path.** The `Jenkinsfile` uses `dir('Jenkins-MultiStage-Pipeline')` and the job uses `scriptPath` `Jenkins-MultiStage-Pipeline/Jenkinsfile`. If either differs from the folder name in the repo, the build fails with a missing file error.
- **Line endings matter.** The `Jenkinsfile` and app files were saved with LF, because the shell blocks run in a Linux container.

## Result

The Jenkins pipeline `Python-MultiStage-Pipeline` (running on port 8080) pulled the `Jenkinsfile` and application from GitHub and ran the Build, Test, Deploy, Run Application, and Test Application stages successfully after Python was installed in the Jenkins container. The unit test passed, `app.py` was copied to the `python-app-deploy` directory, and the pipeline ended with `Pipeline completed successfully!` and `Finished: SUCCESS`.
