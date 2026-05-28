from enum import Enum,auto,IntEnum,StrEnum
from typing import List,Optional, Union,Any
from pydantic import BaseModel,Field,field_serializer
from pymodbus.client.mixin import ModbusClientMixin 
import datetime

class DataType(StrEnum):
  BIN = auto()
  HEX = auto()
  INT8 = auto()
  UINT8 = auto()
  INT16 = auto()
  UINT16 = auto()
  INT32 = auto()
  UINT32 = auto()
  INT64 = auto()
  UINT64 = auto()
  FLOAT = auto()
  DOUBLE = auto()

  @property
  def offset(self):
    if self in (DataType.INT32,DataType.UINT32,DataType.FLOAT): return 2
    elif self in (DataType.INT64,DataType.UINT64,DataType.DOUBLE): return 4
    else: return 1
  
  @property
  def nbytes(self):
    if self in (DataType.BIN,DataType.INT8,DataType.UINT8): return 1
    return self.offset * 2

  def is_signed(self) -> bool: 
    return self not in (DataType.UINT8,DataType.UINT16, DataType.UINT32,DataType.UINT64,DataType.BIN)
  
  @property
  def fmt(self):
    return {
      DataType.INT8:"b", DataType.UINT8:"B",
      DataType.INT16:"h", DataType.UINT16:"H",
      DataType.INT32:"i", DataType.UINT32:"I",
      DataType.INT64:"q", DataType.UINT64:"Q",
      DataType.FLOAT:"f",DataType.DOUBLE:"d"
    }[self]

  @property
  def pymodbus_dtype(self):
    PyModbusDtype = ModbusClientMixin.DATATYPE
    match self:
      case DataType.INT16: return PyModbusDtype.INT16
      case DataType.UINT16: return PyModbusDtype.UINT16
      case DataType.INT32: return PyModbusDtype.INT32
      case DataType.UINT32: return PyModbusDtype.UINT32
      case DataType.INT64: return PyModbusDtype.INT64
      case DataType.FLOAT: return PyModbusDtype.FLOAT32
      case DataType.DOUBLE: return PyModbusDtype.FLOAT64
      case DataType.BIN: return PyModbusDtype.INT16
      case _: raise TypeError(f"DataType is not support : {self}")

  @staticmethod 
  def from_sl(dtype:int):
    match dtype:
      case 1: return DataType.BIN
      case 3: return DataType.INT16
      case 4: return DataType.UINT16
      case 5 | 6: return DataType.INT32
      case 7 | 8: return DataType.UINT32
      case 9 | 10: return DataType.INT64
      case 11 | 12: return DataType.UINT64
      case 13 | 14: return DataType.FLOAT
      case 15 | 16: return DataType.DOUBLE
      case _: raise TypeError(f"DataType is not support ! : {dtype}")
      
  @staticmethod 
  def is_swapped(v:int): return True if v in (6,8,10,12,14,16) else False

class PointType(Enum):
  COIL_STATUS = 1
  INPUT_STATUS = auto()
  HOLDING_REGISTER = auto()
  INPUT_REGISTER = auto()

  def is_1bit(self) -> bool: return self in (PointType.COIL_STATUS,PointType.INPUT_STATUS)
  def is_write(self) -> bool:return self in (PointType.COIL_STATUS,PointType.HOLDING_REGISTER)

class ExceptionCodes(IntEnum):
   """Represents the allowed exception codes."""
   ILLEGAL_FUNCTION = 0x01
   ILLEGAL_ADDRESS = 0x02
   ILLEGAL_VALUE = 0x03
   DEVICE_FAILURE = 0x04
   ACKNOWLEDGE = 0x05
   DEVICE_BUSY = 0x06
   NEGATIVE_ACKNOWLEDGE = 0x07
   MEMORY_PARITY_ERROR = 0x08
   GATEWAY_PATH_UNAVIABLE = 0x0A
   GATEWAY_NO_RESPONSE = 0x0B

