from app.schemas import (ModScanSchema,ModScanResponse,ModWriteRequest,ModWriteResponse,
PointType,DataType,ExceptionCodes,Data)
from app.config import Config
from app.utils import (get_func_read,get_func_write,swap_bytes,hex_registers_to_bits)
import pymodbus.client as modbusClient,struct
from pymodbus.pdu import ExceptionResponse,ModbusPDU
from pymodbus import exceptions
from app.logger import log
from typing import Union

async def _modscan_connect(host: str, port: int, payload: ModScanSchema):
  """
  Internal function: Connect and read Modbus register from specific host:port
  Returns: (success: bool, response: ModScanResponse)
  """
  async with modbusClient.AsyncModbusTcpClient(
    host=host,
    port=port,
    framer="socket",
    timeout=payload.network.timeout,
    retries=payload.network.retries,
    reconnect_delay=0.5
  ) as client:
    try:
      log.info(f"[MODSCAN] Connecting to {host}:{port}")
      await client.connect()
      
      if not client.connected:
        log.error(f"[MODSCAN] Failed to connect to {host}:{port}")
        client.close()
        return False, ModScanResponse(detail=f"Connection failed to {host}:{port}", request=payload)
      
      log.info(f"[MODSCAN] Connected to {host}:{port}")
      func = get_func_read(client, payload.point_type)
      response = await func(address=payload.address-1, count=payload.data_type.offset, device_id=payload.device_id)
      
      if isinstance(response, ExceptionResponse):
        detail = ExceptionCodes(response.exception_code)
        log.critical(f"[MODSCAN] Exception: {detail.name}")
        return False, ModScanResponse(detail=detail.name, request=payload)
      
      if not isinstance(response, ModbusPDU): raise TypeError(f"response is {type(response)}")
      
      # Process response based on point type
      if payload.point_type in (PointType.COIL_STATUS, PointType.INPUT_STATUS):
        log.info("[MODSCAN] Reading Coil/Input Status...")
        if payload.data_type != DataType.BIN:
          raise ValueError(f"Point Type: {payload.point_type}, but data_type is {payload.data_type}")
        bits = list(reversed(response.bits))
        bits = ["".join("1" if b else "0" for b in bits)]
        value = int(any(response.bits))
        reg_hex = [f"{value:02d}"]
        data = Data(bits=bits, reg_hex=reg_hex, value=value)
      else:
        if not response.registers:
          raise ValueError("Register is not found!")
        registers = response.registers
        reg_hex = [f"{r:04x}" for r in registers]
        bits = hex_registers_to_bits(reg_hex)
        # FIXME: Dibalik
        if not payload.is_big_endian:
          reg_hex = swap_bytes(reg_hex)
        if payload.swapped and payload.data_type.offset > 1:
          reg_hex = list(reversed(reg_hex))
        hexs = "".join(reg_hex)
        reg_bytes = bytes.fromhex(hexs)
        if payload.data_type == DataType.BIN:
          bit_position = int(payload.bit_position) if payload.bit_position else 1
          value = int(bits[0][bit_position-1])
        else:
          value = struct.unpack(f"@{payload.data_type.fmt}", reg_bytes)[0]
        if payload.factor_value:
          value *= payload.factor_value
        if payload.offset_value:
          value += payload.offset_value
        if payload.precision_value:
          value = round(value, payload.precision_value)
        data = Data(bits=bits, reg_hex=reg_hex, value=value)
      
      return True, ModScanResponse(request=payload, data=data, detail=f"Success from {host}:{port}")
      
    except exceptions.ConnectionException as e:
      log.critical(f"[MODSCAN] ConnectionException: {e}")
      return False, ModScanResponse(request=payload, detail=str(e))
    except exceptions.ModbusIOException as e:
      log.critical(f"[MODSCAN] ModbusIOException: {e}")
      return False, ModScanResponse(request=payload, detail=str(e))
    except Exception as e:
      log.critical(f"[MODSCAN] Exception: {e}")
      return False, ModScanResponse(request=payload, detail=str(e))
    finally:
      if client.connected: client.close()


async def ModScan(payload: ModScanSchema) -> ModScanResponse:
  """
  Read Modbus register with redundancy.
  Flow:
    1. Try primary host:port
    2. If primary fails, try secondary host:port
    3. Return response with active connection info
  """
  network = payload.network
  
  # Try primary connection
  log.info(f"[MODSCAN] Trying PRIMARY: {network.primary_host}:{network.primary_port}")
  success, response = await _modscan_connect(
    host=network.primary_host,
    port=network.primary_port,
    payload=payload
  )
  
  if success:
    log.info(f"[MODSCAN] PRIMARY connection successful")
    return response
  # Primary failed, try secondary
  log.warning(f"[MODSCAN] PRIMARY failed, trying SECONDARY: {network.secondary_host}:{network.secondary_port}")
  success, response = await _modscan_connect(
    host=network.secondary_host,
    port=network.secondary_port,
    payload=payload
  )
  
  if success:
    log.info(f"[MODSCAN] SECONDARY connection successful")
    return response
  
  # Both failed
  log.error(f"[MODSCAN] Both PRIMARY and SECONDARY connections failed!")
  return ModScanResponse(
    request=payload,
    detail=f"{response.detail}"
  )

