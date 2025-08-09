import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
upload_tracking = {}

app = FastAPI()

def create_upload_link(user_id: str, direction: str) -> str:
    unique_token = str(uuid.uuid4())
    upload_tracking[unique_token] = {"user_id": user_id, "direction": direction}
    # You must set this to your actual server/public/ngrok URL if not localhost
    return f"http://localhost:8000/upload?token={unique_token}"

def create_download_link(file_path: str) -> str:
    filename = os.path.basename(file_path)
    return f"http://localhost:8000/download/{filename}"

def convert_txt_doc_to_pdf(input_path: str, output_path: str):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            pdf.cell(0, 10, txt=line.strip(), ln=True)
    pdf.output(output_path)

def convert_pdf_to_txt(input_path: str, output_path: str):
    import PyPDF2
    reader = PyPDF2.PdfReader(input_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

@app.post("/upload")
async def upload_file(token: str = None, file: UploadFile = File(...)):
    if not token or token not in upload_tracking:
        raise HTTPException(status_code=400, detail="Invalid or missing token.")
    info = upload_tracking[token]
    direction = info["direction"]

    file_ext = os.path.splitext(file.filename)[1].lower()
    input_file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{file_ext}")
    with open(input_file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    if direction == "to_pdf":
        output_file_path = input_file_path.rsplit(".", 1)[0] + ".pdf"
        if file_ext not in [".txt"]:
            raise HTTPException(status_code=400, detail="Currently only .txt files supported for Text->PDF.")
        convert_txt_doc_to_pdf(input_file_path, output_file_path)
    elif direction == "to_text":
        output_file_path = input_file_path.rsplit(".", 1)[0] + ".txt"
        if file_ext != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files supported for PDF->Text.")
        convert_pdf_to_txt(input_file_path, output_file_path)
    else:
        raise HTTPException(status_code=400, detail="Invalid conversion direction.")

    download_url = create_download_link(output_file_path)
    return {"message": "File converted successfully!", "download_url": download_url}

@app.get("/download/{filename}")
def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, filename=filename)

# To run: uvicorn file_conversion_service:app --host 0.0.0.0 --port 8000
