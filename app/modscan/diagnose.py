from app.schemas import (ModScanSchema, ModScanResponse, DataType,
 PointType, Data, Status, FullDiagnosticSchema, DiagnosticSchema, Layer, NetworkSchema)
from app.modscan._modscan import ModScan,ModWrite
from typing import Optional,Union
from app.utils import ping_icmp,telnet,get_current_value_sl
from app.logger import log
from app.config import Config
from typing import Tuple
from app.utils import get_tagname
import datetime,asyncio,requests as req

def diagnostic_network(network:NetworkSchema) -> Tuple[DiagnosticSchema,DiagnosticSchema]:
  """
  Diagnostic network: Check PING then TELNET
  Flow:
    1. Ping primary -> if fail, try secondary
    2. Telnet to the host that passed ping -> if fail, try the other
  Returns: (ping_report, telnet_report)
  """
  log.info("Diagnostic Network ...")
  timestamp = datetime.datetime.now()
  
  # Track which host/port is active (passed checks)
  active_host = network.primary_host
  active_port = network.primary_port
  use_secondary = False
  
  # ==================== PING CHECK ====================
  log.info(f"[PING] Checking primary: {network.primary_host}")
  ping_ok = ping_icmp(host=network.primary_host, count=5)
  
  if not ping_ok:
    log.error(f"[PING] Primary {network.primary_host} is TIMEOUT!")
    log.info(f"[PING] Trying secondary: {network.secondary_host}")
    ping_ok = ping_icmp(host=network.secondary_host, count=5)
    
    if not ping_ok:
      log.error(f"[PING] Secondary {network.secondary_host} is TIMEOUT!")
      msg = f"PING failed: Primary [{network.primary_host}] & Secondary [{network.secondary_host}] both TIMEOUT"
      ping_report = DiagnosticSchema(layer=Layer.PING, status=Status.TIMEOUT, detail=msg, timestamp=timestamp)
      telnet_report = DiagnosticSchema(layer=Layer.TELNET, status=Status.TIMEOUT, detail="Skipped - IP unreachable", timestamp=timestamp)
      return ping_report, telnet_report
    
    # Secondary ping success
    active_host = network.secondary_host
    active_port = network.secondary_port
    use_secondary = True
    log.info(f"[PING] Secondary {network.secondary_host} is OK!")
  else:
    log.info(f"[PING] Primary {network.primary_host} is OK!")
  
  ping_report = DiagnosticSchema(layer=Layer.PING, status=Status.OK, detail=f"Success - {active_host}", timestamp=timestamp)
  
  # ==================== TELNET CHECK ====================
  log.info(f"[TELNET] Checking {active_host}:{active_port}")
  telnet_ok = telnet(host=active_host, port=active_port)
  
  if not telnet_ok:
    log.error(f"[TELNET] {active_host}:{active_port} is CLOSED!")
    
    # Try the other host
    fallback_host = network.secondary_host if not use_secondary else network.primary_host
    fallback_port = network.secondary_port if not use_secondary else network.primary_port
    
    log.info(f"[TELNET] Trying fallback: {fallback_host}:{fallback_port}")
    telnet_ok = telnet(host=fallback_host, port=fallback_port)
    
    if not telnet_ok:
      log.error(f"[TELNET] Fallback {fallback_host}:{fallback_port} is also CLOSED!")
      msg = f"TELNET failed: {active_host}:{active_port} & {fallback_host}:{fallback_port} both CLOSED"
      telnet_report = DiagnosticSchema(layer=Layer.TELNET, status=Status.TIMEOUT, detail=msg, timestamp=timestamp)
      return ping_report, telnet_report
    
    # Fallback telnet success
    active_host = fallback_host
    active_port = fallback_port
    log.info(f"[TELNET] Fallback {fallback_host}:{fallback_port} is OPEN!")
  else:
    log.info(f"[TELNET] {active_host}:{active_port} is OPEN!")
  
  telnet_report = DiagnosticSchema(layer=Layer.TELNET, status=Status.OK, detail=f"Success - {active_host}:{active_port}", timestamp=timestamp)
  return ping_report, telnet_report

def checking_value_sl(tagname:str,currValue:Optional[Union[float,int]]) -> DiagnosticSchema:
  timestamp = datetime.datetime.now()
  log.info("CHECKING VALUE FROM SL:")
  value = get_current_value_sl(tagname)
  if currValue is None:
    status = Status.COMLOSS
    detail = "Tagname is not found | API GET Tagname is Error"
  
  if abs(currValue - value) <= 0.5:
    status = Status.OK
    detail  = f"Match SL and ModScan Values are both {value}"
  else:
    status = Status.FAIL
    detail = f"Mismatch: Expected SL [{value}] but got ModScan [{currValue}]"
  return DiagnosticSchema(timestamp=timestamp,layer=Layer.SMARTLINK,status=status,detail=detail)

