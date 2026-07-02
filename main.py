import os

import uvicorn


def main():
    reload = os.getenv("UVICORN_RELOAD", "true").lower() == "true"
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)


if __name__ == "__main__":
    main()
