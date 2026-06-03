import os

import uvicorn


HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8787"))


if __name__ == "__main__":
    print(f"Rasputin: http://{HOST}:{PORT}")
    uvicorn.run("backend.main:app", host=HOST, port=PORT, log_level=os.environ.get("LOG_LEVEL", "info"))
