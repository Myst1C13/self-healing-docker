import os
import time
import random 
import threading 
import psutil
from fastapi import FastAPI

app = FastAPI()

SERVICE_NAME = os.getenv("SERVICE NAME", "unknown-service")

_chaos_active = False
_chaos_lock = threading.Lock()  