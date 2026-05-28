from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

DIR_APP = Path(__file__).parent
DIR = DIR_APP.parent

if not os.path.exists(DIR.parent/".env"): raise FileExistsError("env is not Exists!")
load_dotenv(DIR.parent/".env")

@dataclass
class Config:
  dir = DIR
  dir_app = DIR_APP
  tagname_path = dir/"storages/tagname.csv"
  encrypt:bool = bool(os.environ.get("ENCRYPT",""))
  host:str = os.environ.get("HOST_AGENT","127.0.0.1")
  port:int = int(os.environ.get("PORT_AGENT",8001))
  debug = bool(os.environ.get("DEBUG",False))
  verbose = bool(os.environ.get("VERBOSE",False))
  sl_host = os.environ.get("SL_HOST","")
  # url_get_tagname = "https://sl-v1.imaji.io/application/api/modbus/get-point"
  # key_get_tagname = "593a0df14582c6223361c39be336e3d8"
  sl_token = os.environ.get("SL_TOKEN","")
  sl_key = os.environ.get("SL_KEY","")
  n_cpu = int(os.environ.get("N_CPU",-1))

if __name__ == "__main__": print(Config.debug)