class NetworkSchema(BaseModel):
  primary_host:str = Field(...,description="Primary Host Connections",examples=["192.168.1.100","plc.local"])
  primary_port:int = Field(...,description="Primary Port Connections")
  secondary_host:str = Field(...,description="Secondary Host Connections",examples=["192.168.1.100","plc.local"])
  secondary_port:int = Field(...,description="Secondary Port Connections")
  retries:int = Field(2,description="Retries for Modscan")
  timeout:float = Field(5.0,description="Timeout for Modscan")

class ModScanSchema(BaseModel):
  network:NetworkSchema = Field(...,description="Network Schema")
  tagname:str = Field(...,description="Tagname",examples=["IM1-UPS_UTI-2-A-A01-MAXIMUM_LOAD_ALARM"])
  bit_position:Optional[int] = Field(None,description="Bit Position")
  precision_value: Optional[int] = Field(None,description="Round of floating value")
  factor_value:Optional[float] = Field(None,description="Factor Value")
  offset_value:Optional[int] = Field(None,description="Offset Value")
  is_big_endian:bool = Field(False,description="Byte Order")
  device_id: int = Field(1, ge=1, le=247, description="Unit ID / Slave ID Modbus (1-247)")
  address: int = Field( ..., ge=0, le=65535, description="Starting address register (0-based, sesuai spesifikasi pymodbus)")
  data_type:DataType = Field(...,description="Tipe data yang diharapkan dari register")
  point_type:PointType = Field(...,description="Modbus Function Code yang akan digunakan")
  swapped: bool = Field(False, description="Apakah word order dibalik (untuk tipe 32-bit dan 64-bit: ABCD → CDAB atau BADC → DCBA)")

  @field_serializer("point_type")
  def serialize_point_type(self,value:PointType) -> str: return value.name

  @field_serializer("data_type")
  def serialize_data_type(self,value:DataType) -> str: return value.name

  @staticmethod
  def from_sl(data:dict):
    tagname = data["tagname"]
    address = int(data["address"])
    bit_position = data["bit_position"]
    is_big_endian = bool(int(data["byte_order"]))
    point_type = PointType(int(data["modbus_point_type"]))
    data_type = DataType.from_sl(int(data["data_type"]))
    offset_value = data.get("offset_value",0)
    precision_value = data.get("precision_value",2)
    factor_value = data["factor_value"]
    device_id = int(data["device_id"])
    primary_host = data["primary_host"]
    primary_port = int(data["primary_port"])
    secondary_host = data["primary_host"]
    secondary_port = int(data["secondary_port"])
    swapped = DataType.is_swapped(int(data["data_type"]))
    retries = data.get("retries",2)
    timeout = data.get("timeout",5)
    network = NetworkSchema(primary_host=primary_host,primary_port=primary_port,
                            secondary_host=secondary_host,secondary_port=secondary_port,
                            retries=retries,timeout=timeout)
    return ModScanSchema(tagname=tagname,address=address,bit_position=bit_position,
                         is_big_endian=is_big_endian,point_type=point_type,data_type=data_type,
                         offset_value=offset_value,precision_value=precision_value,
                         factor_value=factor_value,device_id=device_id,swapped=swapped,network=network)
    

class ModscanRequest(BaseModel):
  tagname:str = Field(...,description="Tagname",examples=["JK5-TH-1"])
  key:Optional[str] = Field(None,description="Key for get connections")
  retries:int = Field(2,description="")
  timeout:float = Field(0.5,description="")

class Data(BaseModel):
  bits: List[str]
  reg_hex: List[str]
  value:Any

class ModScanResponse(BaseModel):
  request:ModScanSchema
  data:Optional[Data] = None
  detail:str
  
class ModWriteRequest(BaseModel):
  tagname:str = Field(...,description="Tagname",examples=["JK5-TH"])
  key:Optional[str] = Field(None,description="Key for get connections")
  retries:int = Field(2,description="")
  timeout:float = Field(0.5,description="")
  value:Union[float,int]

class ModWriteResponse(BaseModel):
  request:ModScanSchema
  new_value:Union[float,int]
  current_value:Union[float,int]
  status:bool
  detail:str

