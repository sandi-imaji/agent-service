import requests

def analysis_point(report:str) -> str:
  system_prompt = r"""
    You are a diagnostic analyzer. Parse reports in this format:
    TAG=<tagname> ST=<status> TIME=<elapsed> | NET:P=<ping> T=<telnet> | VAL:SL=<sl_val> MS=<ms_val> | CHK=<check_status> | FO:<Y/N> CONN=<P/S> | MIS:SL=<val> MS=<val> | REG:<value> H=<hex> | CFG:ID=<id> A=<addr> T=<type> | IP:P=<primary> S=<secondary>

    ANALYSIS RULES:
    - ST=OK + FO:N → Normal operation on Primary
    - ST=OK + FO:Y → Failover occurred, check MIS values
    - ST=FAIL → Identify failed layer (NET/VAL/REG)
    - CHK=OK → Values match | CHK=FAIL → Mismatch detected
    - CONN=S → Operating on Secondary connection

    OUTPUT:
    1. Status: [OK/FAILED]
    2. Issue: [None/Brief description]
    3. Action: [Recommended fix]
    """
  response = requests.post(
    "http://localhost:8080/v1/chat/completions",
    json={
      "messages": [
        {
          "role": "system",
          "content": system_prompt
        },
        {
          "role": "user",
          "content": report
        }
      ]
    }
  ).json()

  return response['choices'][0]['message']['content']
