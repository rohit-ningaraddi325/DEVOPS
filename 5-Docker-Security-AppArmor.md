# Exercise 5: Docker Security with AppArmor and Python

## Overview

This exercise demonstrates container security using Docker, Python, Flask, and AppArmor. A custom AppArmor profile is applied to a Docker container to restrict filesystem access, network operations, and Linux capabilities while allowing the Flask application to run.

**Environment:** Linux machine with Docker and AppArmor enabled. AppArmor is a Linux kernel security module, so this exercise cannot run on Docker Desktop for Windows or macOS.

## Technologies Used

- Python
- Flask
- Docker
- AppArmor
- Docker Python SDK

## Project Structure

```text
Ex5/
├── app.py
├── Dockerfile
├── my-apparmor-profile
├── apply_armour.py
└── test_restricted_actions.py
```

- `app.py`: the Flask application served on port 5000.
- `Dockerfile`: builds the `flask-apparmor` image.
- `my-apparmor-profile`: the custom AppArmor profile.
- `apply_armour.py`: starts the container with the profile applied, using the Docker Python SDK.
- `test_restricted_actions.py`: attempts restricted actions and prints the result of each.

## Prerequisites

- Linux system with Docker installed
- AppArmor enabled on the host
- Python 3 and pip

Verify the installation:

```bash
docker --version
sudo aa-status
```

## Setup and Installation

### 1. Build the Docker Image

Navigate to the project directory and build the image:

```bash
docker build -t flask-apparmor .
```

### 2. Load the AppArmor Profile

Copy the custom profile into the AppArmor configuration directory and load it:

```bash
sudo cp my-apparmor-profile /etc/apparmor.d/my-apparmor-profile
sudo apparmor_parser -r /etc/apparmor.d/my-apparmor-profile
```

Verify that the profile is loaded:

```bash
sudo aa-status
```

The `-r` flag replaces an already loaded profile, so the same command is used to reload the profile after every edit.

### 3. Install Python Dependencies

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Docker Python SDK:

```bash
python -m pip install docker
```

### 4. Run the Container Directly

Start the container with the profile applied and test it:

```bash
docker run --rm \
  --name flask-secure \
  --security-opt="apparmor=my-apparmor-profile" \
  -p 5000:5000 \
  flask-apparmor
```

In a second terminal:

```bash
curl http://localhost:5000
```

![Profile loaded, container started with the AppArmor profile, and the Flask response](Images/apparmor-profile-container-run.png)

The screenshot shows the sequence in the left terminal: the profile was edited with `sudo nano /etc/apparmor.d/my-apparmor-profile`, reloaded with `sudo apparmor_parser -r`, and the container was started with `--security-opt="apparmor=my-apparmor-profile"`. Flask starts on `0.0.0.0:5000`, and the right terminal's `curl http://localhost:5000` returns the greeting from the Flask application. The Flask log records the request as `GET / HTTP/1.1 200`.

The kernel messages at the top of the left terminal are earlier AppArmor audit entries: `apparmor="DENIED" operation="create" class="net"` for `profile="my-apparmor-profile"` and `comm="python"`, with `family="inet"` and `sock_type="dgram"`. They show the profile denying a UDP socket creation by the Python process before the profile was edited. This is the log that guides which permission has to be adjusted.

### 5. Run the Container with the Python Script

Stop the container started directly, then start it through the Docker SDK script:

```bash
sudo docker stop flask-secure
python apply_armour.py
```

![Container started by apply_armour.py with the AppArmor profile applied](Images/apparmor-apply-armour.png)

The script starts the container and prints its ID (`8a521972f064`) and the security option it applied: `AppArmor profile applied: ['apparmor=my-apparmor-profile']`.

## Verify AppArmor Protection

List running containers:

```bash
docker ps
```

Inspect the container's security options:

```bash
docker inspect <container-id> --format '{{.HostConfig.SecurityOpt}}'
```

Expected output:

```text
[apparmor=my-apparmor-profile]
```

Verify the active AppArmor profile inside the container:

```bash
docker exec <container-id> cat /proc/self/attr/current
```

The output should identify `my-apparmor-profile`.

### Test the Restricted Actions

`test_restricted_actions.py` runs commands inside the confined container and reports the exit code and output of each:

```bash
python test_restricted_actions.py
```

![Result of the restricted action tests](Images/apparmor-restricted-actions-test.png)

| Action | Exit code | Output | Result |
|---|---|---|---|
| Read `/etc/passwd` | 1 | `cat: /etc/passwd: Permission denied` | Blocked by AppArmor |
| Execute `/bin/bash` | 0 | (none) | Allowed |

Reading `/etc/passwd` is blocked, which confirms that the profile's restriction on `/etc/` is enforced inside the container. Executing `/bin/bash` returned exit code 0, so this test did not block it.

## Security Features

The custom AppArmor profile demonstrates the following restrictions:

- Restricts read access to files under `/etc/`.
- Restricts read and write access under `/var/`.
- Restricts selected operations on executables under `/bin/` and `/usr/bin/`.
- Denies the `CAP_SYS_ADMIN` Linux capability.
- Allows access to the Python runtime and required libraries.
- Permits the network operations needed by the Flask application.
- Allows Docker lifecycle signals required to stop the confined container.

The profile follows the principle of restricting unnecessary access while allowing the application to function.

## Observations

- **The profile is enforced inside the container.** The read of `/etc/passwd` fails with `Permission denied`, even though the process runs normally, because the kernel checks every file access against the profile.
- **The audit log drives profile changes.** The `apparmor="DENIED"` kernel messages show exactly which operation was blocked (`create` on a network socket), which profile blocked it and which process attempted it. The profile was edited from this information and reloaded.
- **Not every test action was blocked.** Executing `/bin/bash` returned exit code 0. The profile restricts only selected operations on executables, and this one was permitted. If a task requires shell execution to be denied, the profile would need an explicit rule for it.
- **Least privilege has a cost.** A profile that is too strict stops the application itself, as the denied network operation showed, so rules are added only for what the application needs.

## Troubleshooting

### Port 5000 Is Already in Use

Stop the existing container before starting another:

```bash
docker ps
sudo docker stop <container-id-or-name>
```

This was needed before running `apply_armour.py`, because the container started with `docker run` was still using port 5000.

### AppArmor Permission Denied

Inspect kernel logs for denied operations:

```bash
sudo journalctl -k --since "15 minutes ago" --no-pager \
  | grep 'apparmor="DENIED"'
```

Update the profile with only the permissions required, reload it, and restart the container.

### Reload the Profile

```bash
sudo apparmor_parser -r /etc/apparmor.d/my-apparmor-profile
```

## Conclusion

This exercise shows how AppArmor can provide an additional security layer for Docker containers. A custom profile applied through `--security-opt` and through the Docker Python SDK controls access to selected filesystem paths, network operations, and Linux capabilities without disabling container functionality. The test confirmed that reading `/etc/passwd` is denied inside the confined container, and the audit log showed how denied operations are traced and fixed.
