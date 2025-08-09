import os
import uuid
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
upload_tracking = {}

app = FastAPI()

IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "your_imgbb_api_key")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "your_serpapi_api_key")

def create_upload_link(user_id: str) -> str:
    unique_token = str(uuid.uuid4())
    upload_tracking[unique_token] = {"user_id": user_id}
    return f"http://localhost:8000/lens_upload?token={unique_token}"

async def upload_to_imgbb(image_path: str) -> str:
    async with httpx.AsyncClient() as client:
        with open(image_path, "rb") as f:
            bytes_data = f.read()
        response = await client.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": bytes_data},
        )
        resp_json = response.json()
        if response.status_code == 200 and resp_json.get("data") and resp_json["data"].get("url"):
            return resp_json["data"]["url"]
        else:
            raise Exception(f"Image upload failed: {resp_json}")

async def search_google_lens(image_url: str) -> str:
    params = {
        "engine": "google_lens",
        "url": image_url,
        "api_key": SERPAPI_API_KEY,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get("https://serpapi.com/search.json", params=params)
        if response.status_code != 200:
            raise Exception(f"Google Lens API call failed: {response.status_code}")
        data = response.json()
    results = []
    if "visual_matches" in data:
        for match in data["visual_matches"][:5]:
            title = match.get("title") or "No title"
            snippet = match.get("snippet") or ""
            link = match.get("link") or ""
            results.append(f"- {title}\n  {snippet}\n  Link: {link}")
    if not results:
        return "No relevant Google Lens results found for your image."
    return "Google Lens Search Results:\n" + "\n\n".join(results)

@app.post("/lens_upload")
async def lens_upload(token: str = None, file: UploadFile = File(...)):
    if not token or token not in upload_tracking:
        raise HTTPException(status_code=400, detail="Invalid or missing token.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Only .jpg, .jpeg, .png files are supported.")
    image_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{ext}")
    with open(image_path, "wb") as f:
        content = await file.read()
        f.write(content)
    try:
        public_url = await upload_to_imgbb(image_path)
        lens_result = await search_google_lens(public_url)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    return {"message": "Image processed successfully.", "results": lens_result}

@app.get("/lens_download/{filename}")
def lens_download(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, filename=filename)

# To run: uvicorn image_lens_service:app --host 0.0.0.0 --port 8000
