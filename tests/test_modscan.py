from app.utils import get_tagname
from app.schemas import ModscanRequest,ModScanSchema
from app.modscan._modscan import ModScan
from app.modscan.diagnose import full_diagnostic
import pprint,asyncio


def diagnose_point(point_name: str) -> str:
  global _last_diagnostic_report
  print("tag : ",point_name)
  payload = get_tagname(point_name)
  print(payload)
  if not payload : out = "TAGNAME is not found!"
  else: out = full_diagnostic(ModScanSchema.from_sl(payload)).to_md()
  print(f"\n[SYSTEM] Running diagnostics for: {point_name}...")
  
  # Store the report for later display
  _last_diagnostic_report = out
  return out

if __name__ == "__main__":
  TAGNAME = "E2-TH-U2-MDF-B-01-TEMP"
  # tagname = get_tagname(TAGNAME)
  # payload = ModScanSchema.from_sl(tagname)
  # result = full_diagnostic(payload)
  # print(result.model_dump())
  print(diagnose_point(TAGNAME))

  # pprint.pprint(payload.model_dump())

