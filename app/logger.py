import sys
from pathlib import Path
from loguru import logger
from app.config import Config

# Contoh DIR, sesuaikan
DIR = Path(".")
FPATH = DIR/"logger"
log = logger.bind(dataset="logger")

log.remove()

# === File handler ===
log.add(
FPATH,
format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {name}:{function}:{line} - {message}",
rotation="5 MB",
retention=3,
level="INFO",
colorize=False,
buffering=1,
)

# === Console handler jika VERBOSE=1 ===
if Config.verbose:
  log.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
  )

