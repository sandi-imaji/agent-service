from app.schemas import DataType,PointType
from typing import List,Union,Optional,Any
from app.config import Config
import pymodbus.client as modbusClient,struct,subprocess,platform,socket,requests as req
from app.logger import log

def bytes_to_value(data:bytes,dtype:DataType) -> Any:
  fmt = f"={dtype.fmt}"
  return struct.unpack(fmt,data)[0]

def registers_to_bytes(regs:List[int],dtype:DataType,is_big_endian:bool=True) -> bytes:
  byte_ord = "big" if is_big_endian else "little"
  return b''.join(r.to_bytes(2, byteorder=byte_ord, signed=dtype.is_signed()) for r in regs)

def registers_to_hex(registers:List[int]): return [f"{r:04x}" for r in registers]

def registers_hex_to_bytes(regs: List[str], strict: bool = True,is_big_end:bool=True) -> bytes:
  """
  Convert hex registers (16-bit) to raw bytes.
  - regs        : ['0011', 'A0FF', ...]
  - strict     : validate hex & length

  Return: raw bytes (no endian interpretation)
  """
  out = bytearray()

  for r in regs:
    if strict:
      if len(r) != 4: raise ValueError(f"Invalid register length: {r}")
      int(r, 16)  # validate hex
    hi = int(r[0:2], 16)
    lo = int(r[2:4], 16)
    if is_big_end:
      out.append(hi & 0xFF)
      out.append(lo & 0xFF)
    else:
      out.append(lo & 0xFF)
      out.append(hi & 0xFF)
  return bytes(out)

def ping_icmp(host, count=4) -> Optional[str]:
  param = '-n' if platform.system().lower() == 'windows' else '-c'
  command = ['ping', param, str(count), host]
  log.info(f"PING (ICMP): {host} | count : {count}")
  
  try:
    output = subprocess.check_output(command, universal_newlines=True)
    lines = output.splitlines()
    
    # Cari baris yang berisi statistik (biasanya ada kata "packet" atau "packets")
    for line in lines:
      if "packet" in line.lower() and "loss" in line.lower():
        summary_line = line.strip()
        log.info(summary_line)
        return summary_line
    msg = "summary packet loss tidak ditemukan di output ping."
    log.warning(msg)
    return msg
  except subprocess.CalledProcessError as e:
    msg = f"Ping gagal ke {host}"
    log.error(msg)
    return msg

def telnet(host, port, timeout=2) -> bool:
  """
  Memeriksa apakah port tertentu terbuka pada host/IP.
  
  Args:
    host (str): IP address atau hostname
    port (int): Nomor port (1-65535)
    timeout (int): Waktu timeout dalam detik (default 2)
  
  Returns: bool: True jika port terbuka, False jika tertutup/timeout
  """
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    result = s.connect_ex((host, port))  # 0 = terbuka
    s.close()
    return result == 0
  except: return False

def get_tagname(tagname,key:Optional[str] = None) -> dict:
  endpoint =  f"application/api/modbus/get-point?tagname={tagname}"
  url = f"{Config.sl_host}{endpoint}"
  if not key: key = Config.sl_key
  try:
    res = req.post(url,data={"key":key},verify=False)
    if res.status_code == 200: res = res.json()
    if "data" not in res.keys():
      log.error(f"Message from get tagname {tagname}: {res.get('message','')}")
      return {}
    return res.get('data',{})
  except req.exceptions.ConnectTimeout:
    raise ValueError("")

def get_current_value_sl(tagname:str,key:Optional[str]=None) -> Union[int,float]:
  data = get_tagname(tagname)
  if not data:
    log.error("Tagname is not found!")
    return None
  currValue = float(data["currvalue"])
  if currValue.is_integer(): currValue = int(currValue)
  return currValue



def get_func_read(client:modbusClient.AsyncModbusTcpClient,ptype:PointType):
  match ptype:
    case PointType.COIL_STATUS: return client.read_coils
    case PointType.INPUT_STATUS: return client.read_discrete_inputs
    case PointType.HOLDING_REGISTER: return client.read_holding_registers
    case PointType.INPUT_REGISTER: return client.read_input_registers

def get_func_write(client:modbusClient.AsyncModbusTcpClient,ptype:PointType,dtype:DataType):
  if ptype == PointType.COIL_STATUS: return client.write_coil
  else:
    if dtype.offset > 1: return client.write_registers
    else: return client.write_register
  
def swap_bytes(hexs:List[str]) -> List[str]:
  swapped = []
  for reg in hexs:
    reg = reg.zfill(4)  # pastikan 4 digit
    swapped.append(reg[2:4] + reg[0:2])
  return swapped

def hex_registers_to_bits(reg_hex:List[str]):
  bit_list = []
  for reg in reg_hex:
    reg_clean = reg.replace(" ","").zfill(4).upper()
    bits = bin(int(reg_clean,16))[2:].zfill(16)
    bit_list.append(bits)
  return bit_list


if __name__ == "__main__":
  tagname = "CRAH-2DH2.1-RETURN_AIR_TEMP"
  print(get_tagname(tagname))

