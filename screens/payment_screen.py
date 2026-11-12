# screens/payment_screen.py

import tkinter as tk
from threading import Thread
import time
import subprocess
import os
import sys
import math
import requests
import win32print
import win32api
import win32ui
import win32con
from PIL import Image, ImageTk, ImageWin, ImageChops
from config.firebase_config import db
import fitz # PyMuPDF
from config.arduino_config import ArduinoCoinAcceptor
from config.print_config import print_file_for_job


class PaymentScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.total_amount = 0
        self.printing_started = False
        self.arduino = None
        # Idle timer for auto-return to home
        self._idle_timer = None
        self.create_widgets()

        # Bind events to reset global idle timer when user is active
        self.bind_all('<Any-KeyPress>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Any-Button>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Motion>', lambda e: self.controller._reset_global_idle_timer())

    def load_data(self, data):
        """Load payment data and start the payment process."""
        print(f"[PaymentScreen] load_data called with data keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
        self.total_price = data.get('total_price', 0)
        self.job_id = data.get('job_id')
        
        # Keep summary context so back arrow can return to Summary
        self.summary_context = data.get('summary_context')
        
        # Extract file information from summary_context if available
        if self.summary_context:
            self.file_name = self.summary_context.get('file_name')
            self.color_mode = self.summary_context.get('color_mode', 'colored')
            self.page_size = self.summary_context.get('page_size', 'Letter')
            self.page_range = self.summary_context.get('pages_range', 'all')
            self.num_copies = self.summary_context.get('num_copies', 1)
        else:
            # Fallback to direct data fields
            self.file_name = data.get('file_name')
            self.color_mode = data.get('color_mode', 'colored')
            self.page_size = data.get('page_size', 'Letter')
            self.page_range = data.get('page_range', 'all')
            self.num_copies = data.get('num_copies', 1)
        
        print(f"[PaymentScreen] Loaded job_id: {self.job_id}, total_price: {self.total_price}")
        print(f"[PaymentScreen] File: {self.file_name}, Size: {self.page_size}, Copies: {self.num_copies}")
        print(f"[PaymentScreen] Color: {self.color_mode}, Range: {self.page_range}")
        
        # Reset payment state - CRITICAL for handling back navigation
        self.total_amount = 0
        self.printing_started = False
        self.change_dispensed = False  # Track if change has been dispensed
        self.stop_coin_thread = False  # Reset the coin thread flag

        # Update UI - Reset to initial state
        self.total_price_label.config(text=self._peso(self.total_price))
        self.remaining_value_label.config(text=self._peso(self.total_price))
        self.inserted_value_label.config(text=self._peso(0))
        self.remaining_title_label.config(text="Remaining:")  # Reset title

        # Clean up any existing Arduino connection before creating new one
        if self.arduino:
            try:
                print("[INFO] Stopping existing Arduino listener...")
                self.arduino.stop_listening()
                print("[INFO] Resetting payment state...")
                self.arduino.reset_payment()
                print("[INFO] Closing Arduino serial connection...")
                self.arduino.close()
                print("[INFO] Cleaned up existing Arduino connection")
                # Wait a moment for serial port to be fully released
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Error cleaning up Arduino: {e}")
            finally:
                self.arduino = None

        # Try to connect to Arduino
        try:
            print("[INFO] Creating new Arduino connection...")
            self.arduino = ArduinoCoinAcceptor()  # Auto-detect port
            if self.arduino.connect():
                self.stop_coin_thread = False
                # Set the required payment amount on Arduino
                self.arduino.set_required_payment(self.total_price)
                self.arduino.start_listening(self.process_coin_from_arduino)
                print("[INFO] Arduino coin acceptor connected and listening.")
            else:
                print("[WARN] Arduino not found. Coin acceptor unavailable.")
                self.arduino = None
        except Exception as e:
            print(f"[ERROR] Arduino connection failed: {e}")
            import traceback
            traceback.print_exc()
            self.arduino = None

        # Start timeout timer
        self.after(300 * 1000, self.timeout_handler)

    def process_coin_from_arduino(self, coin_value, total):
        # Stop processing if printing already started or change is being dispensed
        if self.stop_coin_thread or self.printing_started:
            print(f"[PaymentScreen] Ignoring coin - stop_coin_thread={self.stop_coin_thread}, printing_started={self.printing_started}")
            return
        # Also check Arduino flags
        if self.arduino and (self.arduino.payment_complete or self.arduino.change_dispensing):
            print(f"[PaymentScreen] Ignoring coin - payment_complete={self.arduino.payment_complete}, change_dispensing={self.arduino.change_dispensing}")
            return
        self.after(0, self.process_coin, coin_value)

    def create_widgets(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        # Keep UI from shrinking on smaller screens; scale up on larger ones
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        # Consistent outer horizontal padding for header and main container
        outer_padx = int(50 * scale)
        # Control how far from the top the header (arrow + title) sits
        header_top_pad = int(60 * scale)

        # Typography (slightly larger title)
        title_font_size = min(36, max(24, int(28 * scale)))
        title_font = ("Bebas Neue", title_font_size, "bold")
        label_font = ("Arial", max(20, int(22 * scale)))
        label_bold = ("Arial", max(20, int(22 * scale)), "bold")
        # Slightly larger fonts for the price card
        price_title_font = ("Arial", max(26, int(28 * scale)), "bold")
        price_value_font = ("Arial", max(59, int(64 * scale)), "bold")
        button_font = ("Arial", max(16, int(18 * scale)), "bold")

        # Top bar (back icon + title)
        header = tk.Frame(self, bg="white")
        # Lower the header from the very top edge
        header.pack(fill="x", pady=(header_top_pad, 0))
        header_inner = tk.Frame(header, bg="white")
        # Align header with the main container's left/right margin
        header_inner.pack(anchor="w", padx=outer_padx)
        
        #Smaller back arrow button
        back_size = 89
        back_canvas = self._add_back_icon_button(header_inner, size=back_size)
        back_canvas.pack(side="left")
        tk.Label(header_inner, text="Please Insert Bills/Coins To Pay", font=title_font, bg="white").pack(side="left", padx=int(16 * scale))

        # Centered content column 
        center = tk.Frame(self, bg="white")
        center.pack(expand=True, fill="x")

        # Light gray rounded container (now holds the logo, cards, and button)
        container_frame, container = self._rounded_container(
            center, bg="#e6e6e6", radius=15, padding=int(16 * scale)
        )
        # Give the main container more left/right breathing room (reduced top gap)
        # Do not expand vertically so it stays close under the header
        container_frame.pack(fill="x", expand=False, padx=outer_padx, pady=(0, int(30 * scale)))

        # Logo inside the container, a bit smaller
        logo_holder = tk.Frame(container, bg="#e6e6e6")
        # Add more bottom space under the logo
        logo_holder.pack(pady=(0, int(18 * scale)))
        # Slightly larger logo
        self._load_logo(logo_holder, scale, max_w=int(380 * scale))

        # Two cards side-by-side (50/50 widths)
        cards = tk.Frame(container, bg="#e6e6e6")
        # Add more inner horizontal padding so cards are not too close to the container edge
        cards.pack(fill="both", expand=True, padx=int(24 * scale))
        cards.grid_columnconfigure(0, weight=1, uniform="cards")
        cards.grid_columnconfigure(1, weight=1, uniform="cards")
        cards.grid_rowconfigure(0, weight=1)

        # Left Card: Details (rounded)
        left_frame, left = self._rounded_container(
            cards, bg="white", radius=15, padding=int(18 * scale)
        )
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(int(15 * scale), int(15 * scale)))

        # Payment details with vertical layout (title on top, value below)
        brand_red = "#b42e41"
        
        # Total Price section
        tk.Label(left, text="Total Price:", font=label_bold, fg="black", bg="white", anchor="w").pack(anchor="w")
        self.total_price_label = tk.Label(left, text="", font=price_value_font, fg=brand_red, bg="white", anchor="w")
        self.total_price_label.pack(anchor="w")
        
        # Remaining Balance / Change Dispensed section (dynamic)
        self.remaining_title_label = tk.Label(left, text="Remaining:", font=label_bold, fg="black", bg="white", anchor="w")
        self.remaining_title_label.pack(anchor="w")
        self.remaining_value_label = tk.Label(left, text="", font=price_value_font, fg=brand_red, bg="white", anchor="w")
        self.remaining_value_label.pack(anchor="w")

        # Right Card: Amount Inserted (rounded)
        right_frame, right = self._rounded_container(
            cards, bg="white", radius=15, padding=int(18 * scale), fill_x=True, vcenter=True
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(int(15 * scale), int(15 * scale)))

        # Centered inserted amount block container so the title and value are truly centered
        inserted_box = tk.Frame(right, bg="white")
        inserted_box.pack(expand=True, fill="both")
        # Use expandable spacers to center vertically
        tk.Frame(inserted_box, bg="white").pack(side="top", expand=True, fill="y")
        inserted_content = tk.Frame(inserted_box, bg="white")
        inserted_content.pack(side="top")

        title_lbl = tk.Label(
            inserted_content,
            text="Amount Inserted:",
            font=price_title_font,
            fg="black",
            bg="white",
        )
        title_lbl.pack(anchor="center", pady=(int(4 * scale), 0))

        self.inserted_value_label = tk.Label(
            inserted_content,
            text=self._peso(0),
            font=price_value_font,
            fg=brand_red,
            bg="white",
        )
        self.inserted_value_label.pack(anchor="center", pady=(int(10 * scale), 0))
        tk.Frame(inserted_box, bg="white").pack(side="top", expand=True, fill="y")


        # Bottom button inside container
        btn = tk.Button(container, text="Cancel", font=button_font, bg=brand_red, fg="white", bd=0, relief="flat",
                         padx=int(16 * scale), pady=int(6 * scale), command=self.cancel_transaction)
        # Add extra space above the button
        btn.pack(pady=(int(24 * scale), 0))
        # Small bottom spacer to add a little height to the gray container
        tk.Frame(container, height=int(12 * scale), bg=container.cget("bg")).pack(fill="x")

    # Helper to render key/value rows inside the left card
    def _kv(self, parent, key, value, font, gap):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="x", pady=(gap, 0))
        tk.Label(frame, text=key, font=font, bg="white").pack(side="left")
        val = tk.Label(frame, text=value, font=font, bg="white")
        val.pack(side="left", padx=(6, 0))
        # keep handle for caller to update
        self._last_value_label = val

    def _peso(self, amount):
        try:
            return f"₱ {float(amount):.2f}"
        except Exception:
            return "₱ 0.00"

    # --- Text wrapping helper ---
    def _bind_wrap_to_parent(self, label, parent, pad=0):
        """Bind a Label's wraplength to track its parent's width.
        Prevents clipping when containers resize.
        """
        def _update(_=None):
            try:
                w = max(parent.winfo_width() - pad * 2, 50)
                label.config(wraplength=w)
            except Exception:
                pass

        parent.bind("<Configure>", _update)
        label.bind("<Configure>", _update)
        parent.after(0, _update)

    def _make_breakable_filename(self, text):
        """Insert zero-width spaces after common separators so long filenames wrap nicely.
        Only affects display; original text remains unchanged elsewhere.
        """
        if not isinstance(text, str):
            return text
        zw = "\u200b"
        # Allow breaks after underscores, hyphens, dots, and slashes
        return (
            text.replace("_", f"_{zw}")
                .replace("-", f"-{zw}")
                .replace(".", f".{zw}")
                .replace("/", f"/{zw}")
                .replace("\\", f"\\{zw}")
        )

    def _draw_round_rect(self, canvas, x1, y1, x2, y2, r, fill, outline='', tag=None, width=1):
        """Draw a rounded rectangle using individual shapes for proper rounded corners"""
        if r <= 0 or x2 - x1 < 2*r or y2 - y1 < 2*r:
            # Fallback to regular rectangle if radius is too large or zero
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline if outline else '', 
                                  width=width, tags=(tag,) if tag else None)
            return
        
        # Draw filled shapes with the tag
        # Center rectangle
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline='', tags=(tag,) if tag else None)
        # Left and right rectangles
        canvas.create_rectangle(x1, y1 + r, x1 + r, y2 - r, fill=fill, outline='', tags=(tag,) if tag else None)
        canvas.create_rectangle(x2 - r, y1 + r, x2, y2 - r, fill=fill, outline='', tags=(tag,) if tag else None)
        
        # Four corner arcs (filled)
        canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, 
                         fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, 
                         fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, 
                         fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, 
                         fill=fill, outline='', style='pieslice', tags=(tag,) if tag else None)
        
        # Draw outline if specified
        if outline and width > 0:
            # Draw outline arcs for corners
            canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            # Draw straight lines connecting the arcs
            canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)

    def _rounded_container(self, parent, bg="#ffffff", radius=10, padding=16, fill_x=True, vcenter=False):
        """Create a container with a rounded background and return (wrapper, inner).
        If fill_x is False, the rounded background fits content width instead of stretching to the wrapper width.
        """
        # Wrapper holds the canvas; inner is where children are added
        parent_bg = parent.cget("bg")
        wrapper = tk.Frame(parent, bg=parent_bg)
        canvas = tk.Canvas(wrapper, bg=parent_bg, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window(padding, padding, anchor="nw", window=inner)

        def _refresh(_=None):
            # Size canvas based on mode: fill_x => stretch to wrapper width, else fit to content width.
            # Compute width first, apply it to the window, then re-measure height to prevent clipping.
            wrapper.update_idletasks()
            wrapper_w = max(wrapper.winfo_width(), 1)
            wrapper_h = max(wrapper.winfo_height(), 1)

            # Determine target width
            inner.update_idletasks()
            content_w_initial = inner.winfo_reqwidth() + padding * 2
            w = max(wrapper_w, 40) if fill_x else max(content_w_initial, 40)

            # Apply width immediately so texts can rewrap; then re-measure height
            canvas.config(width=w)
            try:
                canvas.itemconfig(win, width=max(w - padding * 2, 10))
            except Exception:
                pass

            # Allow geometry to settle, then compute accurate content height
            try:
                inner.update_idletasks()
                canvas.update_idletasks()
            except Exception:
                pass
            content_h = inner.winfo_reqheight() + padding * 2
            # Use wrapper height if it's been set by grid (sticky), otherwise use content height
            h = max(wrapper_h if wrapper_h > 1 else content_h, content_h, 40)

            canvas.config(width=w, height=h)
            canvas.delete("rounded_bg")
            # Draw rounded rectangle filling entire canvas
            self._draw_round_rect(canvas, 0, 0, w, h, radius, fill=bg, outline='', tag="rounded_bg")
            canvas.tag_lower("rounded_bg")
            
            # When vcenter is requested, stretch the inner window to the available height;
            # its children (price_box) use expandable spacers to center content vertically.
            available_h = max(h - padding * 2, 0)
            if vcenter and available_h > 0:
                try:
                    canvas.itemconfig(win, height=available_h)
                except Exception:
                    pass
            canvas.coords(win, padding, padding)

            # One more pass in case text re-wrapped after height set
            try:
                inner.update_idletasks()
                new_h = inner.winfo_reqheight() + padding * 2
                # Check if wrapper has grown (e.g., due to grid layout matching sibling height)
                wrapper.update_idletasks()
                wrapper_h = max(wrapper.winfo_height(), 1)
                final_h = max(wrapper_h if wrapper_h > 1 else new_h, new_h, h)
                if final_h > h:
                    h = final_h
                    canvas.config(height=h)
                    canvas.delete("rounded_bg")
                    self._draw_round_rect(canvas, 0, 0, w, h, radius, fill=bg, outline='', tag="rounded_bg")
                    canvas.tag_lower("rounded_bg")
                    # Ensure inner window fills the new available height
                    available_h = max(h - padding * 2, 0)
                    if vcenter and available_h > 0:
                        try:
                            canvas.itemconfig(win, height=available_h)
                        except Exception:
                            pass
                    canvas.coords(win, padding, padding)
            except Exception:
                pass

        inner.bind("<Configure>", _refresh)
        wrapper.bind("<Configure>", _refresh)
        # Initial draw - multiple passes to ensure grid layout has settled
        wrapper.after(50, _refresh)
        wrapper.after(150, _refresh)
        wrapper.after(300, _refresh)
        return wrapper, inner

    def _load_logo(self, parent, scale, max_w=None):
        """Load and display the logo with proper scaling."""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Try both .png and .jpg
            logo_path_png = os.path.join(base_dir, 'static', 'img', 'logo.png')
            logo_path_jpg = os.path.join(base_dir, 'static', 'img', 'logo.jpg')
            
            if os.path.exists(logo_path_png):
                logo_path = logo_path_png
            elif os.path.exists(logo_path_jpg):
                logo_path = logo_path_jpg
            else:
                raise FileNotFoundError("Logo file not found")
            
            # Simply load and resize the logo
            logo_img = Image.open(logo_path)
            
            # Get parent background color
            bg_color = parent.cget("bg") if hasattr(parent, "cget") else "white"
            
            # Convert to RGB if it's RGBA, using parent background color
            if logo_img.mode == 'RGBA':
                # Parse the background color
                if isinstance(bg_color, str) and bg_color.startswith('#'):
                    if len(bg_color) == 4:  # Short form like #fff
                        r = int(bg_color[1]*2, 16)
                        g = int(bg_color[2]*2, 16)
                        b = int(bg_color[3]*2, 16)
                    else:  # Full form like #e6e6e6
                        r = int(bg_color[1:3], 16)
                        g = int(bg_color[3:5], 16)
                        b = int(bg_color[5:7], 16)
                else:
                    r, g, b = (255, 255, 255)  # Default to white
                
                # Create background with parent's color
                background = Image.new('RGB', logo_img.size, (r, g, b))
                background.paste(logo_img, mask=logo_img.split()[3] if len(logo_img.split()) > 3 else None)
                logo_img = background
            elif logo_img.mode != 'RGB':
                logo_img = logo_img.convert('RGB')
            
            # Scale
            if max_w is not None:
                target_w = int(max_w)
            else:
                target_w = min(max(320, int(560 * scale)), 900)
            
            w, h = logo_img.size
            aspect = h / w
            target_h = int(target_w * aspect)
            resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            self._logo_tk = ImageTk.PhotoImage(resized)
            tk.Label(parent, image=self._logo_tk, bg=bg_color, bd=0, highlightthickness=0).pack()
        except Exception as e:
            print(f"[PaymentScreen] Logo load failed: {e}")
            import traceback
            traceback.print_exc()
            bg_color = parent.cget("bg") if hasattr(parent, "cget") else "white"
            tk.Label(parent, text="PRINTECH", font=("Arial", max(24, int(48 * scale)), "bold"), bg=bg_color, fg="#000").pack()

    def update_gui(self, message, color="black"):
        if not self.winfo_exists():
            return
        if "Inserted:" in message and "Remaining:" in message:
            try:
                parts = message.split("|")
                inserted_part = parts[0].strip()
                remaining_part = parts[1].strip()
                inserted_val = inserted_part.split("Inserted:")[1].strip().replace("pesos","").strip()
                remaining_val = remaining_part.split("Remaining:")[1].strip().replace("pesos","").strip()
                self.inserted_value_label.config(text=f"₱ {float(inserted_val):.2f}")
                self.remaining_value_label.config(text=f"₱ {float(remaining_val):.2f}")
            except Exception:
                pass  # Ignore parsing errors

    def cancel_transaction(self):
        """Show confirmation modal before cancelling the transaction."""
        self.show_cancel_confirmation_modal()
    
    def show_cancel_confirmation_modal(self):
        """Display a modal dialog asking the user to confirm cancellation."""
        # Create white overlay
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Get scale factor
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        
        # Create canvas for rounded rectangle modal
        modal_width = int(550 * scale)
        modal_height = int(300 * scale)
        radius = int(20 * scale)
        
        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        
        # Draw rounded rectangle modal box
        self._draw_round_rect(canvas, 0, 0, modal_width, modal_height, 
                             radius, fill="white", outline="#999999", width=2)
        
        # Main modal container
        modal_container = tk.Frame(canvas, bg="white")
        canvas.create_window(modal_width // 2, modal_height // 2, window=modal_container)
        
        # Modal content frame with padding
        padding = int(40 * scale)
        content = tk.Frame(modal_container, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)
        
        # Title
        title_font = ("Bebas Neue", max(28, int(32 * scale)), "bold")
        tk.Label(
            content,
            text="Cancel Transaction?",
            font=title_font,
            bg="white",
            fg="#333"
        ).pack(pady=(0, int(20 * scale)))

        
        # Message
        message_font = ("Arial", max(14, int(16 * scale)))
        tk.Label(
            content,
            text="Are you sure you want to cancel this transaction?",
            font=message_font,
            bg="white",
            fg="#666",
            justify="center"
        ).pack(pady=(0, int(30 * scale)))
        
        # Buttons frame
        buttons_frame = tk.Frame(content, bg="white")
        buttons_frame.pack()
        
        button_font = ("Arial", max(14, int(16 * scale)), "bold")
        button_padx = int(30 * scale)
        button_pady = int(12 * scale)
        
        # No button (continue transaction)
        no_button = tk.Button(
            buttons_frame,
            text="No, Continue",
            font=button_font,
            bg="#4CAF50",  # Green
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.close_cancel_modal(modal_overlay)
        )
        no_button.pack(side="left", padx=int(10 * scale))
        
        # Yes button (confirm cancel)
        yes_button = tk.Button(
            buttons_frame,
            text="Yes, Cancel",
            font=button_font,
            bg="#b42e41",  # Brand red
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.confirm_cancel_transaction(modal_overlay)
        )
        yes_button.pack(side="left", padx=int(10 * scale))
        
        # Store reference to modal
        self._cancel_modal = modal_overlay
    
    def close_cancel_modal(self, modal_overlay):
        """Close the cancel confirmation modal without cancelling."""
        if modal_overlay and modal_overlay.winfo_exists():
            modal_overlay.destroy()
        if hasattr(self, '_cancel_modal'):
            delattr(self, '_cancel_modal')
    
    def confirm_cancel_transaction(self, modal_overlay):
        """Execute the cancellation after user confirms."""
        print("[PaymentScreen] Confirm cancel transaction called")
        print(f"[PaymentScreen] job_id before cancel: {self.job_id}")
        
        # Close modal first
        self.close_cancel_modal(modal_overlay)
        
        # Proceed with cancellation - properly clean up Arduino
        self.stop_coin_thread = True
        if self.arduino:
            try:
                self.arduino.stop_listening()
                self.arduino.reset_payment()
                self.arduino.close()
                print("[INFO] Arduino cleaned up after cancellation")
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Error cleaning up Arduino during cancel: {e}")
            finally:
                self.arduino = None
                
        self.update_job_status('cancelled')
        home_screen = self.controller.frames["HomeScreen"]
        home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")
        
    def timeout_handler(self):
        # Disabled auto-cancel on idle timeout. Do nothing or show a message if desired.
        pass

    def process_coin(self, coin_value):
        # Double-check: don't process if already printing or dispensing change
        if self.printing_started or (self.arduino and self.arduino.change_dispensing):
            print(f"[PaymentScreen] process_coin blocked - printing_started={self.printing_started}, change_dispensing={self.arduino.change_dispensing if self.arduino else False}")
            return
            
        # Use ArduinoCoinAcceptor logic for coin processing
        total, remaining, payment_complete = self.arduino.process_coin(coin_value, self.total_price)
        self.total_amount = total
        
        # Update the individual labels directly
        self.inserted_value_label.config(text=self._peso(self.total_amount))
        self.remaining_value_label.config(text=self._peso(remaining))

        if payment_complete and not self.printing_started:
            self.printing_started = True
            print("Payment successful! Checking for change...")
            # Stop Arduino coin listening immediately
            if self.arduino:
                self.arduino.stop_listening()
            
            # Calculate change
            change_amount = self.total_amount - self.total_price
            
            # Save inserted_amount and change_amount to Firebase
            try:
                ref = db.reference(f'jobs/print_jobs/{self.job_id}/details/0')
                ref.update({
                    'inserted_amount': self.total_amount,
                    'change_amount': change_amount,
                    'payment_completed_at': time.time()
                })
                print(f"[Firebase] Saved inserted_amount: {self.total_amount}, change_amount: {change_amount}")
            except Exception as e:
                print(f"[ERROR] Failed to save payment amounts to Firebase: {e}")
            
            # Send payment data to Flask backend API
            try:
                backend_url = "https://printech.azurewebsites.net/api/update_job_payment"
                payload = {
                    'job_id': str(self.job_id),
                    'file_name': str(self.file_name),
                    'inserted_amount': float(self.total_amount),
                    'change_amount': float(change_amount),
                    'total_price': float(self.total_price),
                    'status': 'completed'
                }
                response = requests.post(backend_url, json=payload, timeout=10)
                if response.status_code == 200:
                    print(f"[API] Successfully sent payment data to backend: {payload}")
                else:
                    print(f"[API] Backend returned status {response.status_code}: {response.text}")
            except Exception as e:
                print(f"[ERROR] Failed to send payment data to backend API: {e}")
            
            # Update the left card to show "Change Dispensed" if there's change
            if change_amount > 0:
                self.remaining_title_label.config(text="Change Dispensed:")
                self.remaining_value_label.config(text=self._peso(change_amount))
                print(f"Change needed: PHP {change_amount}")
                # Dispense change first, then print
                self.dispense_change_and_print(change_amount)
            else:
                # No change needed, update label to show ₱0.00 remaining
                self.remaining_value_label.config(text=self._peso(0))
                print("Exact payment. No change needed. Starting print...")
                # Start the actual print job in a new thread
                Thread(target=self.print_job, daemon=True).start()

    def dispense_change_and_print(self, change_amount):
        """
        Dispense change first, then proceed to printing.
        This runs in the main thread but spawns a thread for monitoring.
        """
        print(f"[Payment] Dispensing change: PHP {change_amount}")
        
        # No transition screen during dispensing - the change amount is already visible in the left card
        # The left card was updated in process_coin to show "Change Dispensed: ₱X.XX"
        
        def on_change_dispensed(success, amount, message):
            """Callback when change dispensing completes"""
            if success:
                print(f"[Payment] Change dispensed successfully: PHP {amount}")
                self.change_dispensed = True
                # Show success message after change is dispensed
                self.after(0, lambda: self.show_success_screen("Payment Successful!"))
                # Wait 1.5 seconds then start printing
                print("[Payment] Change complete. Starting print job...")
                self.after(1500, lambda: Thread(target=self.print_job, daemon=True).start())
            else:
                print(f"[Payment] Change dispensing failed: {message}")
                # Still print even if change fails (customer already paid)
                print("[Payment] Proceeding to print despite change error...")
                self.after(0, lambda: Thread(target=self.print_job, daemon=True).start())
        
        # CRITICAL: Stop the main listening thread BEFORE change dispensing
        # This prevents race conditions with multiple threads reading from the serial port
        if self.arduino:
            try:
                print("[Payment] Stopping main listening thread before change dispensing...")
                self.arduino.stop_listening()
                print("[Payment] Main listening thread stopped")
                time.sleep(0.2)  # Brief delay to ensure thread has fully stopped
            except Exception as e:
                print(f"[Payment] Error stopping listening thread: {e}")
        
        # Request change dispensing from Arduino
        if self.arduino:
            self.arduino.dispense_change(callback=on_change_dispensed)
        else:
            print("[Payment] ERROR: Arduino not available for change dispensing")
            # Proceed to print anyway
            Thread(target=self.print_job, daemon=True).start()

    def print_job(self):
        import threading
        print("[PaymentScreen] ===== PRINT_JOB METHOD STARTED =====")
        print(f"[PaymentScreen] Current thread: {threading.current_thread().name}")
        print(f"[PaymentScreen] Has job_id: {hasattr(self, 'job_id')}")
        print(f"[PaymentScreen] Has file_name: {hasattr(self, 'file_name')}")
        if hasattr(self, 'job_id'):
            print(f"[PaymentScreen] job_id value: {self.job_id}")
        if hasattr(self, 'file_name'):
            print(f"[PaymentScreen] file_name value: {self.file_name}")
        
        try:
            # Show "Printing In Process..." screen
            self.after(0, lambda: self.show_transition_screen("Printing In Progress"))
            
            print(f"[PaymentScreen] Updating job status to 'printing' for job_id: {self.job_id}")
            self.update_job_status("printing")

            # Only trigger DC motor feed after payment is complete
            options_screen = self.controller.frames.get("OptionsScreen")
            num_copies = 1
            selected_page_size = None
            print(f"[PaymentScreen] options_screen retrieved: {options_screen}")
            if options_screen:
                # Ensure copies_var is a StringVar and get its value
                if hasattr(options_screen, 'copies_var') and isinstance(options_screen.copies_var, tk.StringVar):
                    try:
                        num_copies = int(options_screen.copies_var.get())
                    except Exception:
                        num_copies = 1
                else:
                    num_copies = 1
                selected_page_size = options_screen.page_size_var.get() if hasattr(options_screen, 'page_size_var') else None
                print(f"[PaymentScreen] Copies to print: {num_copies}")
                print(f"[PaymentScreen] Selected page size: {selected_page_size}")

            # Delegate to centralized print module which handles
            # auto-detect printer, page range and copies
            print(f"[PaymentScreen] Starting print_file_for_job for job_id: {self.job_id}")
            ok, msg = print_file_for_job(self.job_id)
            
            if ok:
                self.update_job_status("completed")
                print("Printing complete!")
                # Show "Print Complete!" screen
                self.after(0, lambda: self.show_success_screen("Print Complete!"))
                # Return to home after 3 seconds
                self.after(3000, self.return_to_home)
            else:
                print(f"[PaymentScreen] Printing failed with message: {msg}")
                raise RuntimeError(msg)

        except Exception as e:
            print(f"[ERROR] Printing failed with exception: {e}")
            print(f"[ERROR] Exception type: {type(e).__name__}")
            print(f"[ERROR] Exception args: {e.args}")
            import traceback
            print("[ERROR] Full traceback:")
            traceback.print_exc()
            self.update_job_status("failed")
            # Show error screen with more details
            error_details = str(e)[:200] if str(e) else "Unknown error"
            print(f"[ERROR] Showing error to user: {error_details}")
            self.after(0, lambda msg=error_details: self.show_success_screen(f"Printing Failed!\n{msg}"))
            # Return to home after 7 seconds (longer to read error)
            self.after(7000, self.return_to_home)
    
    def return_to_home(self):
        """Helper method to return to home screen"""
        self.hide_transition_screen()
        
        # Clean up Arduino connection to ensure fresh state for next transaction
        self.stop_coin_thread = True
        if self.arduino:
            try:
                print("[INFO] Cleaning up Arduino before returning to home...")
                self.arduino.stop_listening()
                self.arduino.reset_payment()
                self.arduino.close()
                print("[INFO] Arduino cleaned up successfully")
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Error cleaning up Arduino during return_to_home: {e}")
            finally:
                self.arduino = None
        
        home_screen = self.controller.frames["HomeScreen"]
        home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")
    
    def print_using_local_data(self):
        """Fallback print method using locally stored file data"""
        try:
            from config.print_config import get_default_printer, check_printer_status, print_pdf_via_gdi, get_downloads_dir
            
            print(f"[PaymentScreen] === FALLBACK PRINT DEBUG ===")
            print(f"[PaymentScreen] file_name: {getattr(self, 'file_name', 'NOT SET')}")
            print(f"[PaymentScreen] color_mode: {getattr(self, 'color_mode', 'NOT SET')}")
            print(f"[PaymentScreen] page_size: {getattr(self, 'page_size', 'NOT SET')}")
            print(f"[PaymentScreen] page_range: {getattr(self, 'page_range', 'NOT SET')}")
            print(f"[PaymentScreen] num_copies: {getattr(self, 'num_copies', 'NOT SET')}")
            
            # Check if file_name is set
            if not hasattr(self, 'file_name') or not self.file_name:
                return False, "file_name is not set - cannot print without file name"
            
            # Get printer
            printer_name = get_default_printer()
            print(f"[PaymentScreen] Printer: {printer_name}")
            if not printer_name:
                return False, "No printer available"
            
            ready, msg = check_printer_status(printer_name)
            print(f"[PaymentScreen] Printer ready: {ready}, msg: {msg}")
            if not ready:
                return False, f"Printer not ready: {msg}"
            
            # Build file path
            downloads_dir = get_downloads_dir()
            # The file is saved as {job_id}_{filename}
            expected_filename = f"{self.job_id}_{os.path.basename(self.file_name)}"
            file_path = os.path.abspath(os.path.join(downloads_dir, expected_filename))
            
            print(f"[PaymentScreen] downloads_dir: {downloads_dir}")
            print(f"[PaymentScreen] Looking for file: {file_path}")
            print(f"[PaymentScreen] File exists: {os.path.exists(file_path)}")
            
            if not os.path.exists(file_path):
                # Try to list what files ARE in the downloads folder
                try:
                    files_in_dir = os.listdir(downloads_dir)
                    print(f"[PaymentScreen] Files in downloads dir: {files_in_dir[:5]}")  # Show first 5
                except Exception as e:
                    print(f"[PaymentScreen] Could not list downloads dir: {e}")
                return False, f"File not found: {expected_filename}"
            
            # Get print settings
            num_copies = int(getattr(self, 'num_copies', 1))
            if num_copies < 1:
                num_copies = 1
            
            print(f"[PaymentScreen] About to print {num_copies} copies...")
            
            # Print each copy
            for copy_idx in range(num_copies):
                print(f"[PaymentScreen] Printing copy {copy_idx + 1}/{num_copies}")
                ok, msg = print_pdf_via_gdi(
                    file_path,
                    printer_name,
                    color_mode=getattr(self, 'color_mode', 'colored'),
                    page_size=getattr(self, 'page_size', 'Letter'),
                    page_range=getattr(self, 'page_range', 'all'),
                    scale_mode='actual'
                )
                print(f"[PaymentScreen] Copy {copy_idx + 1} result: ok={ok}, msg={msg}")
                if not ok:
                    return False, f"Failed on copy {copy_idx + 1}: {msg}"
            
            print(f"[PaymentScreen] === FALLBACK PRINT SUCCESS ===")
            return True, f"Successfully printed {num_copies} copies"
            
        except Exception as e:
            print(f"[PaymentScreen] Fallback print exception: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)

    def update_job_status(self, status):
        try:
            print(f"[PaymentScreen] Updating job status to '{status}' for job_id: {self.job_id}")
            
            # Update both root level and details level
            root_ref = db.reference(f'jobs/print_jobs/{self.job_id}')
            root_ref.update({'status': status, 'updated_at': time.time()})
            print(f"[PaymentScreen] Root level updated: jobs/print_jobs/{self.job_id}")
            
            details_ref = db.reference(f'jobs/print_jobs/{self.job_id}/details/0')
            details_ref.update({'status': status, 'updated_at': time.time()})
            print(f"[PaymentScreen] Details level updated: jobs/print_jobs/{self.job_id}/details/0")
            
            print(f"[PaymentScreen] Successfully updated status to '{status}'")
        except Exception as e:
            print(f"[ERROR] Firebase update failed: {e}")
            import traceback
            traceback.print_exc()

    def _add_back_icon_button(self, parent, size=80):
        """Create a circular back arrow canvas and return it so callers can pack/grid it."""
        # Colors for better visibility
        circle_fill = "#e6e6e6"    # lighter gray for better contrast
        circle_outline = "#e6e6e6"  # darker gray outline for visibility
        arrow_color = "#000000"    # black arrow
        canvas = tk.Canvas(parent, width=size, height=size, bg="white", highlightthickness=0)
        # Geometry centered inside the circle (works for any size)
        margin = max(4, int(size * 0.08))
        circle_w = 0  # no visible border
        arrow_w = max(5, int(size * 0.09))
        circle = canvas.create_oval(margin, margin, size - margin, size - margin, outline=circle_outline, width=circle_w, fill=circle_fill)

        cx = size / 2.0
        cy = size / 2.0
        d = size - 2 * margin  # inner circle diameter
        arrow_span = 0.52 * d   # total width of arrow (head tip to tail end)
        head_len = 0.18 * d     # length of the triangular head
        head_half_h = 0.18 * d  # half-height of the triangular head

        head_tip_x = cx - arrow_span / 2.0
        head_base_x = head_tip_x + head_len
        # Compensate for round cap extending beyond tail by ~arrow_w/2 so extremes are symmetric
        tail_x = cx + arrow_span / 2.0 - (arrow_w / 2.0)

        # Draw arrow and then precisely center via its bounding box
        shaft = canvas.create_line(int(tail_x), int(cy), int(head_base_x), int(cy), fill=arrow_color, width=arrow_w, capstyle=tk.ROUND, tags=("arrow",))
        head = canvas.create_polygon(
            int(head_tip_x), int(cy),
            int(head_base_x), int(cy - head_half_h),
            int(head_base_x), int(cy + head_half_h),
            fill=arrow_color, outline=arrow_color, tags=("arrow",)
        )
        bx1, by1, bx2, by2 = canvas.bbox("arrow")
        arrow_cx = (bx1 + bx2) / 2.0
        arrow_cy = (by1 + by2) / 2.0
        # Use the circle's actual bbox center to avoid rounding artifacts
        cx1, cy1, cx2, cy2 = canvas.bbox(circle)
        ccx = (cx1 + cx2) / 2.0
        ccy = (cy1 + cy2) / 2.0
        canvas.move("arrow", ccx - arrow_cx, ccy - arrow_cy)

        def on_enter(_):
            # Keep outline matching background; no hover color change
            canvas.itemconfig(circle, outline=circle_outline)

        def on_leave(_):
            canvas.itemconfig(circle, outline=circle_outline)

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", lambda _: self.go_back_to_summary())
        return canvas

    def go_back_to_summary(self):
        """Navigate back to Summary screen (non-cancelling back action)."""
        # Clean up Arduino connection and stop listening
        self.stop_coin_thread = True
        if self.arduino:
            try:
                print("[INFO] Stopping Arduino listener before going back...")
                self.arduino.stop_listening()
                print("[INFO] Resetting payment state...")
                self.arduino.reset_payment()
                print("[INFO] Closing Arduino serial connection...")
                self.arduino.close()
                print("[INFO] Arduino cleaned up before returning to summary")
                # Wait for serial port to be released
                time.sleep(0.5)
            except Exception as e:
                print(f"[WARN] Error cleaning up Arduino: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.arduino = None
        
        # Cancel the job in Firebase when going back
        self.update_job_status('cancelled')
        
        try:
            if getattr(self, 'summary_context', None):
                self.controller.show_frame("SummaryScreen", data=self.summary_context)
            else:
                # Fallback: derive minimal summary data from controller
                options = self.controller.job_data or {}
                self.controller.show_frame("SummaryScreen", data=options)
        except Exception:
            # As a last resort, return to Options
            self.controller.show_frame("OptionsScreen", data=self.controller.job_data)
    
    def _update_dots_animation(self, canvas, dot_objects, frame_count):
        """Update the position of the dots to create a wave animation."""
        try:
            if not canvas.winfo_exists():
                return  # Stop animation if canvas no longer exists
                
            # Smaller, subtler animation parameters
            dot_radius = 6
            spacing = 12
            base_y = 21
            amplitude = 5  # Height of the wave
            speed = 0.2    # Speed of the wave
            
            for i, dot in enumerate(dot_objects):
                try:
                    # Calculate vertical offset using sine wave with phase shift for each dot
                    phase = frame_count * speed + (i * 2 * math.pi / 3)  # 120° phase shift between dots
                    y_offset = amplitude * math.sin(phase)
                    
                    # Update dot position
                    x = 5 + i * (dot_radius * 2 + spacing)
                    y = base_y + y_offset
                    
                    # Move the dot only if the canvas and dot still exist
                    if canvas.winfo_exists():
                        canvas.coords(dot, 
                                    x, y, 
                                    x + dot_radius * 2, 
                                    y + dot_radius * 2)
                except Exception:
                    continue  # Skip this dot if there's an error
                    
            # Schedule the next update only if the canvas still exists
            if canvas.winfo_exists():
                self.animation_id = canvas.after(50, self._update_dots_animation, canvas, dot_objects, frame_count + 1)
        except Exception:
            pass  # Stop animation if any error occurs
    
    def show_transition_screen(self, message="Processing...", value_text=None):
        """Show a transition screen with the specified message and animated dots.
        
        Args:
            message: Main message to display
            value_text: Optional value text to display below the main message (e.g., amount)
        """
        # Hide the transition screen if it already exists
        self.hide_transition_screen()
        
        # Create a new frame for the transition screen
        transition_frame = tk.Frame(self, bg="white")
        
        # Position the frame to fill the window
        transition_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
        
        # Main container for the loading content
        container = tk.Frame(transition_frame, bg="white")
        container.pack(expand=True)
        
        # Frame to hold both text and dots in a single line
        content_frame = tk.Frame(container, bg="white")
        content_frame.pack()
        
        # Add loading text
        text_label = tk.Label(
            content_frame,
            text=message,
            font=("Bebas Neue", 50),
            bg="white",
            fg="black"
        )
        text_label.pack(side=tk.LEFT)
        
        # Create a canvas for the animated dots (on the same line as the text)
        # Smaller canvas to match smaller dots, positioned slightly lower
        dots_canvas = tk.Canvas(content_frame, width=80, height=42, 
                              bg="white", highlightthickness=0)
        # Position the canvas to align with the text baseline
        dots_canvas.pack(side=tk.LEFT, pady=(22, 0))  # Shift dots a little further down
        
        # Create three smaller dots
        dot_radius = 5
        spacing = 8
        dot_objects = []
        
        # Position dots to align with the text baseline
        for i in range(3):
            x = 5 + i * (dot_radius * 2 + spacing)
            dot = dots_canvas.create_oval(
                x, 21,  # Start y-position aligned with animation base_y
                x + dot_radius * 2, 
                21 + dot_radius * 2,
                fill="black"
            )
            dot_objects.append(dot)
        
        # If value_text is provided, add it below the main message
        if value_text:
            value_label = tk.Label(
                container,
                text=value_text,
                font=("Bebas Neue", 90),  # Much bigger font size
                bg="white",
                fg="#b42e41"  # Brand red color for the value
            )
            value_label.pack(pady=(20, 0))
        
        # Store the canvas and dot objects references
        self._dots_canvas = dots_canvas
        self._dot_objects = dot_objects
        
        # Start the animation and store its ID
        self.animation_id = None
        self._update_dots_animation(dots_canvas, dot_objects, 0)
        
        # Store the transition frame reference
        self._transition_frame = transition_frame
        
        return transition_frame
        
    def hide_transition_screen(self):
        """Hide and destroy the transition screen if it exists."""
        # Cancel any pending animation update
        if hasattr(self, 'animation_id') and self.animation_id:
            try:
                if hasattr(self, '_dots_canvas') and self._dots_canvas.winfo_exists():
                    self._dots_canvas.after_cancel(self.animation_id)
            except Exception:
                pass
            self.animation_id = None
            
        # Clean up the transition frame
        if hasattr(self, '_transition_frame') and self._transition_frame.winfo_exists():
            self._transition_frame.destroy()
            
        # Clean up references
        if hasattr(self, '_dots_canvas'):
            delattr(self, '_dots_canvas')
        if hasattr(self, '_dot_objects'):
            delattr(self, '_dot_objects')
    
    def show_success_screen(self, message="Success!"):
        """Show a success screen without animated dots."""
        # Hide any existing transition screen
        self.hide_transition_screen()
        
        # Create a new frame for the success screen
        transition_frame = tk.Frame(self, bg="white")
        
        # Position the frame to fill the window
        transition_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
        
        # Main container for the content
        container = tk.Frame(transition_frame, bg="white")
        container.pack(expand=True)
        
        # Check if message contains newline (error with details)
        if '\n' in message:
            # Split into title and details
            parts = message.split('\n', 1)
            title = parts[0]
            details = parts[1] if len(parts) > 1 else ""
            
            # Add title text
            text_label = tk.Label(
                container,
                text=title,
                font=("Bebas Neue", 50),
                bg="white",
                fg="#b42e41"  # Brand red color
            )
            text_label.pack()
            
            # Add details text (smaller font)
            if details:
                details_label = tk.Label(
                    container,
                    text=details,
                    font=("Arial", 18),
                    bg="white",
                    fg="#333",
                    wraplength=800,
                    justify="center"
                )
                details_label.pack(pady=(10, 0))
        else:
            # Single line message
            text_label = tk.Label(
                container,
                text=message,
                font=("Bebas Neue", 50),
                bg="white",
                fg="#b42e41"  # Brand red color
            )
            text_label.pack()
        
        # Store the transition frame reference
        self._transition_frame = transition_frame
        
        return transition_frame

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