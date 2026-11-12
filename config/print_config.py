import os
import time
import subprocess
from typing import Optional, Tuple, List, Union

from PIL import Image, ImageWin

import win32print
import win32api
import win32ui
import win32con

from config.firebase_config import db

# ---- Configuration ----
PDF_RENDER_DPI = 200  # Fallback DPI if device DPI cannot be queried
# Default to fitting within the printable area to avoid clipping on Letter/A4
PRINT_SCALE_MODE = 'fit'

# Paper size definitions in tenths of a millimeter
PAPER_SIZES = {
    'letter': {
        'width': 2159,   # 215.9mm
        'height': 2794,  # 279.4mm
    },
    'a4': {
        'width': 2100,   # 210mm
        'height': 2970,  # 297mm
    }
}

def get_paper_config(page_size: str) -> dict:
    """Get paper configuration based on page size."""
    ps = str(page_size).lower()
    if ps.startswith('letter'):
        return PAPER_SIZES['letter']
    return PAPER_SIZES['a4']


def _project_root_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_downloads_dir() -> str:
    """Return the downloads directory path, ensuring it exists."""
    downloads_dir = os.path.join(_project_root_dir(), 'downloads')
    os.makedirs(downloads_dir, exist_ok=True)
    return downloads_dir


# -------------------- Printer detection and status --------------------

def get_available_printers() -> List[str]:
    """Get all available printers (any model/brand).
    Returns a list of printer names sorted in reverse order (non-copy printers first).
    """
    try:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags)
        printer_names = [p[2] for p in printers]
        
        # Sort printers: prioritize ones without "(Copy" in the name, then alphabetically
        # This ensures "Canon TS200 series" comes before "Canon TS200 series (Copy 1)"
        printer_names.sort(key=lambda x: (x.lower().count('(copy'), x.lower()))
        
        print(f"[DEBUG] Found {len(printer_names)} available printer(s): {printer_names}")
        return printer_names
    except Exception as e:
        print(f"[ERROR] Failed to enumerate printers: {e}")
    return []


def get_printer_for_page_size(page_size: str) -> Optional[str]:
    """Get the appropriate printer based on page size.
    A4 paper size -> Printer 1 (first available printer)
    Letter paper size -> Printer 2 (second available printer)
    Works with any printer model/brand.
    Returns the printer name or None if not available.
    """
    available_printers = get_available_printers()
    
    if not available_printers:
        print("[ERROR] No printers found.")
        return None
    
    # Sort printers to ensure consistent ordering
    available_printers.sort()
    
    page_size_lower = str(page_size).lower()
    
    if page_size_lower.startswith('a4'):
        # A4 -> Use first printer (Printer 1)
        if len(available_printers) >= 1:
            printer = available_printers[0]
            print(f"[INFO] A4 paper size -> Using Printer 1: {printer}")
            return printer
        else:
            print("[ERROR] Printer 1 (A4) not available.")
            return None
    else:
        # Letter -> Use second printer (Printer 2)
        if len(available_printers) >= 2:
            printer = available_printers[1]
            print(f"[INFO] Letter paper size -> Using Printer 2: {printer}")
            return printer
        else:
            print("[ERROR] Printer 2 (Letter) not available. At least 2 printers are required.")
            return None


def get_default_printer() -> Optional[str]:
    """Get the default printer, prefer any available printer.
    Returns None if no printers are available.
    """
    try:
        # Try the Windows default printer first
        try:
            printer_name = win32print.GetDefaultPrinter()
            if printer_name:
                print(f"[INFO] Using default printer: {printer_name}")
                return printer_name
        except Exception:
            pass

        # Enumerate local and connected printers
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        printers = win32print.EnumPrinters(flags)
        names = [p[2] for p in printers]
        print(f"[DEBUG] Available printers: {names}")

        # Fallback to the first available printer
        if printers:
            printer = printers[0][2]
            print(f"[INFO] Using first available printer: {printer}")
            return printer
    except Exception as e:
        print(f"[ERROR] Failed to get printer: {e}")

    return None


