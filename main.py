import uvicorn
from app import settings

def main():
    reload = settings.uvicorn_reload
    port = settings.backend_port

    print(f"[ info ] [ Python:main ] APPLICATION RUNING ON PORT : {port} \n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    main()