async def full_diagnostic_async(payload: ModScanSchema) -> FullDiagnosticSchema:
  """
  Full diagnostic: Network check + Modbus register read
  Flow:
    1. Ping check (with redundancy)
    2. Telnet check (with redundancy)
    3. ModScan register read (with redundancy)
  Returns: FullDiagnosticSchema with all results
  """
  import time
  start_time = time.time()
  timestamp = datetime.datetime.now()
  
  log.info("=" * 50)
  log.info("FULL DIAGNOSTIC START")
  log.info("=" * 50)
  
  # ==================== NETWORK DIAGNOSTIC ====================
  ping_report, telnet_report = diagnostic_network(payload.network)
  
  # If network failed, skip ModScan
  if telnet_report.status != Status.OK:
    log.error("[REGISTER] Skipped - Network unreachable")
    # Create empty Data for register when network fails
    register_data = Data(bits=[], reg_hex=[], value=None)
    elapsed = time.time() - start_time
    return FullDiagnosticSchema(
      timestamp=timestamp,
      times=round(elapsed, 3),
      ping=ping_report,
      telnet=telnet_report,
      register_data=register_data,
      status=Status.FAIL,
      detail="Network diagnostic failed"
    )
  # ==================== MODBUS REGISTER CHECK ====================
  log.info(f"[REGISTER] Reading address {payload.address} with {payload.data_type}")
  modscan_response: ModScanResponse = await ModScan(payload)
  
  if modscan_response.data:
    log.info(f"[REGISTER] Success! Value = {modscan_response.data.value}")
    register_data = modscan_response.data
    overall_status = Status.OK
    overall_detail = "All checks passed"
  else:
    log.error(f"[REGISTER] Failed: {modscan_response.detail}")
    # Create empty Data for register when read fails
    register_data = Data(bits=[], reg_hex=[], value=None)
    overall_status = Status.FAIL
    overall_detail = f"Register read failed: {modscan_response.detail}"

  currValue = modscan_response.data.value if modscan_response.data else None
  sm_layer =  checking_value_sl(tagname=payload.tagname,currValue=currValue)
  if sm_layer.status != Status.OK:
    overall_status = Status.FAIL
    overall_detail = "Mismatch Value from Smartlink and from ModScan!"
  elapsed = time.time() - start_time
  log.info("=" * 50)
  log.info(f"FULL DIAGNOSTIC COMPLETE - {elapsed:.3f}s")
  log.info("=" * 50)
  
  return FullDiagnosticSchema(
    timestamp=timestamp,
    times=round(elapsed, 3),
    ping=ping_report,
    telnet=telnet_report,
    smartlink=sm_layer,
    register_data=register_data,
    modscan_data = modscan_response.request,
    status=overall_status,
    detail=overall_detail
  )

def full_diagnostic(payload: ModScanSchema) -> FullDiagnosticSchema:
  """Sync wrapper for full_diagnostic_async"""
  import asyncio
  return asyncio.run(full_diagnostic_async(payload))

def full_diagnostic_async_point(tagname:str):
  payload = get_tagname(tagname)
  # if tagname == "JK5-AHU-1-D-Z01-ACTUAL_FAN_SPEED":
  #   net:NetworkSchema= NetworkSchema(
  #     primary_host = "127.0.0.1",
  #     primary_port = 5020,
  #     secondary_host = "127.0.0.1",
  #     secondary_port = 5020,
  #     timeout = 0.1,
  #     retries = 1,
  #   )
  #   payload:ModScanSchema = ModScanSchema(
  #     network=net,
  #     tagname=tagname,
  #     address=1,
  #     data_type=DataType.INT16,
  #     point_type=PointType.INPUT_REGISTER,
  #     is_big_endian=True,
  #     swapped=False,
  #   )
  # else:
  #   net:NetworkSchema= NetworkSchema(
  #     primary_host = "128.0.0.10",
  #     primary_port = 5020,
  #     secondary_host = "128.0.0.10",
  #     secondary_port = 5010,
  #     timeout = 0.1,
  #     retries = 1,
  #   )
  #   payload:ModScanSchema = ModScanSchema(
  #     network=net,
  #     tagname="test",
  #     address=1,
  #     data_type=DataType.INT16,
  #     point_type=PointType.INPUT_REGISTER,
  #     is_big_endian=True,
  #     bit_position=14,
  #     precision_value=3,
  #     swapped=False,
  #   )
  return asyncio.run(full_diagnostic_async(payload))


if __name__ == "__main__":
  import pprint
  examples = "JK5-AHU-1-D-Z01-ACTUAL_FAN_SPEED"
  print(checking_value_sl("E2-TH-U2-MDF-B-01-TEMP",10))
  # pprint.pprint(full_diagnostic_async_point(examples).to_md())
