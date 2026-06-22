import httpx
import json

with open("./system_prompt.txt","r") as f:
  system_prompt = f.read()

def text(message:str):
  with httpx.stream(
      "POST",
      "http://localhost:8080/v1/chat/completions",
      json={
        "messages": [
          {
            "role": "system",
            "content": system_prompt 
          },
          {
            "role": "user",
            "content": message
          }
        ],
        "stream": True
      }
  ) as response:

    for line in response.iter_lines():

      if not line: continue

      if line.startswith("data: "):
        data = line[6:]

        if data == "[DONE]":
            break

        chunk = json.loads(data)

        delta = chunk["choices"][0]["delta"]

        if "content" in delta:
          if delta["content"]  == "None": continue
          print(delta["content"], end="", flush=True)



if __name__ == "__main__":
  while 1:
    try:
      print()
      message = str(input("> "))
      text(message)
      print()
    except KeyboardInterrupt:
      break
