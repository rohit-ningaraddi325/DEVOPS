import os
from flask import Flask, jsonify, request

app = Flask(__name__)

INPUT_DIR = os.environ.get("INPUT_DIR", "/data/input")
REDIS_HOST = os.environ.get("REDIS_HOST")


def count_in_redis():
    """Increment a counter in the supporting Redis service, if configured."""
    if not REDIS_HOST:
        return None
    try:
        import redis
        r = redis.Redis(host=REDIS_HOST, port=6379, socket_connect_timeout=2)
        return int(r.incr("files_processed"))
    except Exception as e:
        return "unavailable (" + e.__class__.__name__ + ")"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/wordcount")
def wordcount():
    name = os.path.basename(request.args.get("file", "sample.txt"))
    path = os.path.join(INPUT_DIR, name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        app.logger.error("File not found: %s", path)
        return jsonify(error="file not found", path=path), 404
    except PermissionError:
        app.logger.error("Permission denied: %s", path)
        return jsonify(error="permission denied", path=path), 403
    result = {"file": name, "words": len(text.split())}
    counter = count_in_redis()
    if counter is not None:
        result["files_processed"] = counter
    return jsonify(result)


@app.get("/selftest")
def selftest():
    def attempt(label, fn):
        try:
            fn()
            return {"operation": label, "allowed": True}
        except Exception as e:
            return {"operation": label, "allowed": False,
                    "error": e.__class__.__name__ + ": " + str(e)}

    def read_input():
        with open(os.path.join(INPUT_DIR, "sample.txt")) as f:
            f.read()

    def read_passwd():
        with open("/etc/passwd") as f:
            f.read()

    def write_input():
        with open(os.path.join(INPUT_DIR, "tamper.txt"), "w") as f:
            f.write("x")

    return jsonify([
        attempt("read sample.txt from input dir", read_input),
        attempt("read /etc/passwd", read_passwd),
        attempt("write into input dir", write_input),
    ])