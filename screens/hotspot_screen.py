# hotspot_screen.py
"""
GUI screen for the hotspot file transfer functionality.
Displays QR code and connection information for users to upload files.
"""

import tkinter as tk
import os
import sys
import math
from PIL import Image, ImageTk
from datetime import datetime

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.hotspot_config import HotspotServer, HotspotConfig


class HotspotScreen(tk.Frame):
    """Hotspot screen integrated into the main app as a frame."""
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        
        # Hotspot configuration from config file
        self.hotspot_name = HotspotConfig.HOTSPOT_NAME
        self.hotspot_password = HotspotConfig.HOTSPOT_PASSWORD
        self.hotspot_url = HotspotConfig.get_hotspot_url()
        
        # File tracking
        self.files_received = 0
        
        # Job data storage
        self.pending_job_data = None
        
        # Initialize server with callback (will be started when screen is shown)
        self.hotspot_server = HotspotServer(
            port=HotspotConfig.DEFAULT_PORT,
            upload_directory=HotspotConfig.get_upload_directory(),
            callback=self.on_file_received
        )
        
        # Server running state
        self.server_running = False
        
        # Setup GUI
        self.create_widgets()
        
        # Bind events to reset global idle timer when user is active
        self.bind_all('<Any-KeyPress>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Any-Button>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Motion>', lambda e: self.controller._reset_global_idle_timer())
        
        # Fixed 5-minute session timer (not activity-based)
        self._idle_timer = None
    
    def start_server(self):
        """Start the hotspot server if not already running."""
        if not self.server_running:
            self.hotspot_server.start()
            self.server_running = True
            print("Hotspot server started.")
    
    def stop_server(self):
        """Stop the hotspot server if running."""
        if self.server_running:
            self.hotspot_server.stop()
            self.server_running = False
            print("Hotspot server stopped.")
    
    def load_data(self, data=None):
        """Called when the screen is shown. Start the server."""
        self.start_server()
        # Global idle timer is now managed by MainApp - disable local timer
        # self.reset_idle_timer()

    def create_widgets(self):
        """Create the hotspot screen widgets."""
        self._create_wifi_view_content()

    def _create_wifi_view_content(self):
        """Create the hotspot screen with the exact design as home screen."""
        # Get screen dimensions for scaling
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        
        # Padding
        outer_padx = int(50 * scale)
        header_top_pad = int(60 * scale)

        # Typography
        title_font_size = min(27, max(18, int(20 * scale)))
        title_font = ("Arial", title_font_size, "bold")
        wifi_title_font = ("Arial", max(20, int(24 * scale)), "bold")
        info_font = ("Arial", max(18, int(20 * scale)), "bold")
        status_font = ("Arial", max(16, int(18 * scale)))
        url_font = ("Arial", max(14, int(16 * scale)), "bold")

        # Top bar (back icon + title + paper counts)
        header = tk.Frame(self, bg="white")
        header.pack(fill="x", pady=(header_top_pad, 0))
        header_inner = tk.Frame(header, bg="white")
        header_inner.pack(fill="x", padx=89)  # Match the main content container padding
        
        # Left side: Back arrow
        left_header = tk.Frame(header_inner, bg="white")
        left_header.pack(side="left")
        
        # Back arrow button (same size as summary screen)
        back_size = 89
        back_canvas = self._add_back_icon_button_styled(left_header, size=back_size)
        back_canvas.pack(side="left")
        
        # Title
        tk.Label(left_header, text="Connect to Wi-Fi Hotspot and scan the QR code", 
                font=title_font, bg="white").pack(side="left", padx=int(16 * scale))
        
        # Paper counts container (flows after title)
        paper_outer = tk.Frame(left_header, bg="white")
        paper_outer.pack(side="left")
        
        # Create rounded container with canvas
        container_width = int(330 * scale)
        container_height = int(70 * scale)
        container_radius = 10
        container_bg = "#e8e9eb"  # Darker gray background
        
        paper_canvas = tk.Canvas(paper_outer, width=container_width, height=container_height,
                                bg="white", highlightthickness=0)
        paper_canvas.pack()
        
        # Draw rounded rectangle background
        self._draw_round_rect(paper_canvas, 0, 0, container_width, container_height,
                             container_radius, fill=container_bg, outline='')
        
        # Inner frame for content (horizontal layout with icon on left)
        paper_main_frame = tk.Frame(paper_canvas, bg=container_bg)
        paper_canvas.create_window(container_width // 2, container_height // 2,
                                   window=paper_main_frame, anchor="center")
        
        paper_font = ("Arial", max(12, int(13 * scale)), "bold")
        label_font = ("Arial", max(10, int(11 * scale)))
        
        # Warning icon on the left (vertically centered)
        icon_size = int(32 * scale)
        icon_canvas = tk.Canvas(paper_main_frame, width=icon_size, height=icon_size,
                               bg=container_bg, highlightthickness=0)
        icon_canvas.pack(side="left", padx=(6, 8))
        
        # Draw warning triangle
        triangle_color = "#ffc107"  # Amber/warning color
        points = [
            icon_size // 2, 3,  # Top point
            3, icon_size - 3,   # Bottom left
            icon_size - 3, icon_size - 3  # Bottom right
        ]
        icon_canvas.create_polygon(points, fill=triangle_color, outline=triangle_color)
        
        # Draw exclamation mark
        mark_color = "#000"
        mark_width = max(2, int(icon_size * 0.06))
        # Exclamation line (taller)
        icon_canvas.create_rectangle(
            icon_size // 2 - mark_width, icon_size * 0.3,
            icon_size // 2 + mark_width, icon_size * 0.6,
            fill=mark_color, outline=mark_color
        )
        # Exclamation dot
        dot_size = max(3, int(icon_size * 0.08))
        icon_canvas.create_oval(
            icon_size // 2 - dot_size, icon_size * 0.68,
            icon_size // 2 + dot_size, icon_size * 0.68 + dot_size * 2,
            fill=mark_color, outline=mark_color
        )
        
        # Right side: vertical stack with label and counts
        right_content = tk.Frame(paper_main_frame, bg=container_bg)
        right_content.pack(side="left", padx=(0, 6), pady=6)
        
        # Top row: "Remaining Paper:" label
        remaining_label = tk.Label(
            right_content,
            text="Remaining Paper:",
            font=label_font,
            bg=container_bg,
            fg="#555"
        )
        remaining_label.pack(anchor="center", pady=(0, 4))
        
        # Bottom row: Paper counts
        paper_info_frame = tk.Frame(right_content, bg=container_bg)
        paper_info_frame.pack(anchor="center")
        
        # Letter paper count
        short_label = tk.Label(
            paper_info_frame,
            text="Letter: 100 sheets",
            font=paper_font,
            bg=container_bg,
            fg="#333"
        )
        short_label.pack(side="left", padx=(0, 6))
        
        # Separator line
        separator = tk.Frame(paper_info_frame, bg="#b0b3b8", width=2, height=int(26 * scale))
        separator.pack(side="left", padx=6)
        
        # A4 paper count
        a4_label = tk.Label(
            paper_info_frame,
            text="A4: 100 sheets",
            font=paper_font,
            bg=container_bg,
            fg="#333"
        )
        a4_label.pack(side="left", padx=(6, 0))
        
        # Store references for updating
        self.short_paper_label = short_label
        self.a4_paper_label = a4_label
        
        # Fetch and display initial paper counts from Firebase (with delay to ensure widgets are ready)
        self.after(100, self.fetch_paper_counts)

        # Centered content column
        center = tk.Frame(self, bg="white")
        center.pack(expand=True, fill="x")

        # Light gray rounded container with 1 inch (96 pixels) padding on left and right
        container_frame, container = self._rounded_container(
            center, bg="#e6e6e6", radius=15, padding=int(16 * scale)
        )
        container_frame.pack(fill="x", expand=False, padx=89, pady=(0, int(30 * scale)))

        # Two columns side-by-side (50/50 widths)
        cards = tk.Frame(container, bg="#e6e6e6")
        cards.pack(fill="both", expand=True, padx=int(24 * scale), pady=int(24 * scale))
        cards.grid_columnconfigure(0, weight=1, uniform="cards")
        cards.grid_columnconfigure(1, weight=1, uniform="cards")
        cards.grid_rowconfigure(0, weight=1)

        # Left side: QR Code directly on gray background (no card)
        qr_container = tk.Frame(cards, bg="#e6e6e6")
        qr_container.grid(row=0, column=0, sticky="nsew", padx=(int(15 * scale), int(15 * scale)))

        # QR Code centered
        qr_inner = tk.Frame(qr_container, bg="#e6e6e6")
        qr_inner.pack(expand=True)

        # Generate and display QR code dynamically for local hotspot IP
        try:
            # Generate QR code for the local hotspot URL
            qr_image = HotspotConfig.generate_qr_code(port=HotspotConfig.DEFAULT_PORT)
            
            # Resize the QR code image
            qr_image_resized = qr_image.resize((475, 450), Image.Resampling.LANCZOS)
            self.qr_photo = ImageTk.PhotoImage(qr_image_resized)
            qr_label = tk.Label(qr_inner, image=self.qr_photo, bg="#e6e6e6")
            qr_label.pack(pady=(10, 10))
            print(f"QR code generated successfully for URL: {HotspotConfig.get_hotspot_url()}")
        except Exception as e:
            print(f"Error generating QR code: {e}")
            qr_label = tk.Label(qr_inner, text="QR Code Generation Failed", 
                              font=("Arial", 14), bg="#e6e6e6", fg="red")
            qr_label.pack(pady=(10, 10))

        # URL below QR code in red color - show the actual hotspot URL
        hotspot_url = HotspotConfig.get_hotspot_url()
        url_label = tk.Label(
            qr_inner,
            text=hotspot_url,
            font=url_font,
            bg="#e6e6e6",
            fg="#b42e41"
        )
        url_label.pack(pady=(0, 10))

        # Right Card: Logo, Wi-Fi info and status (rounded, compact size)
        brand_red = "#b42e41"
        
        # Container to center the card vertically
        right_container = tk.Frame(cards, bg="#e6e6e6")
        right_container.grid(row=0, column=1, sticky="nsew", padx=(int(15 * scale), int(15 * scale)))
        
        # Center frame
        right_center = tk.Frame(right_container, bg="#e6e6e6")
        right_center.pack(expand=True, fill="both", pady=(int(8 * scale), 0))
        
        right_frame, right = self._rounded_container(
            right_center, bg="white", radius=15, padding=int(10 * scale), fill_x=True, vcenter=False
        )
        right_frame.pack(fill="x", expand=False, padx=int(10 * scale), anchor="n")
        right_frame.config(height=int(430 * scale))
        right_frame.pack_propagate(False)  # Prevent the frame from shrinking to fit its contents

        # Logo at the top of right card
        logo_holder = tk.Frame(right, bg="white")
        logo_holder.pack(pady=(int(20 * scale), int(10 * scale)))
        self._load_logo(logo_holder, scale, max_w=int(380 * scale))

        # Content box for Wi-Fi info
        wifi_content = tk.Frame(right, bg="white")
        wifi_content.pack(pady=(int(15 * scale), 0))

        # Wi-Fi Hotspot title
        wifi_title = tk.Label(
            wifi_content,
            text="Wi-Fi Hotspot",
            font=wifi_title_font,
            bg="white",
            fg="#333"
        )
        wifi_title.pack(anchor="w", pady=(0, int(10 * scale)))

        # Network info
        network_label = tk.Label(
            wifi_content,
            text="Network : PrintQueuesk Hotspot",
            font=info_font,
            bg="white",
            fg=brand_red
        )
        network_label.pack(anchor="w", pady=int(5 * scale))

        password_label = tk.Label(
            wifi_content,
            text="Password : PrintQueuesk123",
            font=info_font,
            bg="white",
            fg="black"
        )
        password_label.pack(anchor="w", pady=int(5 * scale))

        # Status message
        self.files_counter_label = tk.Label(
            wifi_content,
            text="Waiting For Files...",
            font=status_font,
            bg="white",
            fg="#333"
        )
        self.files_counter_label.pack(anchor="center", pady=(int(30 * scale), int(25 * scale)))

    def _add_back_icon_button_styled(self, parent, size=80):
        """Create a circular back arrow canvas with gray fill matching summary screen."""
        circle_fill = "#e6e6e6"
        circle_outline = "#e6e6e6"
        arrow_color = "#000000"
        canvas = tk.Canvas(parent, width=size, height=size, bg="white", highlightthickness=0)
        
        margin = max(4, int(size * 0.08))
        circle_w = 0
        arrow_w = max(5, int(size * 0.09))
        circle = canvas.create_oval(margin, margin, size - margin, size - margin, 
                                    outline=circle_outline, width=circle_w, fill=circle_fill)

        cx = size / 2.0
        cy = size / 2.0
        d = size - 2 * margin
        arrow_span = 0.52 * d
        head_len = 0.18 * d
        head_half_h = 0.18 * d

        head_tip_x = cx - arrow_span / 2.0
        head_base_x = head_tip_x + head_len
        tail_x = cx + arrow_span / 2.0 - (arrow_w / 2.0)

        shaft = canvas.create_line(int(tail_x), int(cy), int(head_base_x), int(cy), 
                                  fill=arrow_color, width=arrow_w, capstyle=tk.ROUND, tags=("arrow",))
        head = canvas.create_polygon(
            int(head_tip_x), int(cy),
            int(head_base_x), int(cy - head_half_h),
            int(head_base_x), int(cy + head_half_h),
            fill=arrow_color, outline=arrow_color, tags=("arrow",)
        )
        
        bx1, by1, bx2, by2 = canvas.bbox("arrow")
        arrow_cx = (bx1 + bx2) / 2.0
        arrow_cy = (by1 + by2) / 2.0
        cx1, cy1, cx2, cy2 = canvas.bbox(circle)
        ccx = (cx1 + cx2) / 2.0
        ccy = (cy1 + cy2) / 2.0
        canvas.move("arrow", ccx - arrow_cx, ccy - arrow_cy)

        def on_enter(_):
            canvas.itemconfig(circle, outline=circle_outline)

        def on_leave(_):
            canvas.itemconfig(circle, outline=circle_outline)

        def on_click(_):
            # Don't navigate if idle confirmation modal is visible
            if self.controller.idle_modal_visible:
                print("[HotspotScreen] Idle modal visible - ignoring back button click")
                return
            # Navigate back to home screen
            self.stop_server()
            self.controller.show_frame("HomeScreen")

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)
        return canvas

    def _draw_round_rect(self, canvas, x1, y1, x2, y2, r, fill, outline='', tag=None, width=1):
        """Draw a rounded rectangle using individual shapes for proper rounded corners"""
        if r <= 0 or x2 - x1 < 2*r or y2 - y1 < 2*r:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline if outline else '', 
                                  width=width, tags=(tag,) if tag else None)
            return
        
        # Draw filled shapes with the tag
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline='', tags=(tag,) if tag else None)
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
        
        if outline and width > 0:
            canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)

    def _rounded_container(self, parent, bg="#ffffff", radius=10, padding=16, fill_x=True, vcenter=False):
        """Create a container with a rounded background and return (wrapper, inner)."""
        parent_bg = parent.cget("bg")
        wrapper = tk.Frame(parent, bg=parent_bg)
        canvas = tk.Canvas(wrapper, bg=parent_bg, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg=bg)
        win = canvas.create_window(padding, padding, anchor="nw", window=inner)

        def _refresh(_=None):
            wrapper.update_idletasks()
            wrapper_w = max(wrapper.winfo_width(), 1)
            wrapper_h = max(wrapper.winfo_height(), 1)

            inner.update_idletasks()
            content_w_initial = inner.winfo_reqwidth() + padding * 2
            w = max(wrapper_w, 40) if fill_x else max(content_w_initial, 40)

            canvas.config(width=w)
            try:
                canvas.itemconfig(win, width=max(w - padding * 2, 10))
            except Exception:
                pass

            try:
                inner.update_idletasks()
                canvas.update_idletasks()
            except Exception:
                pass
            content_h = inner.winfo_reqheight() + padding * 2
            h = max(wrapper_h if wrapper_h > 1 else content_h, content_h, 40)

            canvas.config(width=w, height=h)
            canvas.delete("rounded_bg")
            self._draw_round_rect(canvas, 0, 0, w, h, radius, fill=bg, outline='', tag="rounded_bg")
            canvas.tag_lower("rounded_bg")
            
            available_h = max(h - padding * 2, 0)
            if vcenter and available_h > 0:
                try:
                    canvas.itemconfig(win, height=available_h)
                except Exception:
                    pass
            canvas.coords(win, padding, padding)

            try:
                inner.update_idletasks()
                new_h = inner.winfo_reqheight() + padding * 2
                wrapper.update_idletasks()
                wrapper_h = max(wrapper.winfo_height(), 1)
                final_h = max(wrapper_h if wrapper_h > 1 else new_h, new_h, h)
                if final_h > h:
                    h = final_h
                    canvas.config(height=h)
                    canvas.delete("rounded_bg")
                    self._draw_round_rect(canvas, 0, 0, w, h, radius, fill=bg, outline='', tag="rounded_bg")
                    canvas.tag_lower("rounded_bg")
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
            
            # Simply load and resize the logo without transparency manipulation
            logo_img = Image.open(logo_path)
            
            # Convert to RGB if it's RGBA to avoid transparency issues
            if logo_img.mode == 'RGBA':
                # Create white background
                background = Image.new('RGB', logo_img.size, (255, 255, 255))
                background.paste(logo_img, mask=logo_img.split()[3] if len(logo_img.split()) > 3 else None)
                logo_img = background
            elif logo_img.mode != 'RGB':
                logo_img = logo_img.convert('RGB')
            
            # Scale
            if max_w is not None:
                target_w = int(max_w)
            else:
                target_w = int(200 * scale)
            
            w, h = logo_img.size
            aspect = h / w
            target_h = int(target_w * aspect)
            resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            self.logo_photo = ImageTk.PhotoImage(resized)
            logo_label = tk.Label(parent, image=self.logo_photo, bg="white", bd=0, highlightthickness=0)
            logo_label.pack()
        except Exception as e:
            print(f"Error loading logo: {e}")
            import traceback
            traceback.print_exc()
            # Fallback text
            logo_label = tk.Label(parent, text="PRINTECH", font=("Arial", int(24 * scale), "bold"), 
                                bg="white", fg="#333")
            logo_label.pack()
    
    def on_file_received(self, filepath, job_data):
        """Callback when a file is received"""
        self.files_received += 1
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] File received: {filename}")
        print(f"Total files received: {self.files_received}")
        print(f"Saved to: {filepath}")
        
        # Store job data
        self.pending_job_data = job_data
        
        # Update GUI counter and show transition (must be called from main thread)
        self.after(0, self._process_received_file)
    
    def _process_received_file(self):
        """Process the received file and navigate to options screen."""
        # Show transition screen
        self.show_transition_screen()
        
        # Navigate to options screen after a short delay
        self.after(1500, self._navigate_to_options)
    
    def _navigate_to_options(self):
        """Navigate to options screen with the job data."""
        if self.pending_job_data:
            # Hide transition screen
            self.hide_transition_screen()
            
            # Stop the server
            self.stop_server()
            
            # Navigate to options screen
            self.controller.show_frame("OptionsScreen", data=self.pending_job_data)
            
            # Reset pending job data
            self.pending_job_data = None
    
    def show_transition_screen(self):
        """Show a transition screen while preparing files with an animated loading message."""
        # Create a new frame for the transition screen
        transition_frame = tk.Frame(self, bg="white")
        
        # Position the frame to fill the window
        transition_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
        
        # Main container for the loading content (horizontal layout)
        container = tk.Frame(transition_frame, bg="white")
        container.pack(expand=True)
        
        # Frame to hold both text and dots in a single line
        content_frame = tk.Frame(container, bg="white")
        content_frame.pack(expand=True)
        
        # Add loading text
        text_label = tk.Label(
            content_frame,
            text="Preparing your print job",
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
        
        # Store the canvas and dot objects references
        self._dots_canvas = dots_canvas
        self._dot_objects = dot_objects
        
        # Start the animation and store its ID
        self.animation_id = None
        self._update_dots_animation(dots_canvas, dot_objects, 0)
        
        # Store the transition frame reference
        self._transition_frame = transition_frame
        
        return transition_frame
    
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
    
    def _draw_round_rect(self, canvas, x1, y1, x2, y2, r, fill, outline='', tag=None, width=1):
        """Draw a rounded rectangle using individual shapes for proper rounded corners"""
        if r <= 0 or x2 - x1 < 2*r or y2 - y1 < 2*r:
            canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline if outline else '', 
                                  width=width, tags=(tag,) if tag else None)
            return
        
        # Draw filled shapes with the tag
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline='', tags=(tag,) if tag else None)
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
        
        if outline and width > 0:
            canvas.create_arc(x1, y1, x1 + 2*r, y1 + 2*r, start=90, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y1, x2, y1 + 2*r, start=0, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x1, y2 - 2*r, x1 + 2*r, y2, start=180, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_arc(x2 - 2*r, y2 - 2*r, x2, y2, start=270, extent=90, 
                            outline=outline, width=width, style='arc', tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)
            canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=(tag,) if tag else None)
    
    def update_paper_count(self, short_count, a4_count):
        """Update the remaining paper count display."""
        if hasattr(self, 'short_paper_label'):
            self.short_paper_label.config(text=f"Letter: {short_count} sheets")
        if hasattr(self, 'a4_paper_label'):
            self.a4_paper_label.config(text=f"A4: {a4_count} sheets")
    
    def fetch_paper_counts(self):
        """Fetch paper inventory counts from Firebase and update display."""
        try:
            from config.firebase_config import db
            
            # Fetch from printer_status (same path as dashboard)
            printer_status_ref = db.reference('resources/paper/printer_status')
            statuses = printer_status_ref.order_by_child('updated_at').limit_to_last(1).get()
            
            print(f"[HotspotScreen] Printer status data: {statuses}")
            
            if statuses:
                # Get the latest status entry
                latest_status = list(statuses.values())[0]
                
                # Get Letter and A4 paper counts
                letter_count = latest_status.get('remaining_paper_letter', 100)
                a4_count = latest_status.get('remaining_paper_a4', 100)
                
                # Convert to integers
                try:
                    letter_count = int(letter_count) if letter_count is not None and letter_count != '' else 100
                except (ValueError, TypeError):
                    letter_count = 100
                    
                try:
                    a4_count = int(a4_count) if a4_count is not None and a4_count != '' else 100
                except (ValueError, TypeError):
                    a4_count = 100
                
                print(f"[HotspotScreen] Letter: {letter_count}, A4: {a4_count}")
                self.update_paper_count(letter_count, a4_count)
            else:
                print("[HotspotScreen] No printer_status data found, using defaults")
                self.update_paper_count(100, 100)
            
        except Exception as e:
            print(f"[HotspotScreen] Error fetching paper counts: {e}")
            import traceback
            traceback.print_exc()
            self.update_paper_count(100, 100)
    
    def reset_idle_timer(self):
        # Cancel previous timer if exists
        if hasattr(self, '_idle_timer') and self._idle_timer:
            self.after_cancel(self._idle_timer)
        # Set new timer for 5 minutes (300,000 ms)
        self._idle_timer = self.after(300000, self._on_idle_timeout)

    def _on_idle_timeout(self):
        # Go back to home screen automatically and stop the hotspot server
        try:
            self.stop_server()
        except Exception:
            pass
        home_screen = self.controller.frames["HomeScreen"]
        home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")