async def ModScanSecondary(payload: ModScanSchema) -> ModScanResponse:
  """
  Force read Modbus register from SECONDARY connection (for value mismatch failover).
  This function directly tries secondary without attempting primary first.
  
  Returns: ModScanResponse with connection info
  """
  network = payload.network
  
  log.info(f"[MODSCAN-SECONDARY] Forcing read from SECONDARY: {network.secondary_host}:{network.secondary_port}")
  success, response = await _modscan_connect(
    host=network.secondary_host,
    port=network.secondary_port,
    payload=payload
  )
  
  if success:
    log.info(f"[MODSCAN-SECONDARY] SECONDARY connection successful")
    # Mark that this came from secondary
    response.detail = f"[SECONDARY] {response.detail}"
    return response
  
  # Secondary failed
  log.error(f"[MODSCAN-SECONDARY] SECONDARY connection failed!")
  return ModScanResponse(
    request=payload,
    detail=f"[SECONDARY] Connection failed: {network.secondary_host}:{network.secondary_port} - {response.detail}"
  )

async def _modwrite_connect(host: str, port: int, payload: ModScanSchema, value: Union[float, int]):
  """
  Internal function: Connect and write Modbus register to specific host:port
  Returns: (success: bool, response: ModWriteResponse)
  """
  async with modbusClient.AsyncModbusTcpClient(
    host=host,
    port=port,
    framer="socket",
    timeout=payload.network.timeout,
    retries=payload.network.retries,
    reconnect_delay=0.5
  ) as client:
    try:
      log.info(f"[MODWRITE] Connecting to {host}:{port}")
      await client.connect()
      
      if not client.connected:
        log.error(f"[MODWRITE] Failed to connect to {host}:{port}")
        client.close()
        return False, ModWriteResponse(
          detail=f"Connection failed to {host}:{port}",
          request=payload, new_value=0.0, current_value=0.0, status=False
        )
      
      log.info(f"[MODWRITE] Connected to {host}:{port}")
      func = get_func_write(client, payload.point_type, dtype=payload.data_type)
      pymodbus_dtype = payload.data_type.pymodbus_dtype
      
      if payload.precision_value:
        value = round(value, payload.precision_value)
      
      log.info(f"[MODWRITE] Writing value: {value}")
      
      # Read current value first
      current = await ModScan(payload)
      if not current.data:
        raise ValueError(f"Cannot read current value: {current.detail}")
      
      if payload.data_type.offset == 1:
        if payload.point_type.is_1bit():
          registers = bool(value)
        else:
          if payload.bit_position and payload.data_type == DataType.BIN:
            log.info("[MODWRITE] Modifying bits...")
            bit_position = int(payload.bit_position)
            bits = list(current.data.bits[0])
            value = int(bool(value))
            bits[bit_position-1] = str(value)
            bits = "".join(bits)
            registers = int(bits.zfill(16), 2)
          else:
            registers = client.convert_from_registers([value], data_type=pymodbus_dtype)
        response = await func(address=payload.address-1, device_id=payload.device_id, value=registers)
      else:
        registers = client.convert_to_registers(value=value, data_type=pymodbus_dtype)
        if not payload.is_big_endian:
          registers = [((val & 0xFF) << 8) | (val >> 8) for val in registers]
        if not payload.swapped and payload.data_type.offset > 1:
          registers = list(reversed(registers))
        response = await func(address=payload.address-1, device_id=payload.device_id, values=registers)
      
      return True, ModWriteResponse(
        request=payload,
        new_value=value,
        current_value=current.data.value,
        status=response.status,
        detail=f"Success from {host}:{port}"
      )

    except exceptions.ConnectionException as e:
      log.critical(f"[MODWRITE] ConnectionException: {e}")
      return False, ModWriteResponse(request=payload, new_value=value, current_value=0.0, status=False, detail=str(e))
    except exceptions.ModbusIOException as e:
      log.critical(f"[MODWRITE] ModbusIOException: {e}")
      return False, ModWriteResponse(request=payload, new_value=value, current_value=0.0, status=False, detail=str(e))
    except Exception as e:
      log.critical(f"[MODWRITE] Exception: {e}")
      return False, ModWriteResponse(request=payload, new_value=value, current_value=0.0, status=False, detail=str(e))
    finally:
      if client.connected:
        client.close()


async def ModWrite(payload: ModScanSchema, value: Union[float, int]) -> ModWriteResponse:
  """
  Write Modbus register with redundancy.
  Flow:
    1. Try primary host:port
    2. If primary fails, try secondary host:port
    3. Return response with active connection info
  """
  network = payload.network
  
  # Try primary connection
  log.info(f"[MODWRITE] Trying PRIMARY: {network.primary_host}:{network.primary_port}")
  success, response = await _modwrite_connect(
    host=network.primary_host,
    port=network.primary_port,
    payload=payload,
    value=value
  )
  
  if success:
    log.info(f"[MODWRITE] PRIMARY connection successful")
    return response
  
  # Primary failed, try secondary
  log.warning(f"[MODWRITE] PRIMARY failed, trying SECONDARY: {network.secondary_host}:{network.secondary_port}")
  success, response = await _modwrite_connect(
    host=network.secondary_host,
    port=network.secondary_port,
    payload=payload,
    value=value
  )
  
  if success:
    log.info(f"[MODWRITE] SECONDARY connection successful")
    return response
  
  # Both failed
  log.error(f"[MODWRITE] Both PRIMARY and SECONDARY connections failed!")
  return ModWriteResponse(
    request=payload,
    new_value=value,
    current_value=0.0,
    status=False,
    detail=f"Connection failed: PRIMARY [{network.primary_host}:{network.primary_port}] & SECONDARY [{network.secondary_host}:{network.secondary_port}]"
  )


if __name__ == "__main__":
  pass
