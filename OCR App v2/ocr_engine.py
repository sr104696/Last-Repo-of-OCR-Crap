import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import io
import os
import shutil

# Check for Tesseract on Windows typical paths
DEFAULT_TESS_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\sethn\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
]

def find_tesseract():
    # If it's already in path
    if shutil.which("tesseract"):
        return "tesseract"
        
    for p in DEFAULT_TESS_PATHS:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return p
    return None

def process_pdf(input_path, output_path, progress_callback, log_callback, lang="eng", dpi=300):
    if not find_tesseract():
        raise RuntimeError("Tesseract OCR not found. Please install it.")

    try:
        doc = fitz.open(str(input_path))
        out_doc = fitz.open()
        total = len(doc)
        
        if total == 0:
            raise Exception("PDF has no pages.")

        for i, page in enumerate(doc, start=1):
            log_callback(f"Processing page {i} of {total}...")
            # Render page to image
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            
            # Using Pillow to load the image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Run Tesseract to generate a searchable PDF page
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                img, extension='pdf', lang=lang, config='--psm 1 --oem 3'
            )
            
            # Insert the newly generated searchable page into the output document
            img_pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
            out_doc.insert_pdf(img_pdf)
            
            progress_callback((i / total) * 100)

        # Retain metadata from original
        out_doc.set_metadata(doc.metadata)

        log_callback("Saving document...")
        out_doc.save(str(output_path), garbage=4, deflate=True)
        out_doc.close()
        doc.close()
        
        log_callback("✅ OCR processing completed successfully.")
        return True
        
    except Exception as e:
        log_callback(f"❌ Error during OCR: {str(e)}")
        raise e
