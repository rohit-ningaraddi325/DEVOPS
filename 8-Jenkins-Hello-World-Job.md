# Exercise 8: Creating a "Hello World" Jenkins Job

## Objective

Create a GitHub repository containing a simple shell script, then configure a Jenkins Freestyle job that clones the repository and runs the script. This demonstrates a basic CI flow from source control to build execution.

**Environment:** Windows 11, Command Prompt in the VS Code terminal, Docker Desktop, Jenkins running in Docker (`jenkins-docker` container from Exercise 6, port 8080).

## Approach and Windows-Specific Changes

The exercise normally uses the GitHub web UI, a personal access token and the Jenkins web UI. This run did everything from the command line.

| Original exercise | What was done instead | Why |
|---|---|---|
| Create the repo in the GitHub UI and a fine-grained token | `gh auth login` and `gh repo create ... --push` | The GitHub CLI creates the repo, adds the remote and pushes in one command. No token to copy or store. |
| `chmod +x hello-world.sh` | `git update-index --chmod=+x hello-world.sh` | `chmod` does not exist on Windows. Git can record the executable bit directly in the index. |
| Create the script in any editor | Created in VS Code with the line ending set to **LF** | Windows defaults to CRLF. A carriage return at the end of a line breaks scripts run by Linux, and Jenkins runs inside a Linux container. |
| Create the job in the Jenkins UI | `job.xml` posted to Jenkins' REST API with `curl.exe` | Same job, scriptable and repeatable. |
| Run the repo folder anywhere | Created at `E:\devops\devops-sample-code`, outside the `DEVOPS` lab repo | A Git repo inside another Git repo causes embedded-repo problems. The exercise needs a standalone repo. |

## Step 1: Create the Script

Created `hello-world.sh` in VS Code with the line ending set to LF:

```
#!/bin/bash
echo "Hello, Jenkins!"
```

## Step 2: Commit and Push with the GitHub CLI

```cmd
gh auth login
mkdir E:\devops\devops-sample-code
cd /d E:\devops\devops-sample-code
git init
git config user.name "Your Name"
git config user.email "your-email@example.com"
git add hello-world.sh
git update-index --chmod=+x hello-world.sh
git status
git commit -m "Add hello-world.sh"
git branch -M main
gh repo create devops-sample-code --public --source=. --remote=origin --push
git ls-files -s hello-world.sh
```

![Git commit, gh repo create, and executable bit check](Images/hello-world-git-push.png)

- `git status` lists `hello-world.sh` under "Changes to be committed".
- The commit output shows `create mode 100755`, so the script is marked executable.
- `gh repo create` created `rohit-ningaraddi325/devops-sample-code`, added the `origin` remote and pushed `main` in one command.
- `git ls-files -s hello-world.sh` shows mode `100755`.
- The warning "LF will be replaced by CRLF" is harmless. Git only converts line endings when checking files out to the Windows working copy. The committed file keeps LF.

## Step 3: Create the Jenkins Job through the REST API

Created an API token in Jenkins (user page, Security, Add new token), then described the job in `job.xml`:

```xml
<?xml version='1.1' encoding='UTF-8'?>
<project>
  <scm class="hudson.plugins.git.GitSCM">
    <configVersion>2</configVersion>
    <userRemoteConfigs>
      <hudson.plugins.git.UserRemoteConfig>
        <url>https://github.com/rohit-ningaraddi325/devops-sample-code.git</url>
      </hudson.plugins.git.UserRemoteConfig>
    </userRemoteConfigs>
    <branches>
      <hudson.plugins.git.BranchSpec><name>*/main</name></hudson.plugins.git.BranchSpec>
    </branches>
  </scm>
  <builders>
    <hudson.tasks.Shell><command>sh hello-world.sh</command></hudson.tasks.Shell>
  </builders>
</project>
```

The job definition sets the branch to `*/main` and the build step to `sh hello-world.sh`, the two fields that cause failures when set wrong in the UI.

Created the job, triggered a build and read its console output:

```cmd
set J=http://localhost:8080
set JAUTH=admin:<api-token>
curl.exe -s -u "%JAUTH%" -X POST "%J%/createItem?name=HelloWorld" -H "Content-Type: application/xml" --data-binary @job.xml
curl.exe -s -u "%JAUTH%" -X POST "%J%/job/HelloWorld/build"
timeout /t 15
curl.exe -s -u "%JAUTH%" "%J%/job/HelloWorld/lastBuild/consoleText"
```

`createItem` and `build` print nothing when they succeed. The console output shows Jenkins cloning the repo, checking out commit `d3c4a44`, and running the script:

![Console output of the HelloWorld build](Images/hello-world-console-output.png)

```
Checking out Revision d3c4a44386e23f9e9bbe82d419bc8d167f89254b (refs/remotes/origin/main)
Commit message: "Add hello-world.sh"
[HelloWorld] $ /bin/sh -xe /tmp/jenkins4824043014958569624.sh
+ sh hello-world.sh
Hello, Jenkins!
Finished: SUCCESS
```

## Step 4: Verify on the Jenkins Dashboard

The `HelloWorld` job appears next to the earlier `delivery-monitoring-pipeline` job, with a green status and build #1.

![Jenkins dashboard with the HelloWorld job](Images/hello-world-jenkins-dashboard.png)

## Troubleshooting Notes

**HTTP 401 Unauthorized from the REST API.** The first attempt set `JAUTH` to the token alone. curl then treated the token as a username and asked for a password. The `-u` value must be `username:token`. Setting `JAUTH=admin:<token>` fixed it.

**Branch mismatch (avoided).** The Git plugin defaults "Branches to build" to `*/master`, but this repo uses `main`. Building with the default fails with "Couldn't find any revision to build". The `job.xml` sets `*/main` from the start.

**Stray character in the shell command (avoided).** Pasting into the Execute shell field can add a trailing character, for example `sh hello-world.sh$`, which fails with "cannot open hello-world.sh$". Because the command is written in `job.xml`, there is nothing to paste.

**`gh` not recognized after install.** `winget` reported the package as already installed, but the terminal did not have it on its PATH. Fully restarting VS Code reloaded the PATH.

**Line endings.** The script is saved with LF. A CRLF file would leave a carriage return on each line and break the script under Linux.

## Key Takeaways

- The Jenkins Git plugin does not detect a repository's default branch. Set it manually when it is not `master`.
- A Freestyle job connects source control (GitHub), a trigger (a manual build) and a build step (shell execution). That is the minimal shape of a CI pipeline.
- Jenkins' REST API can create and run a job from a short XML file, so the whole exercise can be done without the web UI.
- Jenkins runs the script inside a Linux container, so line endings and the executable bit matter even when the author works on Windows.
- Use an API token with the `username:token` form for scripted access, and revoke it when finished.
