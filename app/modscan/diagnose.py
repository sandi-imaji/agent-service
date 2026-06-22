from app.schemas import (ModScanSchema, ModScanResponse, DataType,
 PointType, Data, Status, FullDiagnosticSchema, DiagnosticSchema, Layer, NetworkSchema)
from app.modscan._modscan import ModScan,ModWrite, ModScanSecondary
from typing import Optional,Union
from app.utils import ping_icmp,telnet,get_current_value_sl
from app.logger import log
from app.config import Config
from typing import Tuple
from app.utils import get_tagname
import datetime,asyncio,requests as req,time

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
  
  if abs(currValue - value) <= 0.1:
    status = Status.OK
    detail  = f"Match SL and ModScan Values are both {value}"
  else:
    status = Status.FAIL
    detail = f"Mismatch: Expected SL [{value}] but got ModScan [{currValue}]"
  return DiagnosticSchema(timestamp=timestamp,layer=Layer.SMARTLINK,status=status,detail=detail)

async def full_diagnostic_async(payload: ModScanSchema) -> FullDiagnosticSchema:
  """
  Full diagnostic: Network check + Modbus register read with value mismatch failover.
  Flow:
    1. Ping check (with redundancy)
    2. Telnet check (with redundancy)
    3. ModScan register read from PRIMARY
    4. Compare with SL value:
       - If match: OK, use PRIMARY
       - If mismatch: Try SECONDARY
         a. Check network for SECONDARY (ping + telnet)
         b. Read from SECONDARY
         c. Compare with SL value
         d. Track mismatch from PRIMARY in logs and report
    5. Track which connection is used (primary/secondary)
  Returns: FullDiagnosticSchema with all results and connection info
  """
  start_time = time.time()
  timestamp = datetime.datetime.now()
  
  log.info("=" * 50)
  log.info("FULL DIAGNOSTIC START")
  log.info("=" * 50)
  
  # Track which connection is active
  active_connection = "PRIMARY"
  primary_mismatch_detail = None
  secondary_network_ok = True
  
  # ==================== NETWORK DIAGNOSTIC (PRIMARY) ====================
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
      detail="Network diagnostic failed",
      active_connection="NONE"
    )
  
  # ==================== MODBUS REGISTER CHECK (PRIMARY) ====================
  log.info(f"[REGISTER] Reading address {payload.address} from PRIMARY with {payload.data_type}")
  modscan_response: ModScanResponse = await ModScan(payload)
  
  if not modscan_response.data:
    log.error(f"[REGISTER] Failed to read from PRIMARY: {modscan_response.detail}")
    # Create empty Data for register when read fails
    register_data = Data(bits=[], reg_hex=[], value=None)
    elapsed = time.time() - start_time
    return FullDiagnosticSchema(
      timestamp=timestamp,
      times=round(elapsed, 3),
      ping=ping_report,
      telnet=telnet_report,
      register_data=register_data,
      status=Status.FAIL,
      detail=f"Register read failed: {modscan_response.detail}",
      active_connection="NONE"
    )
  
  log.info(f"[REGISTER] PRIMARY read success! Value = {modscan_response.data.value}")
  register_data = modscan_response.data
  
  # ==================== VALUE COMPARISON (PRIMARY vs SL) ====================
  currValue = modscan_response.data.value
  sm_layer = checking_value_sl(tagname=payload.tagname, currValue=currValue)
  
  if sm_layer.status == Status.OK:
    # Primary value matches SL - all good!
    log.info(f"[VALUE-CHECK] PRIMARY value matches SL: {currValue}")
    overall_status = Status.OK
    overall_detail = f"All checks passed - Using PRIMARY connection"
    
  else:
    # PRIMARY MISMATCH - Try failover to SECONDARY
    log.warning(f"[VALUE-CHECK] PRIMARY mismatch detected!")
    log.warning(f"[VALUE-CHECK] PRIMARY detail: {sm_layer.detail}")
    primary_mismatch_detail = sm_layer.detail
    
    # ==================== NETWORK CHECK (SECONDARY) ====================
    log.info(f"[NETWORK-SECONDARY] Checking secondary network...")
    log.info(f"[PING-SECONDARY] Checking secondary: {payload.network.secondary_host}")
    ping_ok_secondary = ping_icmp(host=payload.network.secondary_host, count=5)
    
    if not ping_ok_secondary:
      log.error(f"[PING-SECONDARY] Secondary {payload.network.secondary_host} is TIMEOUT!")
      secondary_network_ok = False
      overall_status = Status.FAIL
      overall_detail = f"PRIMARY value mismatch and SECONDARY network unreachable. {primary_mismatch_detail}"
      
    else:
      log.info(f"[PING-SECONDARY] Secondary {payload.network.secondary_host} is OK!")
      
      # Check Telnet for secondary
      log.info(f"[TELNET-SECONDARY] Checking {payload.network.secondary_host}:{payload.network.secondary_port}")
      telnet_ok_secondary = telnet(host=payload.network.secondary_host, port=payload.network.secondary_port)
      
      if not telnet_ok_secondary:
        log.error(f"[TELNET-SECONDARY] Secondary {payload.network.secondary_host}:{payload.network.secondary_port} is CLOSED!")
        secondary_network_ok = False
        overall_status = Status.FAIL
        overall_detail = f"PRIMARY value mismatch and SECONDARY telnet failed. {primary_mismatch_detail}"
        
      else:
        log.info(f"[TELNET-SECONDARY] Secondary {payload.network.secondary_host}:{payload.network.secondary_port} is OPEN!")
        
        # ==================== MODBUS REGISTER CHECK (SECONDARY) ====================
        log.info(f"[REGISTER-SECONDARY] Trying to read from SECONDARY...")
        secondary_response: ModScanResponse = await ModScanSecondary(payload)
        
        if not secondary_response.data:
          log.error(f"[REGISTER-SECONDARY] Failed to read from SECONDARY: {secondary_response.detail}")
          secondary_network_ok = False
          overall_status = Status.FAIL
          overall_detail = f"PRIMARY value mismatch and SECONDARY read failed. {primary_mismatch_detail}"
          
        else:
          log.info(f"[REGISTER-SECONDARY] SECONDARY read success! Value = {secondary_response.data.value}")
          
          # ==================== VALUE COMPARISON (SECONDARY vs SL) ====================
          secondary_value = secondary_response.data.value
          sm_layer_secondary = checking_value_sl(tagname=payload.tagname, currValue=secondary_value)
          
          # Update active connection
          active_connection = "SECONDARY"
          register_data = secondary_response.data
          modscan_response = secondary_response
          
          if sm_layer_secondary.status == Status.OK:
            # Secondary value matches SL - failover successful!
            log.info(f"[VALUE-CHECK] SECONDARY value matches SL: {secondary_value}")
            overall_status = Status.OK
            overall_detail = f"Failover successful - PRIMARY had mismatch ({primary_mismatch_detail}), SECONDARY value matches SL"
            sm_layer = sm_layer_secondary  # Update SL layer to secondary result
          else:
            # Both PRIMARY and SECONDARY mismatch
            log.error(f"[VALUE-CHECK] SECONDARY also mismatch!")
            log.error(f"[VALUE-CHECK] SECONDARY detail: {sm_layer_secondary.detail}")
            overall_status = Status.FAIL
            overall_detail = f"Both connections mismatch. PRIMARY: {primary_mismatch_detail}. SECONDARY: {sm_layer_secondary.detail}"
            sm_layer = sm_layer_secondary  # Keep the secondary mismatch for reporting
  
  elapsed = time.time() - start_time
  log.info("=" * 50)
  log.info(f"FULL DIAGNOSTIC COMPLETE - {elapsed:.3f}s")
  log.info(f"Active connection: {active_connection}")
  log.info("=" * 50)
  
  return FullDiagnosticSchema(
    timestamp=timestamp,
    times=round(elapsed, 3),
    ping=ping_report,
    telnet=telnet_report,
    smartlink=sm_layer,
    register_data=register_data,
    modscan_data=modscan_response.request,
    status=overall_status,
    detail=overall_detail,
    active_connection=active_connection,
    primary_mismatch_detail=primary_mismatch_detail
  )

def full_diagnostic(payload: ModScanSchema):
  """Sync wrapper for full_diagnostic_async"""
  report = asyncio.run(full_diagnostic_async(payload))
  generated = analysis_point(report.to_md_compact())
  return report.to_md_optimize(generated)

def full_diagnostic_async_point(tagname:str):
  payload = get_tagname(tagname)
  payload = ModScanSchema.from_sl(payload)
  return asyncio.run(full_diagnostic_async(payload))

if __name__ == "__main__":
  from app.llm.llm_client import analysis_point
  examples = "CRAH-2DH2.1-RETURN_AIR_TEMP"
  out = full_diagnostic_async_point(examples)
  generated = analysis_point(out.to_md_compact())
  out = out.to_md_optimize(generated)
  print(out)
  with open("out.md","w") as f:
    f.write(out)
