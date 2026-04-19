import threading
import os
import sys
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

from ocr_engine import process_pdf, find_tesseract

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BASE = TkinterDnD.Tk if DND_AVAILABLE else ctk.CTk

class OCRApp(BASE):
    def __init__(self):
        super().__init__()
        self.title("DocumentLens OCR App")
        self.geometry("700x500")
        self.resizable(False, False)

        # Output folder inherently defaults to user's 'Downloads'
        self.default_downloads = str(Path.home() / "Downloads")
        os.makedirs(self.default_downloads, exist_ok=True)
        self.input_path = None
        self.is_processing = False

        if not find_tesseract():
            self._handle_missing_tesseract()
        else:
            self._build_ui()

    def _handle_missing_tesseract(self):
        messagebox.showerror(
            "Missing Dependency",
            "Tesseract OCR is not found. Please install it from:\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
            "The app will now close."
        )
        self.destroy()
        sys.exit(1)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # TITLE / HEADER
        self.header_label = ctk.CTkLabel(self, text="Local PDF OCR Scanner", font=ctk.CTkFont(size=24, weight="bold"))
        self.header_label.grid(row=0, column=0, pady=(20, 10), sticky="ew")

        # DROP ZONE OR FILE BROWSE
        self.drop_frame = ctk.CTkFrame(self, corner_radius=12, border_width=2, border_color="#3a7ebf", fg_color="transparent")
        self.drop_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew", ipady=20)
        self.drop_frame.grid_columnconfigure(0, weight=1)

        drop_msg = "Drag & Drop PDF Here\n— or click below —" if DND_AVAILABLE else "Click below to select PDF"
        self.drop_label = ctk.CTkLabel(self.drop_frame, text=drop_msg, font=ctk.CTkFont(size=16))
        self.drop_label.grid(row=0, column=0, pady=(15, 10))

        self.browse_btn = ctk.CTkButton(self.drop_frame, text="Browse File", width=160, command=self._browse_pdf)
        self.browse_btn.grid(row=1, column=0, pady=(0, 15))

        if DND_AVAILABLE:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)

        # SELECTED FILE LABEL
        self.file_label = ctk.CTkLabel(self, text="No file selected", font=ctk.CTkFont(size=13, slant="italic"))
        self.file_label.grid(row=2, column=0, padx=40, sticky="n")

        # PROGRESS BAR
        self.progress = ctk.CTkProgressBar(self, mode="determinate")
        self.progress.grid(row=3, column=0, padx=40, pady=15, sticky="ew")
        self.progress.set(0.0)

        # STATUS BOX
        self.log_box = ctk.CTkTextbox(self, state="disabled", height=100, font=ctk.CTkFont(family="Courier", size=12))
        self.log_box.grid(row=4, column=0, padx=40, pady=(0, 15), sticky="nsew")

        # RUN BUTTON
        self.run_btn = ctk.CTkButton(
            self, text="Run OCR", fg_color="#2b8a3e", hover_color="#185624",
            font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self._start_ocr, state="disabled"
        )
        self.run_btn.grid(row=5, column=0, padx=40, pady=(0, 20), sticky="ew")
        
        self._log("Ready. Select a PDF file to begin.")

    def _log(self, message: str):
        def append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, append)

    def _set_progress(self, val: float):
        self.after(0, lambda: self.progress.set(val / 100))

    def _browse_pdf(self):
        if self.is_processing: return
        path = filedialog.askopenfilename(title="Select PDF", filetypes=[("PDF files", "*.pdf")])
        if path:
            self._set_input(path)

    def _on_drop(self, event):
        if self.is_processing: return
        path = event.data.strip().strip("{}")
        if path.lower().endswith(".pdf"):
            self._set_input(path)
        else:
            messagebox.showerror("Error", "Please drop a .pdf file.")

    def _set_input(self, path):
        self.input_path = path
        self.file_label.configure(text=f"Ready: {os.path.basename(path)}")
        self.run_btn.configure(state="normal")
        self.progress.set(0)
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log("Output folder resolved: " + self.default_downloads)
        self._log(f"PDF loaded. Press 'Run OCR' to begin processing.")

    def _start_ocr(self):
        if not self.input_path: return
        self.is_processing = True
        self.run_btn.configure(state="disabled", text="Processing...")
        self.browse_btn.configure(state="disabled")
        
        in_path = self.input_path
        stem = os.path.splitext(os.path.basename(in_path))[0]
        out_name = f"{stem}_ocr.pdf"
        out_path = os.path.join(self.default_downloads, out_name)

        threading.Thread(target=self._ocr_worker, args=(in_path, out_path), daemon=True).start()

    def _ocr_worker(self, in_path, out_path):
        self._log(f"Starting OCR...")
        try:
            process_pdf(
                input_path=in_path,
                output_path=out_path,
                progress_callback=self._set_progress,
                log_callback=self._log,
                lang="eng",
                dpi=300
            )
            self._finish_success(out_path)
        except Exception as e:
            self._finish_error(str(e))

    def _finish_success(self, out_path):
        def _cb():
            self.progress.set(1.0)
            self.is_processing = False
            self.browse_btn.configure(state="normal")
            
            # Reset button
            self.run_btn.configure(state="normal", text="Run OCR")
            
            ans = messagebox.askyesno("Success", f"File successfully saved to:\n{out_path}\n\nOpen Downloads folder now?")
            if ans:
                if sys.platform == "win32":
                    os.startfile(self.default_downloads)
        self.after(0, _cb)
        
    def _finish_error(self, message=None):
        def _cb():
            self.progress.set(0)
            self.is_processing = False
            self.browse_btn.configure(state="normal")
            self.run_btn.configure(state="normal", text="Run OCR")
            if message:
                self._log(f"Error: {message}")
                messagebox.showerror("OCR failed", message)
        self.after(0, _cb)

if __name__ == "__main__":
    app = OCRApp()
    app.mainloop()
