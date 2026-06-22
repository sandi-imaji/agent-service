from fastapi import FastAPI, Response, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.schemas import (
    ModScanResponse,
    ModScanSchema,
    ModscanRequest,
    ModWriteRequest,
    PointType,
    DataType,
    NetworkSchema,
    ChatRequest,
    ChatResponse,
)
from app.modscan import ModScan, ModWrite
from app.modscan.diagnose import full_diagnostic_async
from app.config import Config
from app.utils import get_tagname
from app.logger import log
from typing import Union, Optional
from app.llm.rag import query
import uvicorn, asyncio

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Atau specify domain tertentu: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],  # Mengizinkan semua methods termasuk OPTIONS
    allow_headers=["*"],
)

# def rag_stream(prompt: str):
#   import time
#   # contoh: streaming token dari LLM / RAG
#   for token in ["Ini ", "jawaban ", "RAG ", "secara ", "streaming."]:
#     yield token
#     time.sleep(0.5)
#
# @app.get("/")
# async def index(): return StreamingResponse(rag_stream("test"),media_type="text/plain")


@app.get("/")
async def index_rt():
    return {"detail": "welcome to modscan api!"}


@app.post("/modscan", response_model=ModScanResponse)
async def modscan_rt(payload: ModScanSchema, response: Response):
    result = await ModScan(payload)
    if not result.data:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_200_OK
    return result


@app.post("/modscan/tagname")
async def modscan_rt_by_tagname(payload: ModscanRequest, response: Response):
    if payload.tagname == "example":
        net: NetworkSchema = NetworkSchema(
            primary_host="127.0.0.1",
            primary_port=5010,
            secondary_host="127.0.0.1",
            secondary_port=5020,
            timeout=0.1,
            retries=1,
        )
        payload: ModScanSchema = ModScanSchema(
            network=net,
            tagname="test",
            address=1,
            data_type=DataType.BIN,
            point_type=PointType.INPUT_REGISTER,
            is_big_endian=True,
            bit_position=14,
            precision_value=3,
            swapped=False,
        )
    else:
        data = get_tagname(payload.tagname, payload.key)
        if not data:
            raise HTTPException(status_code=500, detail="Tagname is not found!")
        data["retries"] = payload.retries
        data["timeout"] = payload.timeout
        payload = ModScanSchema.from_sl(data)

    # ModScan now handles primary/secondary redundancy internally
    result = await ModScan(payload)
    if not result.data:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_200_OK
    return result


@app.post("/modwrite")
async def modwrite_rt(
    value: Union[float, int], payload: ModScanSchema, response: Response
):
    # ModWrite now handles primary/secondary redundancy internally
    result = await ModWrite(payload, value)
    if not result.status:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_200_OK
    return result


@app.post("/modwrite/tagname")
async def modwrite_rt_tagname(
    value: Union[float, int], payload: ModscanRequest, response: Response
):
    net: NetworkSchema = NetworkSchema(
        primary_host="127.0.0.1",
        primary_port=5010,
        secondary_host="127.0.0.1",
        secondary_port=5020,
        timeout=1.0,
        retries=1,
    )
    payload: ModScanSchema = ModScanSchema(
        network=net,
        tagname="test",
        address=1,
        data_type=DataType.FLOAT,
        point_type=PointType.INPUT_REGISTER,
        is_big_endian=True,
        bit_position=1,
        precision_value=3,
        swapped=False,
    )

    # ModWrite now handles primary/secondary redundancy internally
    result = await ModWrite(payload, value)
    if not result.status:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_200_OK
    return result


@app.get("/diagnose")
async def diagnose_rt(tagname: str, key: Optional[str] = Config.sl_key):
    data = get_tagname(tagname, key)
    if not data:
        raise HTTPException(status_code=500, detail="Tagname is not found!")
    data["retries"] = 1
    data["timeout"] = 5
    payload = ModScanSchema.from_sl(data)

    report = await full_diagnostic_async(payload)
    print(report.model_dump_json(indent=2))


@app.post("/chat")
async def chat_rt(payload: ChatRequest):
    response = await query(payload.query)
    return ChatResponse(chat_req=payload, response=response)


if __name__ == "__main__": uvicorn.run("router:app", host=Config.host, port=Config.port, reload=True)
