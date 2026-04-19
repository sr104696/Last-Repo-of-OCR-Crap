import os
import sys
import threading
import concurrent.futures
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import requests

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

def find_tesseract():
    import shutil
    if shutil.which("tesseract"): return "tesseract"
    for p in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
    ]:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return p
    return None

def get_downloads_dir():
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders") as key:
                return winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")[0]
        except Exception:
            pass
    return str(Path.home() / "Downloads")

class OCRApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Legit OCR Scanner")
        
        # Center main window
        w, h = 420, 300
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = int((sw/2) - (w/2))
        y = int((sh/2) - (h/2))
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.resizable(False, False)

        # State Variables
        self.input_pdf = tk.StringVar(value="")
        self.output_pdf = tk.StringVar(value="")
        self.engine_choice = tk.StringVar(value="local")
        
        # UI Setup
        self._build_ui()
        
        # Check Tesseract if user wants Local engine
        self.tesseract_ready = find_tesseract() is not None

    def _build_ui(self):
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Document OCR Scanner", style="Header.TLabel").pack(pady=(0, 10))
        
        # File selector
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill=tk.X, pady=5)
        self.lbl_file = ttk.Label(file_frame, text="No file selected...", foreground="gray")
        self.lbl_file.pack(side=tk.LEFT)
        ttk.Button(file_frame, text="Browse PDF", command=self.pick_file).pack(side=tk.RIGHT)
        
        # Divider
        ttk.Separator(frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Engine Options
        engine_frame = ttk.LabelFrame(frame, text=" Processing Engine ", padding=10)
        engine_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(engine_frame, text="Local Native OCR (Unlimited Size/Pages)", 
                        variable=self.engine_choice, value="local").pack(anchor=tk.W)
        ttk.Radiobutton(engine_frame, text="Cloud API OCR.Space (Slow, 1MB Limit)", 
                        variable=self.engine_choice, value="cloud").pack(anchor=tk.W)
        
        # Start Routine
        self.btn_run = ttk.Button(frame, text="EXECUTE OCR", command=self.run_pipeline)
        self.btn_run.pack(pady=15, fill=tk.X)

    def pick_file(self):
        path = filedialog.askopenfilename(
            title="Select PDF for OCR",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if path:
            self.input_pdf.set(path)
            # Truncate visually
            short_name = os.path.basename(path)
            self.lbl_file.config(text=short_name, foreground="black")

    def run_pipeline(self):
        in_path = self.input_pdf.get()
        if not in_path:
            messagebox.showwarning("Missing File", "Please browse and select a PDF file first.")
            return
            
        if self.engine_choice.get() == "local" and not self.tesseract_ready:
            messagebox.showerror("Dependency Error", "Local OCR engine not found. Please install Tesseract or use the Cloud API.")
            return

        # Determine output location
        downloads = get_downloads_dir()
        name, _ = os.path.splitext(os.path.basename(in_path))
        out_path = filedialog.asksaveasfilename(
            title="Save OCR'd PDF As...",
            initialdir=downloads,
            initialfile=f"{name}_ocr.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        
        if not out_path:
            return  # Cancelled
            
        self.output_pdf.set(out_path)
        
        # Disable Main UI
        self.root.withdraw()
        
        # Spawn Progress UI
        self.prog_win = tk.Toplevel()
        try:
            self.prog_win.iconbitmap('')
        except Exception:
            pass
        self.prog_win.title("OCR Engine Working")
        w, h = 340, 110
        sw = self.prog_win.winfo_screenwidth()
        sh = self.prog_win.winfo_screenheight()
        self.prog_win.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")
        self.prog_win.resizable(False, False)
        self.prog_win.attributes('-topmost', 1)
        
        self.lbl = ttk.Label(self.prog_win, text="Starting engine...", font=("Segoe UI", 10))
        self.lbl.pack(pady=15)
        
        self.bar = ttk.Progressbar(self.prog_win, length=300)
        self.bar.pack(pady=5)
        
        # Boot thread
        if self.engine_choice.get() == "cloud":
            threading.Thread(target=self.do_cloud_ocr, args=(in_path, out_path), daemon=True).start()
        else:
            threading.Thread(target=self.do_local_ocr, args=(in_path, out_path), daemon=True).start()

    def do_cloud_ocr(self, input_pdf, output_pdf):
        # OCR.Space Free Tier 1MB limit check
        file_size = os.path.getsize(input_pdf)
        # 1MB = 1048576 bytes
        if file_size > 1024 * 1024:
            size_mb = round(file_size / (1024*1024), 2)
            self.root.after(0, self.on_error, f"Cloud API Failure Prevented:\n\nYour PDF is {size_mb} MB.\nThe OCR.Space Free Tier limits uploads strictly to 1 MB.\n\nPlease close and process this file with the 'Local Native OCR' engine instead!")
            return

        try:
            def update_ui(msg):
                self.lbl.config(text=msg)
                self.bar.config(mode="indeterminate")
                self.bar.start(10)

            self.root.after(0, update_ui, "Uploading to Cloud OCR.Space...")

            api_url = "https://api.ocr.space/parse/image"
            payload = {
                "apikey": "K82448458088957",
                "isCreateSearchablePdf": "true",
                "isSearchablePdfHideTextLayer": "true",
                "language": "eng"
            }

            with open(input_pdf, 'rb') as f:
                response = requests.post(api_url, data=payload, files={"file": f}, timeout=120)

            result = response.json()
            exit_code = str(result.get("OCRExitCode"))
            
            # Code 1 is success, 2 is partial success
            if exit_code not in ['1', '2']:
                err = result.get('ErrorMessage', 'Unknown server error')
                err_det = result.get('ErrorDetails', '')
                self.root.after(0, self.on_error, f"Cloud processing failed.\nError: {err}\nDetails: {err_det}")
                return
                
            pdf_url = result.get("SearchablePDFURL")
            if not pdf_url:
                self.root.after(0, self.on_error, "Success but server did not generate a Searchable PDF url.")
                return

            self.root.after(0, update_ui, "Downloading processed PDF...")
            pdf_response = requests.get(pdf_url, timeout=120)
            
            if pdf_response.status_code == 200:
                with open(output_pdf, "wb") as f:
                    f.write(pdf_response.content)
                self.root.after(0, self.on_success, output_pdf)
            else:
                self.root.after(0, self.on_error, f"Failed to download PDF. Code: {pdf_response.status_code}")

        except Exception:
            import traceback
            err = traceback.format_exc()
            self.root.after(0, self.on_error, f"Network or Cloud Error:\n{err}")

    def do_local_ocr(self, input_pdf, output_pdf):
        try:
            doc = fitz.open(input_pdf)
            total = len(doc)
            
            # Safe concurrency bounds
            workers = min(os.cpu_count() or 4, 8)

            def process_page(img_bytes, w, h):
                img = Image.frombytes("RGB", [w, h], img_bytes)
                return pytesseract.image_to_data(
                    img, lang='eng', config='--psm 1 --oem 3', output_type=pytesseract.Output.DICT
                )

            executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
            futures = {}
            completed = 0

            # helper to apply text inline natively mapping exact bounding boxes
            def apply_ready_page(idx, data):
                page = doc[idx]
                scale = 72.0 / 200.0  
                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    if not text:
                        continue
                    
                    x = data['left'][i] * scale
                    y = data['top'][i] * scale
                    w = data['width'][i] * scale
                    h = data['height'][i] * scale
                    
                    point = fitz.Point(x, y + h - (h * 0.2))
                    fontsize = h * 0.8 if h > 0 else 10
                    
                    try:
                        page.insert_text(point, text, fontsize=fontsize, render_mode=3)
                    except Exception:
                        pass

                def update_ui():
                    self.lbl.config(text=f"Processed page {completed} / {total}...")
                    self.bar.config(mode="determinate")
                    self.bar.stop()
                    self.bar["value"] = (completed / total) * 100
                self.root.after(0, update_ui)

            for i in range(total):
                while len(futures) >= workers * 2:
                    done, _ = concurrent.futures.wait(futures.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                    for f in done:
                        idx = futures.pop(f)
                        completed += 1
                        apply_ready_page(idx, f.result())

                page = doc[i]
                pix = page.get_pixmap(dpi=200, alpha=False)
                f = executor.submit(process_page, pix.samples, pix.width, pix.height)
                futures[f] = i

            for f in concurrent.futures.as_completed(futures.keys()):
                idx = futures[f]
                completed += 1
                apply_ready_page(idx, f.result())

            executor.shutdown(wait=True)

            doc.save(output_pdf, garbage=4, deflate=True)
            doc.close()

            self.root.after(0, self.on_success, output_pdf)

        except Exception:
            import traceback
            err = traceback.format_exc()
            self.root.after(0, self.on_error, err)

    def on_success(self, output_pdf):
        self.prog_win.destroy()
        if sys.platform == 'win32':
            import subprocess
            subprocess.run(f'explorer /select,"{os.path.normpath(output_pdf)}"')
        # Restore app instead of closing completely, allowing multiple runs!
        self.input_pdf.set("")
        self.lbl_file.config(text="No file selected...", foreground="gray")
        self.root.deiconify()
        messagebox.showinfo("OCR Complete", "Your document has been successfully processed and saved!")

    def on_error(self, message):
        self.prog_win.destroy()
        messagebox.showerror("OCR Error", f"Fatal Exception:\n\n{message}")
        self.root.deiconify()

if __name__ == "__main__":
    OCRApp().root.mainloop()
