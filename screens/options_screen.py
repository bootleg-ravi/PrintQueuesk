# screens/options_screen.py

import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
import fitz  # PyMuPDF
import sys
import io
from docx2pdf import convert
import tempfile
import os
import time
import threading
from config.firebase_config import db
from config.arduino_config import ArduinoCoinAcceptor

# Store image references globally to prevent garbage collection
image_refs = {}

class OptionsScreen(tk.Frame):
    def fetch_and_set_color_prices(self):
        # Fetch prices from Firebase and update color radio button labels
        black_price, color_price = self.fetch_latest_prices()
        try:
            self.colored_price = float(color_price) if color_price is not None else 0.0
        except (TypeError, ValueError):
            self.colored_price = 0.0
        try:
            self.bw_price = float(black_price) if black_price is not None else 0.0
        except (TypeError, ValueError):
            self.bw_price = 0.0
        # Update radio button labels if they exist
        if hasattr(self, 'colored_radio') and hasattr(self, 'bw_radio'):
            self.colored_radio.config(text=f"Colored (₱{self.colored_price:.2f})")
            self.bw_radio.config(text=f"Black & White (₱{self.bw_price:.2f})")
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self._preview_cache = {}
        self.image_refs = {}
        # Keep a converted PDF path for DOC/DOCX files to avoid repeated conversions
        self._converted_pdf_path = None
        self._converted_from_docx = False
        # Loading overlay holder
        self._loading_overlay = None
        # Make scale_factor an instance attribute, available to all methods
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.scale_factor = min(screen_width / 1920, screen_height / 1080)
        # Guard to avoid redundant preview updates while changing widgets programmatically
        self._suppress_preview = False
        # Timer variables for debouncing
        self._color_update_timer = None
        self._page_size_update_timer = None
        self._scale_mode_update_timer = None
        self._scale_update_timer = None
        self.preview_page = {"num": 1, "max": 1}  # Ensure preview_page is always initialized
        self.create_widgets()
        # Idle timer for auto-return to home
        self._idle_timer = None
        # Bind events to reset global idle timer when user is active
        self.bind_all('<Any-KeyPress>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Any-Button>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Motion>', lambda e: self.controller._reset_global_idle_timer())

    def load_data(self, data):
        """Load job data and initialize the UI. Uses a lightweight overlay and defers heavy preview rendering."""
        # Ensure any HomeScreen transition overlay is hidden when entering Options
        try:
            home_frame = self.controller.frames.get("HomeScreen")
            if home_frame and hasattr(home_frame, 'hide_transition_screen'):
                home_frame.hide_transition_screen()
        except Exception:
            pass

        self.file_name = data.get('file_name')
        self.file_path = data.get('file_path')
        self.total_pages = data.get('total_pages')
        self.job_id = data.get('job_id')
        # Reset caches only if file changed; speeds up returning from Summary
        if not hasattr(self, '_last_file_path') or self._last_file_path != self.file_path:
            self._preview_cache = {}
            self._converted_pdf_path = None
            self._converted_from_docx = False
            self._cached_page_count = None
        self._last_file_path = self.file_path
        
        # Reset UI elements with new data
        # Truncate file name for display if too long
        display_file_name = self.file_name
        if len(display_file_name) > 55:
            display_file_name = display_file_name[:52] + "..."
        self.file_name_value.config(text=display_file_name)
        self.total_pages_value.config(text=str(self.total_pages))
        
        # Reset preserved options or set defaults
        self.preserved_data = data.get('preserved_options', {})
        self.pages_var.set(self.preserved_data.get('pages_range_mode', 'all'))
        self.color_var.set(self.preserved_data.get('color_mode', 'colored'))
        self.page_size_var.set(self.preserved_data.get('page_size', 'A4'))
        self.scale_var.set(self.preserved_data.get('scale_mode', 'fit'))
        self.copies_var.set(str(self.preserved_data.get('num_copies', 1)))
        
        page_range = self.preserved_data.get('page_range', f'1-{self.total_pages}')
        if page_range and page_range != "all" and "-" in page_range:
            start, end = page_range.split('-')
            self.start_page_var.set(start)
            self.end_page_var.set(end)
        else:
            self.start_page_var.set("1")
            self.end_page_var.set(str(self.total_pages))

        self.manual_scale_var.set(str(self.preserved_data.get('scale_percentage', 100)))

        self.toggle_page_range_inputs()
        self.toggle_manual_scale_inputs()
        
        # Initialize preview state only if not set yet
        if not hasattr(self, 'preview_page'):
            self.preview_page = {"num": 1, "max": 1}

        # Always render without showing any overlay window
        self.after(0, lambda: self.load_preview(1))

    def prewarm_preview(self, file_path, file_name):
        """Render and cache the first-page preview in the background to speed up initial load.
        Only performed for PDFs to avoid heavy DOC/DOCX conversions in background threads.
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return
            # Skip DOC/DOCX prewarm due to conversion complexity
            if file_name and file_name.lower().endswith((".doc", ".docx")):
                return
            # Use a worker thread to render the first page bitmap; Tkinter image creation remains on main thread
            def _worker():
                try:
                    pdf_document = fitz.open(file_path)
                    if pdf_document.page_count < 1:
                        pdf_document.close()
                        return
                    page = pdf_document[0]
                    # Default zoom ~120 DPI
                    matrix = fitz.Matrix(120 / 72, 120 / 72)
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    if pix.n == 1:
                        base_img = Image.frombytes("L", [pix.width, pix.height], pix.samples).convert("RGB")
                    else:
                        base_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    pdf_document.close()
                    # Store in cache for page 1, color mode 'color', zoom 1.0 on main thread
                    cache_key = (1, 'color', 1.0)
                    self.after(0, lambda: self._preview_cache.__setitem__(cache_key, base_img))
                except Exception:
                    pass
            threading.Thread(target=_worker, daemon=True).start()
        except Exception:
            pass

    def show_loading_overlay(self, message="Loading…"):
        """Display a full-frame overlay to indicate loading without blocking the UI."""
        try:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                # Update message if already visible
                for child in self._loading_overlay.winfo_children():
                    if isinstance(child, tk.Label):
                        child.config(text=message)
                return
            overlay = tk.Frame(self, bg="white")
            overlay.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
            label = tk.Label(overlay, text=message, font=("Bebas Neue", max(24, int(40 * self.scale_factor))), bg="white", fg="#333")
            label.pack(expand=True)
            self._loading_overlay = overlay
            self.update_idletasks()
        except Exception:
            # Fail silently; overlay is a UX enhancement
            self._loading_overlay = None

    def hide_loading_overlay(self):
        try:
            if self._loading_overlay and self._loading_overlay.winfo_exists():
                self._loading_overlay.destroy()
        except Exception:
            pass
        finally:
            self._loading_overlay = None

    def fetch_latest_prices(self):
        prices_ref = db.reference('system/settings/print_prices')
        prices = prices_ref.order_by_child('updated_at').limit_to_last(1).get()
        latest = list(prices.values())[-1] if isinstance(prices, dict) else (prices[-1] if isinstance(prices, list) else None)
        return (latest.get('black_price'), latest.get('color_price')) if latest else (None, None)

    def save_print_job_details(self, page_range, color_mode, total_price, page_size, scale_mode, scale_percentage, num_copies):
        # Use NEW HIERARCHICAL STRUCTURE
        detail_ref = db.reference(f'jobs/print_jobs/{self.job_id}/details/0')
        detail_ref.update({
            'file_name': self.file_name,
            'total_pages': self.total_pages,
            'num_copies': num_copies,
            'page_range': page_range,
            'color_mode': color_mode,
            'total_price': total_price,
            'page_size': page_size,
            'scale_mode': scale_mode,
            'scale_percentage': scale_percentage,
            'status': 'configuring',
            'updated_at': time.time()
        })

    def is_payment_complete(self):
        # Returns True if payment is complete for the current job
        return getattr(self.controller.frames.get("PaymentScreen"), "printing_started", False)

    def start_printing(self):
        color_option = self.color_var.get()
        black_price, color_price = self.fetch_latest_prices()
        if black_price is None or color_price is None:
            messagebox.showerror("Error", "Failed to retrieve printing prices.")
            return

        price_per_page = black_price if color_option == "bw" else color_price
        
        actual_total = int(self.total_pages_value.cget("text"))
        pages_range = "all"
        if self.pages_var.get() == "range":
            try:
                start_page = int(self.start_page_var.get())
                end_page = int(self.end_page_var.get())
                if not (1 <= start_page <= end_page <= actual_total):
                    raise ValueError("Invalid page range.")
                pages_range = f"{start_page}-{end_page}"
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid page range: {e}")
                return

        num_copies = int(self.copies_var.get()) if self.copies_var.get().isdigit() and int(self.copies_var.get()) > 0 else 1
        
        total_pages_to_print = actual_total if pages_range == "all" else (end_page - start_page + 1)
        total_price = total_pages_to_print * price_per_page * num_copies
        
        scale_option = self.scale_var.get()
        scale_percentage = int(self.manual_scale_var.get()) if scale_option == "manual" else 100

        selected_page_size = self.page_size_var.get()
        normalized_page_size = 'Letter' if selected_page_size.lower().startswith('letter') else 'A4'
        num_copies = int(self.copies_var.get()) if hasattr(self, 'copies_var') else 1
        # Only allow paper feed after payment is complete
        # Remove all DC motor/paper feed logic from here.
        # Only handle UI and payment initiation in OptionsScreen.

        summary_data = {
            'file_name': self.file_name,
            'file_path': self.file_path,
            'total_pages': self.total_pages,
            'job_id': self.job_id,
            'pages_range': pages_range,
            'color_mode': color_option,
            'total_price': total_price,
            'num_copies': num_copies,
            'page_size': selected_page_size,
            'scale_mode': scale_option,
            'scale_percentage': scale_percentage,
            'pages_range_mode': self.pages_var.get() # Preserve radio button choice
        }
        self.controller.show_frame("SummaryScreen", data=summary_data)

    def create_widgets(self):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Use the instance attribute self.scale_factor
        # Fonts and Padding
        base_font = ("Arial", max(12, int(20 * self.scale_factor))) # Min font size
        section_font = ("Arial", max(14, int(24 * self.scale_factor)), "bold")
        button_font = ("Arial", max(16, int(26 * self.scale_factor)), "bold")
        side_pad = int(80 * self.scale_factor)
        between_pad = int(60 * self.scale_factor)

        main_frame = tk.Frame(self, bg="white")
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1, minsize=int(screen_width * 0.4)) # Give more space to preview
        main_frame.grid_columnconfigure(1, weight=1, minsize=int(screen_width * 0.4))
        main_frame.grid_rowconfigure(0, weight=1)

        # --- LEFT FRAME (PREVIEW) ---
        left_frame = tk.Frame(main_frame, bg="white")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(side_pad, between_pad))
        
        tk.Label(left_frame, text="File Preview", font=section_font, bg="white", fg="#333333").pack(pady=4)
        
        preview_container = tk.Frame(left_frame, bg="#e0e0e0", bd=2, relief="solid")  # Lighter gray background, thicker border
        preview_container.pack(fill="both", expand=True, pady=5)
        self.preview_canvas = tk.Canvas(preview_container, bg="#f5f5f5", highlightthickness=0)  # Light gray canvas background
        self.preview_canvas.pack(fill="both", expand=True, padx=10, pady=10)  # Added padding for better spacing
        
        # Page Navigation
        page_nav_frame = tk.Frame(left_frame, bg="white")
        page_nav_frame.pack(pady=10)
        
        self.page_nav_minus = tk.Button(page_nav_frame, text="←", command=lambda: self.update_preview_page(-1), font=base_font, bg="#b42e41", fg="white", width=4)
        self.page_nav_minus.pack(side="left", padx=5)
        
        self.page_nav_label = tk.Label(page_nav_frame, text="Page 1 of 1", font=base_font, bg="white")
        self.page_nav_label.pack(side="left", padx=10)
        
        self.page_nav_plus = tk.Button(page_nav_frame, text="→", command=lambda: self.update_preview_page(1), font=base_font, bg="#b42e41", fg="white", width=4)
        self.page_nav_plus.pack(side="left", padx=5)


        # --- RIGHT FRAME (OPTIONS) ---
        right_frame = tk.Frame(main_frame, bg="white")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(between_pad, side_pad))
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(2, weight=1) # Make the options_main_frame expand vertically

        # Logo and File Details
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, 'static', 'img', 'logo.png')
            print(f"Loading options logo from: {logo_path}")
            logo_img = Image.open(logo_path).resize((max(100, int(screen_width * 0.2)), max(30, int(screen_height*0.08))), Image.Resampling.LANCZOS)
            self.logo_tk = ImageTk.PhotoImage(logo_img)
            tk.Label(right_frame, image=self.logo_tk, bg="white").grid(row=0, column=0, pady=(10, 5), sticky="n")
        except Exception as e:
            print(f"Error loading options logo: {e}")
            pass

        file_details_frame = tk.Frame(right_frame, bg="white")
        file_details_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_details_frame.grid_columnconfigure(0, weight=0)
        file_details_frame.grid_columnconfigure(1, weight=1)

        tk.Label(file_details_frame, text="File Name:", font=base_font, bg="white", anchor="w").grid(row=0, column=0, sticky="w", padx=(0,5))
        self.file_name_value = tk.Label(file_details_frame, text="", font=base_font, bg="white", anchor="w")
        self.file_name_value.grid(row=0, column=1, sticky="w")
        tk.Label(file_details_frame, text="Total Pages:", font=base_font, bg="white", anchor="w").grid(row=1, column=0, sticky="w", padx=(0,5))
        self.total_pages_value = tk.Label(file_details_frame, text="", font=base_font, bg="white", anchor="w")
        self.total_pages_value.grid(row=1, column=1, sticky="w")
        
        # Options Container - Simple frame without scrolling
        options_main_frame = tk.Frame(right_frame, bg="white")
        options_main_frame.grid(row=2, column=0, sticky="nsew", pady=5)

        # Direct frame for options (no canvas, no scrolling)
        self.options_scrollable_frame = tk.Frame(options_main_frame, bg="#f5f5f5", padx=10, pady=10)
        self.options_scrollable_frame.pack(fill="both", expand=True)
        
        # Variables
        self.pages_var = tk.StringVar(value="all")
        self.color_var = tk.StringVar(value="colored")
        self.page_size_var = tk.StringVar(value="A4")
        self.scale_var = tk.StringVar(value="fit")
        self.copies_var = tk.StringVar(value="1")
        self.start_page_var = tk.StringVar(value="1")
        self.end_page_var = tk.StringVar(value="1")
        self.manual_scale_var = tk.StringVar(value="100")
        
        # Debounced preview updates
        self.color_var.trace_add('write', self._on_color_mode_change)
        self.page_size_var.trace_add('write', self._on_page_size_change)
        self.scale_var.trace_add('write', self._on_scale_mode_change)
        self.manual_scale_var.trace_add('write', self._on_manual_scale_change)
        self.start_page_var.trace_add('write', self._on_start_end_change)
        self.end_page_var.trace_add('write', self._on_start_end_change)


        # -- Option Sections within options_scrollable_frame --
        
        # Pages Section
        pages_section = self._create_section_frame(self.options_scrollable_frame, "Pages to Print", section_font)
        pages_section.pack(fill="x", pady=5)
        tk.Radiobutton(pages_section, text="All Pages", variable=self.pages_var, value="all", command=self.toggle_page_range_inputs, bg="#f9f9f9", font=base_font).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(pages_section, text="Page Range", variable=self.pages_var, value="range", command=self.toggle_page_range_inputs, bg="#f9f9f9", font=base_font).pack(anchor="w", padx=10, pady=2)
        
        self.page_range_frame = tk.Frame(pages_section, bg="#f9f9f9")
        self.page_range_frame.pack(anchor="w", padx=30, pady=5)

        # Start Page row
        tk.Label(self.page_range_frame, text="Start Page", bg="#f9f9f9", font=base_font).grid(row=0, column=0, padx=(0,10), pady=4, sticky="w")
        self.start_page_entry = tk.Entry(self.page_range_frame, textvariable=self.start_page_var, width=5, font=base_font, justify='center')
        self.start_page_entry.grid(row=0, column=1, padx=(0,10), pady=4, sticky="w")
        start_btns = tk.Frame(self.page_range_frame, bg="#f9f9f9")
        start_btns.grid(row=0, column=2, padx=(15,0), pady=4, sticky="w")
        self.start_minus_btn = tk.Button(start_btns, text="-", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_start(-1))
        self.start_minus_btn.pack(side="left", padx=(0,8), pady=0, ipadx=6, ipady=4)
        self.start_plus_btn = tk.Button(start_btns, text="+", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_start(1))
        self.start_plus_btn.pack(side="left", padx=0, pady=0, ipadx=6, ipady=4)

        # End Page row
        tk.Label(self.page_range_frame, text="End Page", bg="#f9f9f9", font=base_font).grid(row=1, column=0, padx=(0,10), pady=4, sticky="w")
        self.end_page_entry = tk.Entry(self.page_range_frame, textvariable=self.end_page_var, width=5, font=base_font, justify='center')
        self.end_page_entry.grid(row=1, column=1, padx=(0,10), pady=4, sticky="w")
        end_btns = tk.Frame(self.page_range_frame, bg="#f9f9f9")
        end_btns.grid(row=1, column=2, padx=(15,0), pady=4, sticky="w")
        self.end_minus_btn = tk.Button(end_btns, text="-", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_end(-1))
        self.end_minus_btn.pack(side="left", padx=(0,8), pady=0, ipadx=6, ipady=4)
        self.end_plus_btn = tk.Button(end_btns, text="+", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_end(1))
        self.end_plus_btn.pack(side="left", padx=0, pady=0, ipadx=6, ipady=4)

        # Copies
        copies_frame = tk.Frame(pages_section, bg="#f9f9f9")
        copies_frame.pack(anchor="w", padx=30, pady=5)
        tk.Label(copies_frame, text="Copies", bg="#f9f9f9", font=base_font).grid(row=0, column=0, padx=(0,10), sticky="w")
        self.copies_entry = tk.Entry(copies_frame, textvariable=self.copies_var, width=5, font=base_font, justify='center')
        self.copies_entry.grid(row=0, column=1, padx=(0,10), sticky="w")
        copies_btns = tk.Frame(copies_frame, bg="#f9f9f9")
        copies_btns.grid(row=0, column=2, padx=(0,0), sticky="w")
        tk.Button(copies_btns, text="-", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_copies(-1)).pack(side="left", padx=(0,8), pady=0, ipadx=6, ipady=4)
        tk.Button(copies_btns, text="+", font=base_font, width=4, bg="#b42e41", fg="white", bd=0, command=lambda: self._adjust_copies(1)).pack(side="left", padx=0, pady=0, ipadx=6, ipady=4)
        
        # Color
        color_section = self._create_section_frame(self.options_scrollable_frame, "Color Mode", section_font)
        color_section.pack(fill="x", pady=5)
        self.colored_radio = tk.Radiobutton(color_section, text="Colored", variable=self.color_var, value="colored", bg="#f9f9f9", font=base_font)
        self.colored_radio.pack(anchor="w", padx=10, pady=2)
        self.bw_radio = tk.Radiobutton(color_section, text="Black & White", variable=self.color_var, value="bw", bg="#f9f9f9", font=base_font)
        self.bw_radio.pack(anchor="w", padx=10, pady=2)
        self.after(0, self.fetch_and_set_color_prices)

        # Paper Size
        page_size_section = self._create_section_frame(self.options_scrollable_frame, "Paper Size", section_font)
        page_size_section.pack(fill="x", pady=5)
        tk.Radiobutton(page_size_section, text="A4", variable=self.page_size_var, value="A4", bg="#f9f9f9", font=base_font).pack(anchor="w", padx=10, pady=2)
        tk.Radiobutton(page_size_section, text="Letter Size", variable=self.page_size_var, value="Letter Size", bg="#f9f9f9", font=base_font).pack(anchor="w", padx=10, pady=2)
        # Action Button Frame (always visible at the bottom of right_frame)
        action_buttons_frame = tk.Frame(right_frame, bg="white")
        action_buttons_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0)) # Fixed row, not tied to scroll
        action_buttons_frame.grid_columnconfigure(0, weight=1)

        # Button container for Cancel and Proceed (right aligned, close together)
        button_row = tk.Frame(action_buttons_frame, bg="white")
        button_row.pack(pady=(0, 5), anchor="e")

        # Add a stretchable empty frame to push buttons to the right
        tk.Frame(button_row, bg="white").pack(side="left", expand=True, fill="x")

        cancel_button = tk.Button(
            button_row, text="Cancel", command=self.show_cancel_confirmation_modal,
            font=button_font, bg="#959595", fg="white", padx=40, pady=15, bd=0, relief="flat"
        )
        cancel_button.pack(side="left", padx=(0, 12))

        proceed_button = tk.Button(
            button_row, text="Proceed", command=self.start_printing,
            font=button_font, bg="#b42e41", fg="white", padx=40, pady=15, bd=0, relief="flat"
        )
        proceed_button.pack(side="left", padx=(0, 0))
    def show_cancel_confirmation_modal(self):
        """Display a modal dialog asking the user to confirm cancellation (styled like PaymentScreen)."""
        # Copy of PaymentScreen cancel modal
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        modal_width = int(550 * scale)
        modal_height = int(300 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        self._draw_round_rect(canvas, 0, 0, modal_width, modal_height, radius, fill="white", outline="#999999", width=2)

        modal_container = tk.Frame(canvas, bg="white")
        canvas.create_window(modal_width // 2, modal_height // 2, window=modal_container)
        padding = int(40 * scale)
        content = tk.Frame(modal_container, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)

        title_font = ("Bebas Neue", max(28, int(32 * scale)), "bold")
        tk.Label(
            content,
            text="Cancel Printing?",
            font=title_font,
            bg="white",
            fg="#333"
        ).pack(pady=(0, int(20 * scale)))

        message_font = ("Arial", max(14, int(16 * scale)))
        tk.Label(
            content,
            text="Are you sure you want to cancel this Printing?",
            font=message_font,
            bg="white",
            fg="#666",
            justify="center"
        ).pack(pady=(0, int(30 * scale)))

        buttons_frame = tk.Frame(content, bg="white")
        buttons_frame.pack()
        button_font = ("Arial", max(14, int(16 * scale)), "bold")
        button_padx = int(30 * scale)
        button_pady = int(12 * scale)

        no_button = tk.Button(
            buttons_frame,
            text="No, Continue",
            font=button_font,
            bg="#4CAF50",
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.close_cancel_modal(modal_overlay)
        )
        no_button.pack(side="left", padx=int(10 * scale))

        yes_button = tk.Button(
            buttons_frame,
            text="Yes, Cancel",
            font=button_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.confirm_cancel(modal_overlay)
        )
        yes_button.pack(side="left", padx=int(10 * scale))

        self._cancel_modal = modal_overlay

    def close_cancel_modal(self, modal_overlay):
        if modal_overlay and modal_overlay.winfo_exists():
            modal_overlay.destroy()
        if hasattr(self, '_cancel_modal'):
            delattr(self, '_cancel_modal')

    def confirm_cancel(self, modal_overlay):
        self.close_cancel_modal(modal_overlay)
        
        # Update job status to 'cancelled' in Firebase (NEW HIERARCHICAL STRUCTURE)
        if hasattr(self, 'job_id') and self.job_id:
            try:
                # Update root level status (for dashboard)
                job_ref = db.reference(f'jobs/print_jobs/{self.job_id}')
                job_ref.update({
                    'status': 'cancelled',
                    'updated_at': time.time()
                })
                
                # Also update details level status (for consistency)
                detail_ref = db.reference(f'jobs/print_jobs/{self.job_id}/details/0')
                detail_ref.update({
                    'status': 'cancelled',
                    'updated_at': time.time()
                })
            except Exception as e:
                print(f"Error updating job status to cancelled: {e}")
        
        # Go back to home screen
        home_screen = self.controller.frames["HomeScreen"]
        home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")

    def _draw_round_rect(self, canvas, x1, y1, x2, y2, r, fill, outline='', tag=None, width=1):
        """Draw a rounded rectangle using individual shapes for proper rounded corners."""
        if r <= 0 or x2 - x1 < 2*r or y2 - y1 < 2*r:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline if outline else '', width=width, tags=(tag,) if tag else None)
            return
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline='', tags=(tag,) if tag else None)
        canvas.create_rectangle(x1, y1 + r, x1 + r, y2 - r, fill=fill, outline='', tags=(tag,) if tag else None)
        canvas.create_rectangle(x2 - r, y1 + r, x2, y2 - r, fill=fill, outline='', tags=(tag,) if tag else None)
        canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        if outline and width > 0:
            canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)

    def _create_section_frame(self, parent, title, title_font):
        frame = tk.Frame(parent, bg="#f9f9f9", padx=10, pady=10, relief="solid", bd=1, highlightbackground="#e0e0e0")
        label = tk.Label(frame, text=title, font=title_font, bg="#f9f9f9", anchor="w")
        label.pack(pady=(0, 10), padx=5, anchor="w")
        return frame

    # --- UI Logic Methods ---
    def toggle_page_range_inputs(self):
        state = "normal" if self.pages_var.get() == "range" else "disabled"
        # Enable/disable entries
        self.start_page_entry.config(state=state)
        self.end_page_entry.config(state=state)
        # Enable/disable +/- buttons if they exist
        for attr in ["start_plus_btn", "start_minus_btn", "end_plus_btn", "end_minus_btn"]:
            if hasattr(self, attr):
                getattr(self, attr).config(state=state)

        if self.pages_var.get() == "range":
            # No need to reload preview immediately; values haven't changed
            return
        else:
            # Reset to full range when "All Pages" is selected without causing multiple reloads
            try:
                total = int(self.total_pages_value.cget("text"))
            except Exception:
                total = 1
            self._suppress_preview = True
            self.start_page_var.set("1")
            self.end_page_var.set(str(max(1, total)))
            self._suppress_preview = False
            self.after(200, lambda: self.load_preview(self.preview_page["num"]))


    def toggle_manual_scale_inputs(self):
        state = "normal" if self.scale_var.get() == "manual" else "disabled"
        # The manual scale entry UI was removed per request. Be defensive in case
        # anything still calls this method (e.g., variable traces).
        if hasattr(self, 'manual_scale_entry') and self.manual_scale_entry is not None:
            try:
                self.manual_scale_entry.config(state=state)
            except Exception:
                # If config fails for any reason, ignore to avoid breaking the UI flow
                pass

    # --- Increment/Decrement Handlers ---
    def _get_total_pages_safe(self):
        try:
            return max(1, int(self.total_pages_value.cget("text") or "1"))
        except Exception:
            return 1

    def _adjust_start(self, delta):
        total = self._get_total_pages_safe()
        try:
            start = int(self.start_page_var.get() or 1)
        except ValueError:
            start = 1
        try:
            end = int(self.end_page_var.get() or total)
        except ValueError:
            end = total
        new_start = max(1, min(end, start + delta))
        # Suppress preview reloads triggered by variable traces
        self._suppress_preview = True
        self.start_page_var.set(str(new_start))
        self._suppress_preview = False

    def _adjust_end(self, delta):
        total = self._get_total_pages_safe()
        try:
            start = int(self.start_page_var.get() or 1)
        except ValueError:
            start = 1
        try:
            end = int(self.end_page_var.get() or total)
        except ValueError:
            end = total
        new_end = max(start, min(total, end + delta))
        # Suppress preview reloads triggered by variable traces
        self._suppress_preview = True
        self.end_page_var.set(str(new_end))
        self._suppress_preview = False

    def _adjust_copies(self, delta):
        try:
            copies = int(self.copies_var.get() or 1)
        except ValueError:
            copies = 1
        new_val = max(1, min(999, copies + delta))
        self.copies_var.set(str(new_val))

    def update_preview_page(self, delta):
        new_page = self.preview_page["num"] + delta
        if 1 <= new_page <= self.preview_page["max"]:
            self.preview_page["num"] = new_page
            self.load_preview(new_page)
            
    # --- Debounced Preview Update Handlers ---
    def _on_color_mode_change(self, *_):
        if self._suppress_preview: return
        if self._color_update_timer: self.after_cancel(self._color_update_timer)
        self._color_update_timer = self.after(200, lambda: self.load_preview(self.preview_page["num"]))

    def _on_page_size_change(self, *_):
        if self._suppress_preview: return
        if self._page_size_update_timer: self.after_cancel(self._page_size_update_timer)
        self._page_size_update_timer = self.after(200, lambda: self.load_preview(self.preview_page["num"]))
        
    def _on_scale_mode_change(self, *_):
        if self._suppress_preview: return
        if self._scale_mode_update_timer: self.after_cancel(self._scale_mode_update_timer)
        self._scale_mode_update_timer = self.after(300, lambda: self.load_preview(self.preview_page["num"]))

    def _on_manual_scale_change(self, *_):
        if self._suppress_preview: return
        if self.scale_var.get() == "manual":
            if self._scale_update_timer: self.after_cancel(self._scale_update_timer)
            self._scale_update_timer = self.after(300, lambda: self.load_preview(self.preview_page["num"]))

    def _on_start_end_change(self, *_):
        if self._suppress_preview: return
        # Debounce updates from both start and end fields
        if self._page_size_update_timer: self.after_cancel(self._page_size_update_timer)
        self._page_size_update_timer = self.after(300, lambda: self.load_preview(self.preview_page["num"]))

    # --- Mouse Wheel Scrolling for Options Pane ---
    
    # --- Preview Loading Logic ---
    def load_preview(self, page_num=1, on_done=None):
        if not hasattr(self, 'file_path') or not self.file_path:
            if on_done: on_done()
            return

        self.preview_canvas.delete("all")

        # Get actual canvas dimensions after it's rendered
        self.update_idletasks()  # Ensure canvas dimensions are updated
        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()

        if canvas_w < 10 or canvas_h < 10:  # Canvas not ready
            print(f"[DEBUG] Canvas not ready ({canvas_w}x{canvas_h}), retrying preview...")
            self.after(100, lambda: self.load_preview(page_num, on_done=on_done))
            return

        temp_pdf_path = None
        temp_dir = None
        pdf_document = None
        try:
            display_path = self.file_path

            # Handle DOC/DOCX conversion (convert once per job and cache)
            if self.file_name and self.file_name.lower().endswith(('.doc', '.docx')):
                if self._converted_pdf_path and os.path.exists(self._converted_pdf_path):
                    display_path = self._converted_pdf_path
                else:
                    temp_dir = tempfile.mkdtemp()
                    temp_pdf_path = os.path.join(
                        temp_dir,
                        os.path.basename(self.file_name).replace('.docx', '.pdf').replace('.doc', '.pdf')
                    )
                    try:
                        convert(self.file_path, temp_pdf_path)
                        # Persist the converted PDF for the lifetime of the job (don't delete in finally)
                        self._converted_pdf_path = temp_pdf_path
                        self._converted_from_docx = True
                        display_path = self._converted_pdf_path
                        # We keep temp_dir alive by nulling it out so it's not removed in finally
                        temp_dir = None
                        temp_pdf_path = None
                    except Exception as e:
                        # Inline error on canvas; don't spam popups
                        self.preview_canvas.delete("all")
                        font_size = max(10, int(16 * self.scale_factor))
                        error_details = str(e)
                        if not error_details:
                            error_details = "No details. Microsoft Word may not be installed, or the file may be corrupted."
                        self.preview_canvas.create_text(
                            canvas_w / 2, canvas_h / 2,
                            text=("Conversion Error\n" +
                                  "Failed to convert Word document to PDF.\n" +
                                  "Please upload a PDF or install Microsoft Word.\n\n" +
                                  f"Details: {error_details}"),
                            fill="red",
                            font=("Arial", font_size),
                            justify="center"
                        )
                        print(f"[ERROR] DOCX->PDF conversion failed: {error_details}")
                        if on_done: on_done()
                        return

            # Get selected paper size early for cache key and rendering
            selected_page_size = (self.page_size_var.get() or "Letter Size").lower()
            
            # Calculate zoom and color mode first so we can check cache without opening the file
            zoom = 1.0
            if self.scale_var.get() == "manual":
                try:
                    manual_scale = int(self.manual_scale_var.get())
                    if 1 <= manual_scale <= 500:
                        zoom = manual_scale / 100.0
                except ValueError:
                    pass
            color_mode = 'bw' if self.color_var.get() == 'bw' else 'color'
            cache_key = (page_num, color_mode, round(zoom, 2), selected_page_size)

            base_img = self._preview_cache.get(cache_key)
            if base_img is None:
                # Open the document only if we need to render
                pdf_document = fitz.open(display_path)
                total_pdf_pages = pdf_document.page_count
                self._cached_page_count = total_pdf_pages

                # Validate and adjust page_num
                page_num = max(1, min(page_num, total_pdf_pages))

                # Update UI for total pages and page range entries
                self.total_pages_value.config(text=str(total_pdf_pages))
                try:
                    if int(self.end_page_var.get()) > total_pdf_pages:
                        self.end_page_var.set(str(total_pdf_pages))
                except Exception:
                    self.end_page_var.set(str(total_pdf_pages))
                self.preview_page['max'] = total_pdf_pages

                page = pdf_document[page_num - 1]  # fitz is 0-indexed

                # Render pixmap at ~120 DPI times zoom (faster than 150 with acceptable quality)
                matrix = fitz.Matrix(zoom * 120 / 72, zoom * 120 / 72)
                if color_mode == 'bw':
                    pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY)
                else:
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                # Convert pixmap to PIL Image
                if pix.n == 1:
                    base_img = Image.frombytes("L", [pix.width, pix.height], pix.samples).convert("RGB")
                else:
                    base_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                self._preview_cache[cache_key] = base_img
            else:
                # If we have cached image, try to use cached page count too to avoid reopening file
                if hasattr(self, '_cached_page_count') and self._cached_page_count:
                    self.preview_page['max'] = self._cached_page_count
                    self.total_pages_value.config(text=str(self._cached_page_count))
            img = base_img

            # Determine paper aspect ratio based on selected page size (already defined above)
            if selected_page_size.startswith("a4"):
                paper_w_mm, paper_h_mm = 210.0, 297.0  # A4
            else:
                paper_w_mm, paper_h_mm = 215.9, 279.4  # Letter
            paper_aspect = paper_w_mm / paper_h_mm

            # Build a paper rectangle inside the canvas with padding
            pad = max(5, int(min(canvas_w, canvas_h) * 0.025))
            avail_w = max(1, canvas_w - 2 * pad)
            avail_h = max(1, canvas_h - 2 * pad)

            # Calculate paper dimensions to fit within available space
            if avail_w / avail_h > paper_aspect:
                paper_h = avail_h
                paper_w = int(paper_h * paper_aspect)
            else:
                paper_w = avail_w
                paper_h = int(paper_w / paper_aspect)
            
            # Double-check and enforce maximum dimensions
            if paper_h > avail_h:
                paper_h = avail_h
                paper_w = int(paper_h * paper_aspect)
            if paper_w > avail_w:
                paper_w = avail_w
                paper_h = int(paper_w / paper_aspect)

            paper_x0 = int((canvas_w - paper_w) / 2)
            paper_y0 = int((canvas_h - paper_h) / 2)
            paper_x1 = paper_x0 + paper_w
            paper_y1 = paper_y0 + paper_h

            # Draw paper background with border (no shadow)
            border_width = 2  # Border
            border_color = "#cccccc"  # Light gray border
            
            # Draw paper background with border
            self.preview_canvas.create_rectangle(
                paper_x0, paper_y0, paper_x1, paper_y1,
                fill="white", outline=border_color, width=border_width
            )

            # Scale the rendered page image to fit within the paper bounds
            scale = min(paper_w / max(1, img.width), paper_h / max(1, img.height))
            
            resized_w = max(1, int(img.width * scale))
            resized_h = max(1, int(img.height * scale))
            resized = img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
            
            # Center the image
            img_x = paper_x0 + (paper_w - resized_w) // 2
            img_y = paper_y0 + (paper_h - resized_h) // 2

            # Convert to Tk image and place on the paper rectangle
            img_tk = ImageTk.PhotoImage(resized)
            self.preview_canvas.create_image(img_x, img_y, image=img_tk, anchor="nw")
            self.image_refs['preview'] = img_tk

            # Update page nav label and state
            self.page_nav_label.config(text=f"Page {page_num} of {self.preview_page['max']}")

            # Remove any previous preview overlays if present
            try:
                if hasattr(self, 'preview_overlay'):
                    self.preview_canvas.delete(self.preview_overlay)
                if hasattr(self, 'preview_overlay_text'):
                    self.preview_canvas.delete(self.preview_overlay_text)
            except Exception:
                pass

            if on_done: on_done()
        except Exception as e:
            self.preview_canvas.delete("all")
            font_size = max(10, int(16 * self.scale_factor))
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width() / 2, self.preview_canvas.winfo_height() / 2,
                text=f"Preview failed:\n{e}",
                fill="red",
                font=("Arial", font_size),
                justify="center"
            )
            print(f"[ERROR] Preview failed: {e}")
        finally:
            if pdf_document is not None:
                try:
                    pdf_document.close()
                except Exception:
                    pass
            # Only delete temp files if we didn't cache the conversion
            if temp_pdf_path and os.path.exists(temp_pdf_path):
                try:
                    os.unlink(temp_pdf_path)
                except Exception:
                    pass
            if temp_dir and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except OSError as e:
                    print(f"Error removing temp directory {temp_dir}: {e}")

    def reset_idle_timer(self):
        # Cancel previous timer if exists
        if hasattr(self, '_idle_timer') and self._idle_timer:
            self.after_cancel(self._idle_timer)
        # Set new timer for 5 minutes (300,000 ms)
        self._idle_timer = self.after(300000, self._on_idle_timeout)

    def _on_idle_timeout(self):
        # Go back to home screen automatically
        home_screen = self.controller.frames["HomeScreen"]
        home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")