def check_printer_status(printer_name: str) -> Tuple[bool, str]:
    """Check if the printer is ready and available."""
    try:
        ph = win32print.OpenPrinter(printer_name)
        if ph:
            try:
                info = win32print.GetPrinter(ph, 2)
                status = info.get('Status', 0)
            finally:
                win32print.ClosePrinter(ph)
            if status == 0:
                return True, "Printer ready"
            return False, f"Printer status code: {status}"
        return False, "Could not open printer"
    except Exception as e:
        return False, f"Printer check error: {e}"


# -------------------- Rendering and GDI printing --------------------

def _create_printer_dc_with_color(printer_name: str, color_mode: Optional[str] = None, page_size: Optional[str] = None):
    """Create a printer DC, honoring color mode and paper size through DEVMODE when possible.
    color_mode: 'bw' for monochrome, 'colored' for color, or None for printer default.
    page_size: 'A4', 'Letter', etc. (best effort)
    """
    hdc = win32ui.CreateDC()
    try:
        ph = win32print.OpenPrinter(printer_name)
        try:
            pinfo = win32print.GetPrinter(ph, 2)
            try:
                devmode = win32print.DocumentProperties(None, ph, printer_name, None, None, 0)
            except Exception:
                devmode = pinfo.get('pDevMode')

            if devmode is not None:
                try:
                    # Color mode
                    if color_mode is not None:
                        try:
                            devmode.Fields |= win32con.DM_COLOR
                        except Exception:
                            pass
                        devmode.Color = 1 if color_mode == 'bw' else 2  # 1 mono, 2 color

                    # Disable ICM if possible
                    try:
                        devmode.Fields |= win32con.DM_ICMMETHOD
                        devmode.ICMMethod = 1  # DMICMMETHOD_NONE
                    except Exception:
                        pass

                    # Paper size (best effort)
                    if page_size:
                        try:
                            try:
                                devmode.Fields |= win32con.DM_ORIENTATION
                                devmode.Orientation = 1  # Portrait
                            except Exception:
                                pass
                            devmode.Fields |= win32con.DM_PAPERSIZE
                            paper_config = get_paper_config(page_size or 'a4')
                            
                            if str(page_size).lower().startswith('letter'):
                                devmode.PaperSize = 1  # DMPAPER_LETTER
                            else:
                                devmode.PaperSize = 9  # DMPAPER_A4
                                
                            try:
                                # Set paper dimensions
                                devmode.Fields |= win32con.DM_PAPERWIDTH | win32con.DM_PAPERLENGTH
                                devmode.PaperWidth = paper_config['width']
                                devmode.PaperLength = paper_config['height']
                                
                                # Set to portrait orientation
                                devmode.Fields |= win32con.DM_ORIENTATION
                                devmode.Orientation = win32con.DMORIENT_PORTRAIT
                                
                                # Set printing quality
                                devmode.Fields |= win32con.DM_PRINTQUALITY
                                devmode.PrintQuality = win32con.DMRES_HIGH
                            except Exception:
                                pass
                        except Exception:
                            pass

                    # Set high quality printing
                    try:
                        devmode.Fields |= win32con.DM_PRINTQUALITY | win32con.DM_MEDIATYPE
                        devmode.PrintQuality = win32con.DMRES_HIGH
                        # Try to set best available media type
                        devmode.MediaType = 1  # DMMEDIA_STANDARD
                    except Exception:
                        pass

                    # Validate/apply devmode if driver supports it
                    try:
                        devmode = win32print.DocumentProperties(
                            None, ph, printer_name, devmode, devmode,
                            win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER
                        )
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    # Preferred path when available
                    hdc.CreateDC("WINSPOOL", printer_name, None, devmode)
                except Exception:
                    # Fallback path on some pywin32 builds
                    hdc.CreatePrinterDC(printer_name)
                try:
                    hdc.ResetDC(devmode)
                except Exception:
                    pass
            else:
                hdc.CreatePrinterDC(printer_name)
        finally:
            win32print.ClosePrinter(ph)
    except Exception:
        try:
            hdc.CreatePrinterDC(printer_name)
        except Exception:
            hdc.CreateDC("WINSPOOL", printer_name, None, None)
    return hdc


