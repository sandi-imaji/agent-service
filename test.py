import asyncio,pprint
from app.modscan._modscan import ModScan,_modscan_connect
from app.schemas import ModScanResponse,ModScanSchema
from app.utils import get_tagname
from app.logger import log


if __name__ == "__main__":
  tagname = "CRAH-2DH2.2-RETURN_AIR_TEMP"
  point_sl = get_tagname(tagname)
  curr_value = point_sl['currvalue']
  pprint.pprint(point_sl)
  modscan_schema = ModScanSchema.from_sl(point_sl)