########################### REPORTING ###################################
class Layer(Enum):
  PING = auto()
  TELNET = auto()
  REGISTER = auto()
  CHECK_VALUE = auto()
  SMARTLINK = auto()

class Status(Enum):
  OK = auto()
  FAIL = auto()
  SUCCESS = auto()
  CLOSED = auto()
  OPEN = auto()
  TIMEOUT = auto()
  CHECKING = auto()        
  COMLOSS = auto()        
  RESOLVED = auto()       
  UNRESOLVED = auto()     
  def __str__(self): return self.name

class DiagnosticSchema(BaseModel):
  layer:Layer
  timestamp:datetime.datetime
  status:Status
  detail:str

class FullDiagnosticSchema(BaseModel):
  timestamp:datetime.datetime
  times:float = 0.0
  ping:DiagnosticSchema
  telnet:DiagnosticSchema
  smartlink:Optional[DiagnosticSchema] = None
  register_data:Data
  modscan_data:Optional[ModScanSchema] = None
  status:Status
  detail:str

  def to_md(self):
    """Generate simple text representation for chat"""
    
    # Status emoji mapping
    status_emoji = {
      Status.OK: "✅",
      Status.SUCCESS: "✅",
      Status.RESOLVED: "✅",
      Status.FAIL: "❌",
      Status.CLOSED: "🚫",
      Status.TIMEOUT: "⏱️",
      Status.COMLOSS: "📡",
      Status.UNRESOLVED: "⚠️",
      Status.CHECKING: "🔄",
      Status.OPEN: "🔓",
    }
    
    main_emoji = status_emoji.get(self.status, "ℹ️")
    
    # Build simple text report
    lines = []
    lines.append("=" * 60)
    lines.append("🔬 DIAGNOSTIC REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"{main_emoji} Status: {self.detail}")
    lines.append(f"⏱️  Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} ({self.times:.2f}s)")
    lines.append("")
    
    # Network Diagnostics
    lines.append("-" * 60)
    lines.append("🌐 NETWORK DIAGNOSTICS")
    lines.append("-" * 60)
    
    # Ping
    ping_emoji = status_emoji.get(self.ping.status, "ℹ️")
    ping_status = "PASSED" if self.ping.status in [Status.OK, Status.SUCCESS] else "FAILED"
    lines.append(f"\n1️⃣  IP Test ({self.ping.layer.name}) ICMP")
    lines.append(f"   Status: {ping_emoji} {ping_status} ({self.ping.status})")
    lines.append(f"   Detail: {self.ping.detail}")
    lines.append(f"   Time: {self.ping.timestamp.strftime('%H:%M:%S')}")
    
    # Telnet
    telnet_emoji = status_emoji.get(self.telnet.status, "ℹ️")
    telnet_status = "PASSED" if self.telnet.status in [Status.OK, Status.SUCCESS, Status.OPEN] else "FAILED"
    lines.append(f"\n2️⃣  PORT Test ({self.telnet.layer.name})")
    lines.append(f"   Status: {telnet_emoji} {telnet_status} ({self.telnet.status})")
    lines.append(f"   Detail: {self.telnet.detail}")
    lines.append(f"   Time: {self.telnet.timestamp.strftime('%H:%M:%S')}")
    
    # Smartlink - Value comparison layer
    if self.smartlink:
      smartlink_emoji = status_emoji.get(self.smartlink.status, "ℹ️")
      smartlink_status = "MATCH" if self.smartlink.status in [Status.OK, Status.SUCCESS] else "MISMATCH"
      lines.append(f"\n3️⃣  VALUE Compare ({self.smartlink.layer.name})")
      lines.append(f"   Status: {smartlink_emoji} {smartlink_status} ({self.smartlink.status})")
      lines.append(f"   Detail: {self.smartlink.detail}")
      lines.append(f"   Time: {self.smartlink.timestamp.strftime('%H:%M:%S')}")
    
    # Register Data
    lines.append("")
    lines.append("-" * 60)
    lines.append("📡 REGISTER DATA")
    lines.append("-" * 60)
    
    if self.register_data.value is not None:
      lines.append(f"\n📈 Value: {self.register_data.value}")
      if self.modscan_data: lines.append(f"   Type: {self.modscan_data.data_type}")
      
      if self.register_data.reg_hex:
        hex_str = ' '.join(self.register_data.reg_hex)
        lines.append(f"\n🔤 Hex: {hex_str}")
      
      if self.register_data.bits:
        bits_str = ' '.join(self.register_data.bits)
        lines.append(f"\n💾 Bits: {bits_str}")
        
        # Show important bits (ON bits only)
        # all_bits = ''.join(self.register_data.bits)
        # total_bits = len(all_bits)
        # on_bits = []
        # for idx, bit in enumerate(all_bits):
        #   if bit == "1":
        #     bit_pos = total_bits - idx - 1
        #     on_bits.append(f"Bit{bit_pos}")
        #
        # if on_bits:
        #   lines.append(f"   Active: {', '.join(on_bits)}")

    else:
      lines.append("\n⚠️  No register data available")
    
    # Modbus Configuration
    if self.modscan_data:
      lines.append("")
      lines.append("-" * 60)
      lines.append("🔌 MODBUS CONFIGURATION")
      lines.append("-" * 60)
      
      lines.append(f"\n🏷️ Tag: {self.modscan_data.tagname}")
      lines.append(f"   Type: {self.modscan_data.data_type} / {self.modscan_data.point_type}")
      
      lines.append(f"\n🌐 Network:")
      lines.append(f"   Primary: {self.modscan_data.network.primary_host}:{self.modscan_data.network.primary_port}")
      lines.append(f"   Secondary: {self.modscan_data.network.secondary_host}:{self.modscan_data.network.secondary_port}")
      lines.append(f"   Retries: {self.modscan_data.network.retries} | Timeout: {self.modscan_data.network.timeout}s")
      
      lines.append(f"\n⚙️  Parameters:")
      lines.append(f"   Device ID: {self.modscan_data.device_id}")
      lines.append(f"   Address: {self.modscan_data.address}")
      lines.append(f"   Byte Order: {'Big Endian' if self.modscan_data.is_big_endian else 'Little Endian'}")
      lines.append(f"   Swapped: {'Yes' if self.modscan_data.swapped else 'No'}")
      
      # Optional params
      if self.modscan_data.bit_position is not None:
        lines.append(f"   Bit Position: {self.modscan_data.bit_position}")
      if self.modscan_data.precision_value is not None:
        lines.append(f"   Precision: {self.modscan_data.precision_value}")
      if self.modscan_data.factor_value is not None:
        lines.append(f"   Factor: {self.modscan_data.factor_value}")
      if self.modscan_data.offset_value is not None:
        lines.append(f"   Offset: {self.modscan_data.offset_value}")
    
    # Recommendations based on layer status
    lines.append("")
    lines.append("-" * 60)
    lines.append("💡 RECOMMENDATIONS")
    lines.append("-" * 60)
    lines.append("")
    
    if self.status in [Status.OK, Status.SUCCESS, Status.RESOLVED]:
      lines.append("✅ All systems operational. No action required.")
      if self.register_data.value is not None:
        lines.append(f"   Current value: {self.register_data.value}")
        if self.smartlink and self.smartlink.status in [Status.OK, Status.SUCCESS]:
          lines.append(f"   Smartlink value verified and matched.")
    
    else:
      # Check which layer failed and provide specific recommendations
      failed_layers = []
      
      # PING Layer Check
      if self.ping.status not in [Status.OK, Status.SUCCESS]:
        failed_layers.append("PING")
        lines.append("🔴 PING Layer Failed:")
        lines.append("")
        lines.append("Immediate Actions:")
        lines.append("   • Verify physical network cable connections")
        lines.append("   • Check if device is powered on")
        lines.append("   • Confirm IP address is correct")
        if self.modscan_data:
          lines.append(f"   • Ping test: ping {self.modscan_data.network.primary_host}")
          lines.append(f"   • Backup: ping {self.modscan_data.network.secondary_host}")
        lines.append("")
        lines.append("Troubleshooting:")
        lines.append("   • Check network switch/router status")
        lines.append("   • Verify VLAN configuration")
        lines.append("   • Check if ICMP is blocked by firewall")
        lines.append("   • Try traceroute to identify where connection fails")
        lines.append("")
      
      # TELNET Layer Check  
      if self.telnet.status not in [Status.OK, Status.SUCCESS, Status.OPEN]:
        failed_layers.append("TELNET")
        lines.append("🔴 TELNET/PORT Layer Failed:")
        lines.append("")
        lines.append("Immediate Actions:")
        lines.append("   • Verify Modbus service is running on device")
        lines.append("   • Check if port is correct (usually 502 or 5020)")
        if self.modscan_data:
          lines.append(f"   • Test: telnet {self.modscan_data.network.primary_host} {self.modscan_data.network.primary_port}")
          lines.append(f"   • Backup: telnet {self.modscan_data.network.secondary_host} {self.modscan_data.network.secondary_port}")
        lines.append("")
        lines.append("Troubleshooting:")
        lines.append("   • Check firewall rules for Modbus port")
        lines.append("   • Verify device Modbus TCP is enabled")
        lines.append("   • Check max connections limit on device")
        lines.append("   • Restart Modbus service on device")
        lines.append("")
      
      # SMARTLINK Layer Check
      if self.smartlink and self.smartlink.status not in [Status.OK, Status.SUCCESS]:
        failed_layers.append("SMARTLINK")
        lines.append("🔴 SMARTLINK Value Comparison Failed:")
        lines.append("")
        lines.append("Immediate Actions:")
        lines.append("   • Value mismatch between ModScan and Smartlink")
        lines.append("   • Check if tagname is correctly mapped")
        lines.append("   • Verify data synchronization timing")
        lines.append("")
        lines.append("Troubleshooting:")
        if self.smartlink.status == Status.COMLOSS:
          lines.append("   • Smartlink API connection timeout/failed")
          lines.append("   • Check Smartlink server availability")
          lines.append("   • Verify network route to Smartlink API")
        else:
          lines.append("   • Compare ModScan value with Smartlink dashboard")
          lines.append("   • Check scaling factor and offset configuration")
          lines.append("   • Verify data type conversion (INT/FLOAT)")
          lines.append("   • Check if point is stale or freeze in Smartlink")
        lines.append("")
      
      # Register Layer Check (no smartlink issue, but register data is None)
      if self.register_data.value is None and "PING" not in failed_layers and "TELNET" not in failed_layers:
        failed_layers.append("REGISTER")
        lines.append("🔴 REGISTER Read Failed:")
        lines.append("")
        lines.append("Immediate Actions:")
        lines.append("   • Verify register address is correct")
        lines.append("   • Check device ID (slave ID) configuration")
        if self.modscan_data:
          lines.append(f"   • Device ID: {self.modscan_data.device_id}")
          lines.append(f"   • Address: {self.modscan_data.address}")
          lines.append(f"   • Data Type: {self.modscan_data.data_type}")
        lines.append("")
        lines.append("Troubleshooting:")
        lines.append("   • Check Modbus function code (FC) is supported")
        lines.append("   • Verify byte order (big/little endian)")
        lines.append("   • Check word swap configuration")
        lines.append("   • Increase timeout value if device is slow")
        lines.append("")
      
      if not failed_layers:
        lines.append("⚠️  Unknown issue detected. Review diagnostic details above.")
    
    lines.append("")
    
    return '\n'.join(lines).join("\n\n")


class ChatRequest(BaseModel):
  query:str
  timestamp:datetime.datetime = datetime.datetime.now()
  context:Optional[str] = None

class ChatResponse(BaseModel):
  chat_req:ChatRequest
  timestamp:datetime.datetime = datetime.datetime.now()
  response:str
  

if __name__ == "__main__":pass




