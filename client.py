from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
import shutil
import os
from pathlib import Path
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
import json
import asyncio

app = FastAPI()

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

MHTML_DIR = Path("mhtml_output")
PRICE_INFO_DIR = Path("price_info_output")
PUBLIC_DIR = Path("public")

# Ensure required directories exist
for d in [MHTML_DIR, PRICE_INFO_DIR, PUBLIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".mhtml"):
        raise HTTPException(status_code=400, detail="Only .mhtml files are allowed")

    # Clear existing mhtml files to avoid clutter/pollution
    for f in MHTML_DIR.glob("*.mhtml"):
        f.unlink()

    file_path = MHTML_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"filename": file.filename, "message": "Upload successful"}

async def run_mcp_pipeline(websocket: WebSocket, filename: str, extraction_request: str):
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "server.py"],
        env=os.environ.copy()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await websocket.send_json({"type": "log", "message": "MCP Server Initialized"})

                # Step 1: screenshot_tool
                await websocket.send_json({"type": "progress", "step": "Taking screenshots (screenshot_tool) ..."})
                result = await session.call_tool("screenshot_tool", {})
                await websocket.send_json({
                    "type": "step_done", 
                    "step": "screenshot_tool",
                    "data": json.loads(result.content[0].text) if result.content else "No Output"
                })

                # Step 2: product_name_processing_tool
                await websocket.send_json({"type": "progress", "step": "Processing Product Name & OCR... (product_name_processing_tool)"})
                result = await session.call_tool("product_name_processing_tool", {})
                content = json.loads(result.content[0].text) if result.content else {}
                
                await websocket.send_json({
                    "type": "step_done", 
                    "step": "product_name_processing_tool",
                    "data": content
                })

                # (Fallback to product_price_processing_tool if name processing failed)
                if not content.get("success", False):
                    await websocket.send_json({"type": "log", "message": "Name processing failed or incomplete. Attempting price processing..."})
                    await websocket.send_json({"type": "progress", "step": "Processing Product Price... (product_price_processing_tool)"})
                    price_result = await session.call_tool("product_price_processing_tool", {})
                    await websocket.send_json({
                        "type": "step_done", 
                        "step": "product_price_processing_tool",
                        "data": json.loads(price_result.content[0].text) if price_result.content else {}
                    })

                # Step 3: extract_data_tool
                await websocket.send_json({"type": "progress", "step": "Generating extraction configurations... (extract_data_tool)"})
                result = await session.call_tool("extract_data_tool", {"extraction_request": extraction_request})
                config_data = json.loads(result.content[0].text) if result.content else {}
                await websocket.send_json({
                    "type": "step_done",
                    "step": "extract_data_tool",
                    "data": config_data
                })

                if not config_data.get("success", False):
                    await websocket.send_json({"type": "error", "message": "Failed to generate extraction configuration."})
                    return

                schema_path = config_data.get("schema_path", "")

                # Step 4: execute_extraction_tool
                await websocket.send_json({"type": "progress", "step": f"Executing extraction using schema {schema_path}... (execute_extraction_tool)"})
                kwargs = {"selectors_config_path": schema_path} if schema_path else {}
                result = await session.call_tool("execute_extraction_tool", kwargs)
                final_data = json.loads(result.content[0].text) if result.content else {}
                
                await websocket.send_json({
                    "type": "step_done",
                    "step": "execute_extraction_tool",
                    "data": final_data
                })

                await websocket.send_json({
                    "type": "result",
                    "data": final_data
                })
                await websocket.send_json({"type": "complete"})

    except Exception as e:
        await websocket.send_json({"type": "fatal", "message": str(e)})


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        msg = json.loads(data)
        
        if msg.get("action") == "start":
            filename = msg.get("filename", "unknown.mhtml")
            extraction_request = msg.get("extraction_request", "I want to extract all product names and prices")
            await websocket.send_json({"type": "log", "message": f"Starting extraction pipeline for {filename}..."})
            await run_mcp_pipeline(websocket, filename, extraction_request)
            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({"type": "fatal", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