def render_pdf_to_images(file_path: str, dpi: int = PDF_RENDER_DPI, dpi_x: Optional[int] = None,
                         dpi_y: Optional[int] = None, grayscale: bool = False,
                         page_range: Optional[str] = None) -> Tuple[bool, Union[List[Image.Image], str]]:
    """Render a PDF to a list of PIL Images using PyMuPDF.
    Supports page ranges formatted like '1-3'.
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        images: List[Image.Image] = []

        # Determine zoom factors to reach target DPI
        if dpi_x is not None and dpi_y is not None:
            zoom_x = float(dpi_x) / 72.0
            zoom_y = float(dpi_y) / 72.0
        else:
            zoom = (dpi or PDF_RENDER_DPI) / 72.0
            zoom_x = zoom_y = zoom
        mat = fitz.Matrix(zoom_x, zoom_y)

        # Build page index list
        total_pages = len(doc)
        page_indices = list(range(total_pages))
        if page_range and page_range != 'all' and '-' in str(page_range):
            try:
                start_s, end_s = str(page_range).split('-')
                start_i = max(1, int(start_s.strip()))
                end_i = min(total_pages, int(end_s.strip()))
                if start_i <= end_i:
                    page_indices = list(range(start_i - 1, end_i))
                    print(f"[DEBUG] Rendering pages {start_i}-{end_i} (0-based {start_i-1}-{end_i-1})")
            except Exception as e:
                print(f"[DEBUG] Invalid page range '{page_range}', using all pages. {e}")

        for idx in page_indices:
            page = doc.load_page(idx)
            if grayscale:
                try:
                    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
                except Exception:
                    pix = page.get_pixmap(matrix=mat, alpha=False)
            else:
                pix = page.get_pixmap(matrix=mat, alpha=False)

            if grayscale or getattr(pix, 'n', 3) == 1:
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
            else:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        doc.close()
        return True, images
    except Exception as e:
        return False, f"PDF render error: {e}"


def print_images_via_gdi(images: List[Image.Image], printer_name: str, render_dpi: Tuple[int, int],
                         scale_mode: str = PRINT_SCALE_MODE, color_mode: Optional[str] = None,
                         page_size: Optional[str] = None, doc_name: Optional[str] = None) -> Tuple[bool, str]:
    """Send PIL images to the printer using GDI, honoring printable area and scaling mode."""
    try:
        hdc = _create_printer_dc_with_color(printer_name, color_mode=color_mode, page_size=page_size)
        hdc.StartDoc(doc_name or "Print Job")

        # Device caps
        HORZRES = 8; VERTRES = 10
        LOGPIXELSX = 88; LOGPIXELSY = 90
        PHYSICALOFFSETX = 112; PHYSICALOFFSETY = 113
        PHYSICALWIDTH = 110; PHYSICALHEIGHT = 111

        page_w = hdc.GetDeviceCaps(HORZRES)
        page_h = hdc.GetDeviceCaps(VERTRES)
        dev_dpi_x = hdc.GetDeviceCaps(LOGPIXELSX)
        dev_dpi_y = hdc.GetDeviceCaps(LOGPIXELSY)
        off_x = hdc.GetDeviceCaps(PHYSICALOFFSETX)
        off_y = hdc.GetDeviceCaps(PHYSICALOFFSETY)
        phys_w = hdc.GetDeviceCaps(PHYSICALWIDTH)
        phys_h = hdc.GetDeviceCaps(PHYSICALHEIGHT)
        
        print(f"[DEBUG] DeviceCaps phys=({phys_w}x{phys_h}) printable=({page_w}x{page_h}) offsets=({off_x},{off_y}) dpi=({dev_dpi_x},{dev_dpi_y}) page_size={page_size}")

        for img in images:
            hdc.StartPage()
            iw, ih = img.size

            if isinstance(render_dpi, tuple):
                render_dpi_x, render_dpi_y = render_dpi
            else:
                render_dpi_x = render_dpi_y = int(render_dpi)

            # Calculate dimensions at actual size - no scaling
            # Simply convert from render DPI to printer DPI
            dest_w = int(round(iw * (dev_dpi_x / float(render_dpi_x))))
            dest_h = int(round(ih * (dev_dpi_y / float(render_dpi_y))))

            # Adjust positioning based on paper size
            # Letter paper needs slight right adjustment, A4 stays at edge
            if page_size and str(page_size).lower().startswith('letter'):
                x = -110  # Letter: move left by 110 units (less than A4)
                y = -60  # Move up by 60 units
            else:
                x = -70  # A4: move left by 70 units
                y = -60  # Move up by 60 units
            
            print(f"[DEBUG] Print settings: paper={page_size}, color_mode={color_mode}")
            print(f"[DEBUG] Dimensions: content=({iw}x{ih}@{render_dpi_x}dpi), output=({dest_w}x{dest_h}@{dev_dpi_x}dpi)")
            print(f"[DEBUG] Printable area: ({page_w}x{page_h}), Offset: ({off_x}, {off_y}), Position: ({x}, {y})")

            # Handle image mode conversion properly for B&W printing
            if color_mode == 'bw':
                if img.mode not in ('L', 'LA'):
                    # Convert to grayscale without dithering to preserve exact tones
                    img = img.convert('L')
                
                # Enhance contrast and remove background tint for B&W printing
                from PIL import ImageEnhance, ImageOps
                
                # First, auto-level the image to maximize contrast
                # This ensures whites are pure white and blacks are pure black
                img = ImageOps.autocontrast(img, cutoff=0)
                
                # Increase contrast to make text darker and backgrounds whiter
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.3)  # 30% more contrast
                
                # Increase brightness slightly to ensure whites are truly white
                brightness_enhancer = ImageEnhance.Brightness(img)
                img = brightness_enhancer.enhance(1.05)  # 5% brighter
                
                # Apply sharpness to make text crisper
                sharpness_enhancer = ImageEnhance.Sharpness(img)
                img = sharpness_enhancer.enhance(1.2)  # 20% sharper
                
                print(f"[DEBUG] B&W mode: Image enhanced (mode={img.mode}, contrast+30%, brightness+5%, sharpness+20%)")
            else:
                # For color printing, ensure RGB mode
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                print(f"[DEBUG] Color mode: Image in RGB (mode={img.mode})")
            
            dib = ImageWin.Dib(img)
            dib.draw(hdc.GetHandleOutput(), (x, y, x + dest_w, y + dest_h))
            hdc.EndPage()

        hdc.EndDoc()
        hdc.DeleteDC()
        return True, "GDI image print successful"
    except Exception as e:
        try:
            hdc.EndDoc()
        except Exception:
            pass
        try:
            hdc.DeleteDC()
        except Exception:
            pass
        return False, f"GDI print error: {e}"


def print_pdf_via_gdi(file_path: str, printer_name: str, dpi: int = PDF_RENDER_DPI,
                      color_mode: Optional[str] = None, page_size: Optional[str] = None,
                      page_range: Optional[str] = None, scale_mode: str = 'actual', doc_name: Optional[str] = None) -> Tuple[bool, str]:
    """Render a PDF to images and print with GDI. Respects page_range."""
    # Determine printer/device DPI for accurate scaling
    try:
        hdc = _create_printer_dc_with_color(printer_name, color_mode=color_mode, page_size=page_size)
        LOGPIXELSX = 88; LOGPIXELSY = 90
        dev_dpi_x = hdc.GetDeviceCaps(LOGPIXELSX)
        dev_dpi_y = hdc.GetDeviceCaps(LOGPIXELSY)
        hdc.DeleteDC()
        render_dpi = (dev_dpi_x, dev_dpi_y)
    except Exception:
        render_dpi = (dpi or PDF_RENDER_DPI, dpi or PDF_RENDER_DPI)

    ok, result = render_pdf_to_images(
        file_path,
        dpi=max(render_dpi),
        dpi_x=render_dpi[0],
        dpi_y=render_dpi[1],
        grayscale=(color_mode == 'bw'),
        page_range=page_range
    )
    if not ok:
        return False, f"Failed to render PDF: {result}"

    return print_images_via_gdi(
        result,
        printer_name,
        render_dpi=render_dpi,
        scale_mode=scale_mode,  # Use the provided scale_mode parameter
        color_mode=color_mode,
        page_size=page_size,
        doc_name=doc_name
    )


# -------------------- High-level job printing --------------------

def _update_job_status(job_id: str, status: str) -> None:
    try:
        job_ref = db.reference(f'jobs/print_jobs/{job_id}')
        job_ref.update({'status': status, 'updated_at': time.time()})
        detail_ref = db.reference(f'jobs/print_jobs/{job_id}/details/0')
        detail_ref.update({'status': status, 'updated_at': time.time()})
    except Exception as e:
        print(f"[ERROR] Firebase update failed: {e}")


def _wait_for_spool_completion(printer_name: str, doc_name: str, poll_interval: float = 1.0, timeout: float = 600.0) -> bool:
    try:
        ph = win32print.OpenPrinter(printer_name)
        try:
            start = time.time()
            while True:
                try:
                    jobs = win32print.EnumJobs(ph, 0, -1, 1)
                except Exception:
                    jobs = []
                still_there = False
                for j in jobs:
                    try:
                        if j.get('pDocument') == doc_name:
                            still_there = True
                            break
                    except Exception:
                        continue
                if not still_there:
                    return True
                if (time.time() - start) > timeout:
                    return False
                time.sleep(poll_interval)
        finally:
            win32print.ClosePrinter(ph)
    except Exception:
        return False


def print_file_for_job(job_id: str) -> Tuple[bool, str]:
    """Main print function used by the app. Reads job details from Firebase and prints.
    Supports auto printer selection based on page size, page ranges, and copies.
    - A4 paper size -> Printer 1
    - Letter paper size -> Printer 2
    """
    try:
        print(f"[DEBUG] print_file_for_job called with job_id: {job_id}")

        job_ref = db.reference(f'jobs/print_jobs/{job_id}')
        job_data = job_ref.get()
        if not job_data or 'details' not in job_data or not job_data['details']:
            _update_job_status(job_id, "failed")
            return False, "Invalid job data"

        details = job_data['details'][0]
        file_name = details.get('file_name')
        color_mode = details.get('color_mode', 'colored')  # 'bw' or 'colored'
        # Default to Letter to align with your printer settings if unspecified
        page_size = details.get('page_size') or 'Letter'
        page_range = details.get('page_range', 'all')
        num_copies = int(details.get('num_copies', 1) or 1)
        if num_copies < 1:
            num_copies = 1

        if not file_name:
            _update_job_status(job_id, "failed")
            return False, "No file name in job details"

        # Select printer based on page size
        printer_name = get_printer_for_page_size(page_size)
        if not printer_name:
            _update_job_status(job_id, "failed")
            return False, "No printers available"

        ready, msg = check_printer_status(printer_name)
        if not ready:
            _update_job_status(job_id, "failed")
            return False, f"Printer not ready: {msg}"

        # Build local file path
        downloads_dir = get_downloads_dir()
        file_path = os.path.abspath(os.path.join(downloads_dir, os.path.basename(file_name)))
        print(f"[DEBUG] Looking for file at: {file_path}")

        if not os.path.exists(file_path):
            # Try alternative paths from job details
            local_path = details.get('local_path') or details.get('file_path')
            if local_path and os.path.exists(local_path):
                file_path = os.path.abspath(local_path)
                print(f"[DEBUG] Using local_path from job details: {file_path}")
            else:
                # Attempt to download if URL provided
                download_url = details.get('download_url')
                if not download_url:
                    _update_job_status(job_id, "failed")
                    return False, "File not found and no download URL provided"
                print(f"[INFO] Downloading file from: {download_url}")
                try:
                    import requests
                    temp_path = f"{file_path}.download"
                    with requests.get(download_url, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        with open(temp_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                        os.replace(temp_path, file_path)
                    else:
                        _update_job_status(job_id, "failed")
                        return False, "Download failed or file empty"
                except Exception as e:
                    _update_job_status(job_id, "failed")
                    return False, f"Download failed: {e}"

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            _update_job_status(job_id, "failed")
            return False, "File not found or is empty"

        _update_job_status(job_id, "printing")

        # Decide printing path
        is_pdf = file_path.lower().endswith('.pdf')
        if not is_pdf:
            # Try converting DOCX to PDF when possible
            try:
                import pythoncom
                from docx2pdf import convert
                
                # Initialize COM for this thread
                pythoncom.CoInitialize()
                try:
                    pdf_path = file_path + ".pdf"
                    convert(file_path, pdf_path)
                    file_path = pdf_path
                    is_pdf = True
                    print(f"[INFO] Converted to PDF: {pdf_path}")
                finally:
                    # Uninitialize COM
                    pythoncom.CoUninitialize()
            except Exception as e:
                print(f"[WARNING] DOCX to PDF conversion failed: {e}")
                if color_mode == 'bw':
                    # We cannot enforce B/W reliably via shell printing
                    _update_job_status(job_id, "failed")
                    return False, f"Conversion to PDF failed; cannot enforce B/W via fallback. {e}"
                # Otherwise proceed with shell/command printing below

        base_doc_name = f"JOB-{job_id}-{os.path.basename(file_path)}"
        doc_names: List[str] = []

        if is_pdf:
            for copy_idx in range(num_copies):
                dn = f"{base_doc_name}-copy{copy_idx + 1}"
                ok, msg = print_pdf_via_gdi(
                    file_path,
                    printer_name,
                    color_mode=color_mode,
                    page_size=page_size,
                    page_range=page_range,
                    scale_mode='actual',
                    doc_name=dn
                )
                if not ok:
                    _update_job_status(job_id, "failed")
                    return False, f"Failed to print copy {copy_idx + 1}: {msg}"
                doc_names.append(dn)
        else:
            for copy_idx in range(num_copies):
                ok, msg = _print_file_with_shellexecute(file_path, printer_name)
                if not ok:
                    ok, msg = _print_file_with_command(file_path, printer_name)
                if not ok:
                    _update_job_status(job_id, "failed")
                    return False, f"Failed to print copy {copy_idx + 1}: {msg}"
            doc_names = [os.path.basename(file_path)]

        for dn in doc_names:
            _wait_for_spool_completion(printer_name, dn, poll_interval=1.0, timeout=max(600.0, float(num_copies) * 300.0))

        _update_job_status(job_id, "completed")
        return True, "Print job completed"

    except Exception as e:
        _update_job_status(job_id, "failed")
        return False, f"Unexpected error: {e}"


# -------------------- Fallback helpers --------------------

def _print_file_with_shellexecute(file_path: str, printer_name: str) -> Tuple[bool, str]:
    try:
        print(f"[DEBUG] ShellExecute print: {file_path} -> {printer_name}")
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return False, f"File not found: {abs_path}"
        result = win32api.ShellExecute(0, "print", abs_path, f'/d:"{printer_name}"', ".", 0)
        if result > 32:
            return True, "ShellExecute sent"
        return False, f"ShellExecute failed code {result}"
    except Exception as e:
        return False, f"ShellExecute error: {e}"


def _print_file_with_command(file_path: str, printer_name: str) -> Tuple[bool, str]:
    try:
        print(f"[DEBUG] print command: {file_path} -> {printer_name}")
        cmd = ['print', '/D:' + printer_name, file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            return True, "print command ok"
        return False, f"print command failed: {res.stderr}"
    except Exception as e:
        return False, f"Command print error: {e}"
