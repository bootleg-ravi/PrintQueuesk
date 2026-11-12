# screens/home_screen.py

import tkinter as tk
import os
import math
from PIL import Image, ImageTk
from config.firebase_config import db

class HomeScreen(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.job_labels = {}
        self.carousel_images = []
        self.carousel_index = 0
        self.carousel_active = False
        self.carousel_label = None
        self.carousel_frame = None
        self.home_active = True
        self._idle_timer = None
        self._carousel_timer = None
        self._paper_refresh_timer = None
        self.create_widgets()
        # Don't bind globally - only bind when on main view to avoid interfering with idle timers
        self._bind_main_view_events()

    def _bind_main_view_events(self):
        """Bind events only when on main view (home_active=True)."""
        self.bind_all('<Any-KeyPress>', lambda e: self._on_user_activity())
        self.bind_all('<Any-Button>', lambda e: self._on_user_activity())
        self.bind_all('<Motion>', lambda e: self._on_user_activity())
        self._reset_idle_timer()

    def _unbind_main_view_events(self):
        """Unbind events when switching away from main view (WiFi/QR view)."""
        try:
            self.unbind_all('<Any-KeyPress>')
            self.unbind_all('<Any-Button>')
            self.unbind_all('<Motion>')
        except Exception:
            pass

    def create_widgets(self):
        # This frame holds both the main view and the wifi viewx
        self.main_view = tk.Frame(self, bg="white")
        self.main_view.pack(expand=True, fill="both")  

        self.wifi_view = tk.Frame(self, bg="white")
        # Initially, wifi_view is not packed

        self._create_main_view_content()
        self._create_wifi_view_content()

    def _create_main_view_content(self):
        center_frame = tk.Frame(self.main_view, bg="white")
        center_frame.pack(expand=True)

        # Logo
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, 'static', 'img', 'logo.png')
            print(f"Loading logo from: {logo_path}") 
            logo_image = Image.open(logo_path).resize((995, 275), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(center_frame, image=self.logo_photo, bg="white")
            logo_label.pack(pady=(50, 10))
        except Exception as e:
            print(f"Error loading logo: {e}")
            raise  # Re-raise the exception to see the full traceback

        # Buttons frame
        buttons_frame = tk.Frame(center_frame, bg="white")
        buttons_frame.pack(pady=40)

        # Start Button
        start_button = tk.Button(
            buttons_frame,
            text="Start Printing",
            font=("Bebas Neue", 50),
            bg="#b42e41", fg="white",
            activebackground="#d12246", activeforeground="white",
            relief=tk.FLAT, bd=0, padx=30, pady=20,
            command=self.show_wifi_view
        )
        start_button.pack(pady=(0, 0))

    def _create_wifi_view_content(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        outer_padx = int(50 * scale)
        header_top_pad = int(60 * scale)

        # Typography
        title_font_size = min(25, max(18, int(20 * scale)))
        title_font = ("Arial", title_font_size, "bold")
        status_font = ("Arial", max(28, int(32 * scale)))
        button_font = ("Arial", max(16, int(20 * scale)), "bold")
        url_font = ("Arial", max(14, int(16 * scale)), "bold")

        # Top bar (back icon + title + paper counts)
        header = tk.Frame(self.wifi_view, bg="white")
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
        tk.Label(left_header, text="Scan the QR code or send the file via Hotspot", 
                font=title_font, bg="white").pack(side="left", padx=int(16 * scale))
        
        # Paper counts container (flows after title)
        paper_outer = tk.Frame(left_header, bg="white")
        paper_outer.pack(side="left")
        
        # Create rounded container with canvas
        container_width = int(330 * scale)
        container_height = int(70 * scale)
        container_radius = 10
        container_bg = "#e8e9eb" 
        
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
        triangle_color = "#ffc107"
        points = [
            icon_size // 2, 3,  
            3, icon_size - 3,  
            icon_size - 3, icon_size - 3  
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

        # Centered content column
        center = tk.Frame(self.wifi_view, bg="white")
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

        try:
            qr_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'img', 'qr-code.png')
            print(f"Loading QR code from: {qr_path}")
            qr_image = Image.open(qr_path).resize((475, 450), Image.Resampling.LANCZOS)
            self.qr_photo = ImageTk.PhotoImage(qr_image)
            qr_label = tk.Label(qr_inner, image=self.qr_photo, bg="#e6e6e6")
            qr_label.pack(pady=(10, 10))
        except Exception as e:
            print(f"Error loading QR code: {e}")
            qr_label = tk.Label(qr_inner, text="QR Code Not Found", 
                              font=("Arial", 14), bg="#e6e6e6", fg="red")
            qr_label.pack(pady=(10, 10))

        # URL below QR code in red color
        url_label = tk.Label(
            qr_inner,
            text="https://printqueuesk.azurewebsites.net",
            font=url_font,
            bg="#e6e6e6",
            fg="#b42e41"
        )
        url_label.pack(pady=(0, 10))
        
        # Fetch and display initial paper counts from Firebase (with delay to ensure widgets are ready)
        self.after(100, self.fetch_paper_counts)

        # Right Card: Logo, Status and Button (rounded, compact size)
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

        # Content box for status and button - no expandable spacers
        price_content = tk.Frame(right, bg="white")
        price_content.pack(pady=(int(15 * scale), 0))

        # Status message
        self.status_label = tk.Label(
            price_content,
            text="Waiting For Files...",
            font=status_font,
            bg="white",
            fg="#333"
        )
        self.status_label.pack(anchor="center", pady=(int(30 * scale), int(45 * scale)))

        # Button container for buttons stacked vertically
        button_container = tk.Frame(price_content, bg="white")
        button_container.pack(anchor="center", pady=(int(10 * scale), int(5 * scale)))
        
        # Button dimensions
        button_width = int(380 * scale)
        button_height = int(60 * scale)
        button_radius = 8
        
        # Hotspot button (top)
        hotspot_frame = tk.Frame(button_container, bg="white", width=button_width, height=button_height)
        hotspot_frame.pack(pady=(0, int(15 * scale)))
        hotspot_frame.pack_propagate(False)
        
        hotspot_canvas = tk.Canvas(hotspot_frame, width=button_width, height=button_height, 
                                   bg="white", highlightthickness=0)
        hotspot_canvas.place(relx=0, rely=0)
        
        self._draw_round_rect(hotspot_canvas, 0, 0, button_width, button_height, 
                             button_radius, fill=brand_red, outline='')
        
        hotspot_button = tk.Button(
            hotspot_canvas,
            text="Receive File via Hotspot",
            font=button_font,
            bg=brand_red, 
            fg="white",
            activebackground="#d12246", 
            activeforeground="white",
            relief=tk.FLAT, 
            bd=0,
            command=self.launch_hotspot_screen,
            cursor="hand2"
        )
        hotspot_button.place(relx=0.5, rely=0.5, anchor="center")
        
        # USB button (bottom) - same color as hotspot
        usb_frame = tk.Frame(button_container, bg="white", width=button_width, height=button_height)
        usb_frame.pack()
        usb_frame.pack_propagate(False)
        
        usb_canvas = tk.Canvas(usb_frame, width=button_width, height=button_height,
                              bg="white", highlightthickness=0)
        usb_canvas.place(relx=0, rely=0)
        
        self._draw_round_rect(usb_canvas, 0, 0, button_width, button_height,
                             button_radius, fill=brand_red, outline='')
        
        usb_button = tk.Button(
            usb_canvas,
            text="Transfer via USB Drive",
            font=button_font,
            bg=brand_red,
            fg="white",
            activebackground="#d12246",
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            command=self.show_usb_drive_screen,
            cursor="hand2"
        )
        usb_button.place(relx=0.5, rely=0.5, anchor="center")

    def _add_back_icon_button(self, parent):
        """Create a top-left circular back arrow button with no rectangular background."""
        # Canvas size and styling
        size = 80
        pad = 20
        color = "#6c757d" 

        canvas = tk.Canvas(parent, width=size, height=size, bg="white", highlightthickness=0)
        # Place at top-left corner
        canvas.place(x=pad, y=pad)

        # Draw circle
        margin = 8
        self._back_circle = canvas.create_oval(
            margin, margin, size - margin, size - margin,
            outline=color, width=3
        )

        # Draw a wide left arrow inside the circle
        # Shaft
        shaft_y = size // 2
        shaft_start_x = margin + 44  
        shaft_end_x = margin + 22    
        self._back_shaft = canvas.create_line(
            shaft_start_x, shaft_y, shaft_end_x, shaft_y,
            fill=color, width=5, capstyle=tk.ROUND
        )
        # Arrow head (triangle) pointing left
        head_tip_x = margin + 16
        head_top_y = shaft_y - 10
        head_bot_y = shaft_y + 10
        self._back_head = canvas.create_polygon(
            head_tip_x, shaft_y,
            head_tip_x + 12, head_top_y,
            head_tip_x + 12, head_bot_y,
            fill=color, outline=color
        )

        # Hover effects (optional subtle tint)
        def on_enter(_):
            canvas.itemconfig(self._back_circle, outline="#4f5961")
            canvas.itemconfig(self._back_shaft, fill="#4f5961")
            canvas.itemconfig(self._back_head, fill="#4f5961", outline="#4f5961")

        def on_leave(_):
            canvas.itemconfig(self._back_circle, outline=color)
            canvas.itemconfig(self._back_shaft, fill=color)
            canvas.itemconfig(self._back_head, fill=color, outline=color)

        def on_click(_):
            self.show_main_view()

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", on_click)

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

        canvas.bind("<Enter>", on_enter)
        canvas.bind("<Leave>", on_leave)
        canvas.bind("<Button-1>", lambda _: self.show_main_view())
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
                target_w = min(max(320, int(560 * scale)), 900)
            w, h = logo_img.size
            target_h = int(h * (target_w / w))
            resized = logo_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            
            self._logo_tk = ImageTk.PhotoImage(resized)
            bg_color = parent.cget("bg") if hasattr(parent, "cget") else "white"
            tk.Label(parent, image=self._logo_tk, bg=bg_color, bd=0, highlightthickness=0).pack()
        except Exception as e:
            print(f"[HomeScreen] Logo load failed: {e}")
            import traceback
            traceback.print_exc()
            bg_color = parent.cget("bg") if hasattr(parent, "cget") else "white"
            tk.Label(parent, text="PRINTQUEUESK", font=("Arial", max(24, int(48 * scale)), "bold"), 
                    bg=bg_color, fg="#000").pack()

    def _reset_idle_timer(self):
        """Reset the carousel idle timer (30 seconds on home screen)."""
        if self._idle_timer:
            self.after_cancel(self._idle_timer)
            print(f"[HomeScreen] Canceled existing carousel timer")
        if self.home_active:
            # 30 seconds for carousel to start
            self._idle_timer = self.after(30000, self._start_carousel)
            print(f"[HomeScreen] Started new carousel timer (30 seconds)")
        else:
            self._idle_timer = None
            print(f"[HomeScreen] Carousel timer set to None (not on home screen)")

    def _on_user_activity(self):
        """Called when user interacts with the screen."""
        if self.carousel_active:
            self._stop_carousel()
        # Only reset the carousel idle timer if on main home screen
        # On QR code view, the global idle timer in MainApp will handle it
        if self.home_active:
            print(f"[HomeScreen] User activity detected - resetting carousel timer")
            self._reset_idle_timer()
        else:
            print(f"[HomeScreen] User activity detected - on QR code view (not resetting carousel timer)")

    def _start_carousel(self):
        print(f"[HomeScreen] _start_carousel called (home_active={self.home_active})")
        self.carousel_active = True
        self._load_carousel_images()
        self._show_carousel_image()
        self._schedule_next_carousel()

    def _stop_carousel(self):
        self.carousel_active = False
        if self._carousel_timer:
            self.after_cancel(self._carousel_timer)
            self._carousel_timer = None
        if self.carousel_label:
            self.carousel_label.pack_forget()
            self.carousel_label.destroy()
            self.carousel_label = None
        if self.carousel_frame:
            self.carousel_frame.pack_forget()
            self.carousel_frame.destroy()
            self.carousel_frame = None
        self.show_main_view()

    def _load_carousel_images(self):
        # Load images from static/img/
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_dir = os.path.join(base_dir, 'static', 'img')
        img_files = ['1.png', '2.png', '3.png', '4.png', '5.png', '6.png', '7.png','8.png','9.png']
        self.carousel_image_paths = []
        for fname in img_files:
            path = os.path.join(img_dir, fname)
            if os.path.exists(path):    
                self.carousel_image_paths.append(path)
        self.carousel_index = 0

    def _show_carousel_image(self):
        # Safety check: if no images loaded, stop carousel
        if not self.carousel_image_paths:
            print("[HomeScreen] No carousel images found")
            self.carousel_active = False
            return
            
        if self.carousel_frame:
            self.carousel_frame.place_forget()
            self.carousel_frame.destroy()
        self.carousel_frame = tk.Frame(self, bg="white")
        self.carousel_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        # Resize image to fit 1440x900, maintain aspect ratio, center
        target_w = 1280
        target_h = 1280
        img_path = self.carousel_image_paths[self.carousel_index]
        from PIL import Image, ImageTk
        img = Image.open(img_path)
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_w = target_w
            new_h = int(target_w / img_ratio)
        else:
            new_h = target_h
            new_w = int(target_h * img_ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        full_img = ImageTk.PhotoImage(img)
        self.carousel_label = tk.Label(self.carousel_frame, image=full_img, bg="white")
        self.carousel_label.image = full_img
        self.carousel_label.place(relx=0.5, rely=0.5, anchor="center")
        # Explicit event bindings for user activity
        for widget in [self.carousel_frame, self.carousel_label]:
            widget.bind('<Button>', lambda e: self._on_user_activity())
            widget.bind('<Motion>', lambda e: self._on_user_activity())
        self.bind_all('<Key>', lambda e: self._on_user_activity())

    def _schedule_next_carousel(self):
        if not self.carousel_active or not self.carousel_image_paths:
            return
        self._carousel_timer = self.after(10000, self._next_carousel_image)  # 10 seconds

    def _next_carousel_image(self):
        if not self.carousel_active:
            return
        self.carousel_index = (self.carousel_index + 1) % len(self.carousel_image_paths)
        self._show_carousel_image()
        self._schedule_next_carousel()

    def show_wifi_view(self):
        self.home_active = False
        self._unbind_main_view_events()  # Unbind carousel timer events to prevent interference
        self.main_view.pack_forget()
        # Fetch paper counts first to determine whether to show a remaining paper notice
        self.fetch_paper_counts()
        self.wifi_view.pack(expand=True, fill="both")
        self.set_status("Waiting for files...")
        
        # Show Remaining Paper modal when start button is clicked
        try:
            letter = getattr(self, '_letter_count', 100)
            a4 = getattr(self, '_a4_count', 100)
            # Always show the remaining paper modal on start
            self.show_remaining_paper_modal(letter, a4)
        except Exception:
            pass

        # Fetch and check ink levels
        try:
            self.fetch_ink_levels()
        except Exception:
            pass

        # Stop carousel if active and stop carousel idle timer
        if self.carousel_active:
            self._stop_carousel()
        self._reset_idle_timer()  # This cancels carousel timer since home_active is now False
        
        # Refresh paper counts while on wifi view
        self._start_paper_refresh()
        
        # Set flag to indicate we're on QR code view
        self.controller._on_qr_code_view = True
        print("[HomeScreen] Switched to QR code view - enabling global idle timer")
        
        # IMPORTANT: Start global 5-minute idle timer for QR code view
        # The QR code/WiFi view should trigger idle confirmation modal after 5 minutes
        self.controller._reset_global_idle_timer()

    def show_main_view(self):
        self.home_active = True
        self._bind_main_view_events()  # Rebind carousel timer events
        self._stop_paper_refresh()
        self.wifi_view.pack_forget()
        self.main_view.pack(expand=True, fill="both")
        
        # Reset carousel idle timer now that we're back on home screen
        self._reset_idle_timer()
        
        # Clear flag and cancel global idle timer when returning to main view
        self.controller._on_qr_code_view = False
        print("[HomeScreen] Returned to main view - disabling global idle timer")
        self.controller._cancel_global_idle_timer()

    def show_usb_drive_screen(self):
        """Navigate to the USB drive file transfer screen."""
        self.home_active = False
        self._unbind_main_view_events()
        self.main_view.pack_forget()
        
        # Stop carousel if active
        if self.carousel_active:
            self._stop_carousel()
        self._reset_idle_timer()
        
        # Navigate to USB drive screen
        self.controller.show_frame("USBDriveScreen")
        
        # Set flag and start idle timer for USB screen
        self.controller._on_qr_code_view = True
        self.controller._reset_global_idle_timer()

    def set_status(self, message):
        if hasattr(self, 'status_label'):
            self.status_label.config(text=message)
    
    def _start_paper_refresh(self, interval_ms=5000):
        """Start periodic refresh of paper counts while on the WiFi/QR view."""
        self._stop_paper_refresh()
        def _tick():
            try:
                self.fetch_paper_counts()
            except Exception:
                pass
            finally:
                # Continue refreshing only if WiFi view is active and visible
                if not self.home_active and self.wifi_view.winfo_ismapped():
                    self._paper_refresh_timer = self.after(interval_ms, _tick)
                else:
                    self._paper_refresh_timer = None
        # Kick off immediately
        self._paper_refresh_timer = self.after(0, _tick)

    def _stop_paper_refresh(self):
        """Stop the periodic paper count refresh if running."""
        if getattr(self, "_paper_refresh_timer", None):
            try:
                self.after_cancel(self._paper_refresh_timer)
            except Exception:
                pass
            self._paper_refresh_timer = None

    def update_paper_count(self, short_count, a4_count):
        """Update the remaining paper count display."""
        if hasattr(self, 'short_paper_label'):
            self.short_paper_label.config(text=f"Letter: {short_count} sheets")
        if hasattr(self, 'a4_paper_label'):
            self.a4_paper_label.config(text=f"A4: {a4_count} sheets")
        # Keep internal numeric state for checks
        try:
            self._letter_count = int(short_count)
        except Exception:
            self._letter_count = 100
        try:
            self._a4_count = int(a4_count)
        except Exception:
            self._a4_count = 100

    def show_low_paper_modal(self, letter_count, a4_count):
        """Display a modal dialog styled like the cancel modal to warn about low paper."""
        # Create white overlay that covers the HomeScreen
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Scale based on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        # Modal size and rounded box (increased for more room)
        modal_width = int(1050 * scale)
        # modal height: increase to ensure the warning sign can be drawn fully without clipping
        modal_height = int(750 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Draw rounded rectangle modal box: first draw filled background,
        # then draw an inset outline to avoid clipping of the stroke.
        self._draw_round_rect(canvas, 0, 0, modal_width, modal_height,
                     radius, fill="white", outline='', width=0)
        # Inset the outline by 1 pixel so the stroke is not clipped at canvas edges
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_width - inset, modal_height - inset,
                     max(0, radius - inset), fill='', outline="#999999", width=2)

        # Main modal container: draw the warning icon directly on the modal canvas
        # and place the content window slightly lower so the icon sits above it.
        modal_container = tk.Frame(canvas, bg="white")

        # Icon parameters: make the sign noticeably larger to match larger modal
        icon_size = int(110 * scale)
        tri_color = "#ffc107"
        mark_color = "#000"
        # Exclamation mark thickness and dot size — scale with icon
        mark_w = max(3, int(icon_size * 0.11))
        dot_s = max(3, int(icon_size * 0.10))

        # Compute triangle half-size and center so it fills more area but stays inside the rounded box
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_width // 2
        # Ensure the triangle top is a safe distance below the rounded corner
        top_margin = max(12, int(10 * scale))
        icon_cy = int(radius + top_margin + half)

        # Position the content window directly below the triangle (anchor at top)
        # This avoids centering the content vertically (which created large bottom whitespace)
        content_y = icon_cy + int(half) + int(8 * scale)
        canvas.create_window(modal_width // 2, content_y, window=modal_container, anchor='n')

        # Triangle points centered at (icon_cx, icon_cy)
         # Make the yellow triangle larger relative to the icon and reduce inset
        inset = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset,
             icon_cx - half + inset, icon_cy + half - inset,
             icon_cx + half - inset, icon_cy + half - inset]
        poly_id = canvas.create_polygon(pts, fill=tri_color, outline=tri_color)

        # Draw the exclamation '!' as centered text at the triangle's bounding-box center
        try:
            excl_font_size = max(10, int(icon_size * 0.55))
            excl_font = ("Arial", excl_font_size, "bold")
        except Exception:
            excl_font = ("Arial", int(icon_size * 0.55), "bold")

        # Compute the triangle centroid (average of vertices) for accurate visual centering
        try:
            x1, y1 = pts[0], pts[1]
            x2, y2 = pts[2], pts[3]
            x3, y3 = pts[4], pts[5]
            poly_cx = int((x1 + x2 + x3) / 3.0)
            poly_cy = int((y1 + y2 + y3) / 3.0)
        except Exception:
            poly_cx = icon_cx
            poly_cy = icon_cy
        # Place the '!' at the triangle centroid; nudge it upward slightly for optical centering
        text_nudge = int(icon_size * 0.08)
        text_id = canvas.create_text(poly_cx, poly_cy - text_nudge, text='!', font=excl_font, fill=mark_color, anchor='center')

        # Raise icon parts above the content window to ensure visibility
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        # Content
        # Reduce content padding to tighten vertical spacing inside modal
        padding = int(16 * scale)
        content = tk.Frame(modal_container, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)

        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        # Add a bit of top spacing so the warning icon isn't too close to the title
        tk.Label(content, text="Low Paper Notice", font=title_font, bg="white", fg="#333").pack(pady=(int(18 * scale), int(8 * scale)))

        # Build message
        parts = []
        try:
            if isinstance(letter_count, (int, float)) and int(letter_count) <= 30:
                parts.append(f"Letter: {int(letter_count)}")
        except Exception:
            pass    
        try:
            if isinstance(a4_count, (int, float)) and int(a4_count) <= 30:
                parts.append(f"A4: {int(a4_count)}")
        except Exception:
            pass

        # Centered subtitle (larger)
        subtitle_font = ("Arial", max(18, int(20 * scale)), "bold")
        tk.Label(content, text="The following paper types are low:", font=subtitle_font, bg="white", fg="#666", justify="center").pack(pady=(0, int(10 * scale)))

        # Show Letter and A4 counts — render labels black and numeric values brand red (bigger)
        counts_font = ("Arial", max(22, int(26 * scale)), "bold")
        counts_frame = tk.Frame(content, bg="white")
        counts_frame.pack(pady=(0, int(12 * scale)))

        # Build structured items so we can color only the numbers
        count_items = []
        try:
            if isinstance(letter_count, (int, float)) and int(letter_count) <= 30:
                count_items.append(("Letter", int(letter_count)))
        except Exception:
            pass
        try:
            if isinstance(a4_count, (int, float)) and int(a4_count) <= 30:
                count_items.append(("A4", int(a4_count)))
        except Exception:
            pass

        if count_items:
            for i, (name, val) in enumerate(count_items):
                if i > 0:
                    sep = tk.Label(counts_frame, text=" | ", font=counts_font, bg="white", fg="#666")
                    sep.pack(side="left")

                tk.Label(counts_frame, text=f"{name}: ", font=counts_font, bg="white", fg="#000000").pack(side="left")
                tk.Label(counts_frame, text=str(val), font=counts_font, bg="white", fg="#b42e41").pack(side="left")
                # Suffix ' sheets' in black to match no-paper modal
                tk.Label(counts_frame, text=" sheets", font=counts_font, bg="white", fg="#000000").pack(side="left")
        else:
            tk.Label(counts_frame, text="Unknown", font=counts_font, bg="white", fg="#666").pack()

        # Prominent WARNING title (even larger for emphasis)
        info_title = "WARNING"
        info_title_font = ("Arial", max(22, int(25 * scale)), "bold")
        tk.Label(content, text=info_title, font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(int(12 * scale), int(10 * scale)))

        # Instruction sentences split into two rows for better readability
        info_sentence_1 = (
            "Remaining paper is low. If one paper type is empty, you may still be able to print using the other size."
        )
        info_sentence_2 = (
            "Please check which paper type is available, confirm your document's page size, and the number of copies before printing."
        )
        info_font = ("Arial", max(15, int(20 * scale)), "bold")
        tk.Label(content, text=info_sentence_1, font=info_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(8 * scale), int(6 * scale)))
        tk.Label(content, text=info_sentence_2, font=info_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(0, int(14 * scale)))

        # Buttons frame (add top padding so buttons have breathing room)
        buttons_frame = tk.Frame(content, bg="white")
        buttons_frame.pack(pady=(int(10 * scale), 0))

        button_font = ("Arial", max(16, int(20 * scale)), "bold")
        button_padx = int(40 * scale)
        button_pady = int(14 * scale)

        ok_button = tk.Button(
            buttons_frame,
            text="OK",
            font=button_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.close_low_paper_modal(modal_overlay)
        )
        ok_button.pack(side="left", padx=int(10 * scale))

        # Store reference so it can be closed later
        self._low_paper_modal = modal_overlay

    def close_low_paper_modal(self, modal_overlay):
        if modal_overlay and modal_overlay.winfo_exists():
            modal_overlay.destroy()
        if hasattr(self, '_low_paper_modal'):
            delattr(self, '_low_paper_modal')

    def show_no_paper_modal(self, letter_count, a4_count):
        """Display a small modal that indicates there is no remaining paper.
        The 'I Confirm' button closes the modal and returns to the main view.
        """
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        modal_w = int(1050 * scale)
        modal_h = int(750 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_w, height=modal_h,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Background + inset outline
        self._draw_round_rect(canvas, 0, 0, modal_w, modal_h, radius, fill="white", outline='')
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_w - inset, modal_h - inset,
                     max(0, radius - inset), fill='', outline="#999999", width=2)

        container = tk.Frame(canvas, bg="white", padx=int(16 * scale), pady=int(12 * scale))

        # Draw the warning sign (triangle + exclamation) above the modal content to match low-paper modal
        tri_color = "#ffc107"
        mark_color = "#000"
        icon_size = int(110 * scale)
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_w // 2
        top_margin = max(12, int(10 * scale))
        icon_cy = int(radius + top_margin + half)

        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri,
               icon_cx - half + inset_tri, icon_cy + half - inset_tri,
               icon_cx + half - inset_tri, icon_cy + half - inset_tri]
        poly_id = canvas.create_polygon(pts, fill=tri_color, outline=tri_color)

        try:
            excl_font_size = max(12, int(icon_size * 0.60))
            excl_font = ("Arial", excl_font_size, "bold")
        except Exception:
            excl_font = ("Arial", int(icon_size * 0.60), "bold")

        try:
            x1, y1 = pts[0], pts[1]
            x2, y2 = pts[2], pts[3]
            x3, y3 = pts[4], pts[5]
            poly_cx = int((x1 + x2 + x3) / 3.0)
            poly_cy = int((y1 + y2 + y3) / 3.0)
        except Exception:
            poly_cx = icon_cx
            poly_cy = icon_cy

        text_nudge = int(icon_size * 0.08)
        text_id = canvas.create_text(poly_cx, poly_cy - text_nudge, text='!', font=excl_font, fill=mark_color, anchor='center')

        # Place the content window directly below the triangle
        content_y = icon_cy + int(half) + int(8 * scale)
        canvas.create_window(modal_w // 2, content_y, window=container, anchor='n')

        # Ensure icon is above the content
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        title_font = ("Bebas Neue", max(28, int(32 * scale)), "bold")
        tk.Label(container, text="No Remaining Paper", font=title_font, bg="white", fg="#333").pack(pady=(0, int(10 * scale)))

        # Match low-paper modal: show a centered WARNING row and instruction sentence (larger)
        info_title = "WARNING"
        info_title_font = ("Arial", max(20, int(24 * scale)), "bold")
        tk.Label(container, text=info_title, font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(int(8 * scale), int(6 * scale)))

           # Instruction sentences for no-paper modal (split into two rows)
        no_paper_sentence_1 = "Both Letter and A4 paper are currently empty."
    
        # Use prominent fonts for the no-paper instructions
        no_paper_info_font = ("Arial", max(18, int(22 * scale)), "bold")
        tk.Label(container, text=no_paper_sentence_1, font=no_paper_info_font, bg="white", fg="#333", justify="center", wraplength=modal_w - int(32 * scale)).pack(pady=(int(8 * scale), int(6 * scale)))

        # Prominent alert line (uppercase, bold, noticeable color, larger)
        alert_line = "THE PRINTING IS NOT AVAILABLE RIGHT NOW. PLEASE CONTACT US!"
        alert_font = ("Arial", max(20, int(24 * scale)), "bold")
        tk.Label(container, text=alert_line, font=alert_font, bg="white", fg="#b42e41", justify="center", wraplength=modal_w - int(32 * scale)).pack(pady=(int(10 * scale), int(12 * scale)))

        # Contact lines (two rows, slightly larger)
        contact_font = ("Arial", max(18, int(20 * scale)), "bold")
        tk.Label(container, text="For Assistance", font=contact_font, bg="white", fg="#333", justify="center").pack(pady=(0, int(4 * scale)))
        tk.Label(container, text="Contact Us: printqueuesk@gmail.com", font=contact_font, bg="white", fg="#333", justify="center", wraplength=modal_w - int(32 * scale)).pack(pady=(0, int(10 * scale)))

        parts = []
        try:
            if isinstance(letter_count, (int, float)) and int(letter_count) == 0:
                parts.append("Letter: 0 sheets")
        except Exception:
            pass
        try:
            if isinstance(a4_count, (int, float)) and int(a4_count) == 0:
                parts.append("A4: 0 sheets")
        except Exception:
            pass

        # Make the zero-count lines larger; show labels in black and numeric values in brand red
        info_font2 = ("Arial", max(20, int(26 * scale)), "bold")
        info_frame = tk.Frame(container, bg="white")
        info_frame.pack(pady=(int(6 * scale), int(8 * scale)))

        # Build structured items using the numeric inputs so we can color only the values
        items = []
        try:
            if isinstance(letter_count, (int, float)) and int(letter_count) == 0:
                items.append(("Letter", int(letter_count)))
        except Exception:
            pass
        try:
            if isinstance(a4_count, (int, float)) and int(a4_count) == 0:
                items.append(("A4", int(a4_count)))
        except Exception:
            pass

        if items:
            for idx, (name, val) in enumerate(items):
                if idx > 0:
                    # Small separator between items
                    sep = tk.Label(info_frame, text=" and ", font=info_font2, bg="white", fg="#333")
                    sep.pack(side="left")

                # Label (black)
                tk.Label(info_frame, text=f"{name}: ", font=info_font2, bg="white", fg="#000000").pack(side="left")
                # Numeric value (brand red)
                tk.Label(info_frame, text=str(val), font=info_font2, bg="white", fg="#b42e41").pack(side="left")
                # Suffix (black)
                tk.Label(info_frame, text=" sheets", font=info_font2, bg="white", fg="#000000").pack(side="left")
        else:
            tk.Label(info_frame, text="Paper unavailable", font=info_font2, bg="white", fg="#333").pack()

        # Confirm button
        buttons = tk.Frame(container, bg="white")
        buttons.pack(pady=(int(20 * scale), 0))

        btn_font = ("Arial", max(16, int(20 * scale)), "bold")
        confirm_btn = tk.Button(
            buttons,
            text="Confirm",
            font=btn_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=int(28 * scale),
            pady=int(12 * scale),
            command=lambda: (modal_overlay.destroy(), self.show_main_view())
        )
        confirm_btn.pack()

        # Keep a reference in case other code needs to close it
        self._no_paper_modal = modal_overlay
    
    def show_low_ink_modal(self, black_ink_level, color_ink_level):
        """Display a modal dialog styled like the paper modal to warn about low ink levels.
        The wording is business-friendly and provides clear next steps for staff assistance.
        """
        # Create white overlay that covers the HomeScreen
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Scale based on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        # Modal size and rounded box (match paper modal)
        modal_width = int(1050 * scale)
        modal_height = int(750 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Draw rounded rectangle modal box
        self._draw_round_rect(canvas, 0, 0, modal_width, modal_height,
                     radius, fill="white", outline='', width=0)
        # Inset outline
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_width - inset, modal_height - inset,
                     max(0, radius - inset), fill='', outline="#999999", width=2)

        # Main modal container
        modal_container = tk.Frame(canvas, bg="white")

        # Icon parameters (match paper modal)
        icon_size = int(110 * scale)
        tri_color = "#ffc107"
        mark_color = "#000"

        # Compute triangle half-size and center
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_width // 2
        top_margin = max(12, int(10 * scale))
        icon_cy = int(radius + top_margin + half)

        # Position the content window below the triangle
        content_y = icon_cy + int(half) + int(8 * scale)
        canvas.create_window(modal_width // 2, content_y, window=modal_container, anchor='n')

        # Triangle points centered at (icon_cx, icon_cy)
        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri,
             icon_cx - half + inset_tri, icon_cy + half - inset_tri,
             icon_cx + half - inset_tri, icon_cy + half - inset_tri]
        poly_id = canvas.create_polygon(pts, fill=tri_color, outline=tri_color)

        # Draw exclamation mark
        try:
            excl_font_size = max(10, int(icon_size * 0.55))
            excl_font = ("Arial", excl_font_size, "bold")
        except Exception:
            excl_font = ("Arial", int(icon_size * 0.55), "bold")

        try:
            x1, y1 = pts[0], pts[1]
            x2, y2 = pts[2], pts[3]
            x3, y3 = pts[4], pts[5]
            poly_cx = int((x1 + x2 + x3) / 3.0)
            poly_cy = int((y1 + y2 + y3) / 3.0)
        except Exception:
            poly_cx = icon_cx
            poly_cy = icon_cy

        text_nudge = int(icon_size * 0.08)
        text_id = canvas.create_text(poly_cx, poly_cy - text_nudge, text='!', font=excl_font, fill=mark_color, anchor='center')

        # Raise icon parts above content
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        # Content
        padding = int(16 * scale)
        content = tk.Frame(modal_container, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)

        # Title
        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        tk.Label(content, text="Ink Supply Notice", font=title_font, bg="white", fg="#333").pack(pady=(int(18 * scale), int(8 * scale)))

        # Subtitle
        subtitle_font = ("Arial", max(18, int(20 * scale)), "bold")
        tk.Label(content, text="The following ink levels are currently low based on the printed papers:", font=subtitle_font, bg="white", fg="#666", justify="center").pack(pady=(0, int(10 * scale)))

        # Show ink levels
        counts_font = ("Arial", max(22, int(26 * scale)), "bold")
        counts_frame = tk.Frame(content, bg="white")
        counts_frame.pack(pady=(int(10 * scale), int(8 * scale)))

        # Determine display colors
        LOW_COLOR = "#b42e41"  # brand warning color for low
        OK_COLOR = "#b42e41"   # brand normal color for okay
        try:
            b_val = int(black_ink_level)
        except Exception:
            b_val = 100
        try:
            c_val = int(color_ink_level)
        except Exception:
            c_val = 100

        # Inline printer ink row — show Letter and A4 on a single row
        row_font = ("Arial", max(18, int(20 * scale)), "bold")
        # A4 printer
        tk.Label(counts_frame, text="A4 Printer Available:", font=row_font, bg="white", fg="#222").grid(row=0, column=3, sticky="e")
        tk.Label(counts_frame, text=f"{c_val}", font=row_font, bg="white", fg=(LOW_COLOR if c_val <= 30 else OK_COLOR)).grid(row=0, column=4, sticky="w", padx=(0, int(6 * scale)))
        # Separator
        tk.Label(counts_frame, text="|", font=row_font, bg="white", fg="#666").grid(row=0, column=2, padx=(int(8 * scale), int(8 * scale)))
        # Letter printer
        tk.Label(counts_frame, text="Letter Printer Available:", font=row_font, bg="white", fg="#222").grid(row=0, column=0, sticky="e", padx=(0, int(8 * scale)))
        tk.Label(counts_frame, text=f"{b_val}", font=row_font, bg="white", fg=(LOW_COLOR if b_val <= 30 else OK_COLOR)).grid(row=0, column=1, sticky="w", padx=(0, int(14 * scale)))
    
        # Guidance header
        guidance_font = ("Arial", max(20, int(22 * scale)), "bold")
        tk.Label(content, text="Recommended Action", font=guidance_font, bg="white", fg="#b42e41", justify="center").pack(pady=(int(12 * scale), int(8 * scale)))

        # Instruction text (professional tone, bigger and simpler)
        instruction_font = ("Arial", max(18, int(22 * scale)), "bold")
        instruction_line1 = (
            "Remaining ink is low. If one printer's ink is empty, you may still be able to print using the other printer."
        )
        instruction_line2 = (
            "Please check which printer is available, confirm your document's page size, and the number of copies before printing."
        )
        tk.Label(content, text=instruction_line1, font=instruction_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(8 * scale), int(6 * scale)))
        tk.Label(content, text=instruction_line2, font=instruction_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(0, int(14 * scale)))

        # Okay button: close modal and ensure QR view is visible
        buttons = tk.Frame(content, bg="white")
        buttons.pack(pady=(int(12 * scale), 0))

        btn_font = ("Arial", max(16, int(20 * scale)), "bold")
        okay_btn = tk.Button(
            buttons,
            text="Noted",
            font=btn_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=int(28 * scale),
            pady=int(12 * scale),
            command=lambda: modal_overlay.destroy()
        )
        okay_btn.pack()

        # Keep reference
        self._low_ink_modal = modal_overlay

    def show_no_ink_modal(self, black_ink_level, color_ink_level):
        """Display a blocking modal when both ink cartridges are empty.
        This mirrors the `show_no_paper_modal` style and prevents printing.
        """
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        modal_w = int(1050 * scale)
        modal_h = int(750 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_w, height=modal_h, bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Background + inset outline
        self._draw_round_rect(canvas, 0, 0, modal_w, modal_h, radius, fill="white", outline='')
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_w - inset, modal_h - inset,
                     max(0, radius - inset), fill='', outline="#999999", width=2)

        container = tk.Frame(canvas, bg="white", padx=int(16 * scale), pady=int(12 * scale))

        # Draw warning sign above content
        tri_color = "#ffc107"
        mark_color = "#000"
        icon_size = int(110 * scale)
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_w // 2
        top_margin = max(12, int(10 * scale))
        icon_cy = int(radius + top_margin + half)

        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri,
               icon_cx - half + inset_tri, icon_cy + half - inset_tri,
               icon_cx + half - inset_tri, icon_cy + half - inset_tri]
        poly_id = canvas.create_polygon(pts, fill=tri_color, outline=tri_color)

        try:
            excl_font_size = max(12, int(icon_size * 0.60))
            excl_font = ("Arial", excl_font_size, "bold")
        except Exception:
            excl_font = ("Arial", int(icon_size * 0.60), "bold")

        try:
            x1, y1 = pts[0], pts[1]
            x2, y2 = pts[2], pts[3]
            x3, y3 = pts[4], pts[5]
            poly_cx = int((x1 + x2 + x3) / 3.0)
            poly_cy = int((y1 + y2 + y3) / 3.0)
        except Exception:
            poly_cx = icon_cx
            poly_cy = icon_cy

        text_nudge = int(icon_size * 0.08)
        text_id = canvas.create_text(poly_cx, poly_cy - text_nudge, text='!', font=excl_font, fill=mark_color, anchor='center')

        # Place the content window directly below the triangle
        content_y = icon_cy + int(half) + int(8 * scale)
        canvas.create_window(modal_w // 2, content_y, window=container, anchor='n')

        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        # Content
        title_font = ("Bebas Neue", max(28, int(32 * scale)), "bold")
        tk.Label(container, text="No Remaining Ink", font=title_font, bg="white", fg="#333").pack(pady=(0, int(10 * scale)))

        # Details (2 rows)
        info_font2 = ("Arial", max(20, int(26 * scale)), "bold")
        info_frame = tk.Frame(container, bg="white")
        info_frame.pack(pady=(int(6 * scale), int(8 * scale)))
        
        # Row 1: Letter Printer
        row1 = tk.Frame(info_frame, bg="white")
        row1.pack(pady=(0, int(8 * scale)))
        tk.Label(row1, text="Letter Printer:", font=info_font2, bg="white", fg="#000").pack(side="left")
        tk.Label(row1, text=f"{int(black_ink_level)}%", font=info_font2, bg="white", fg="#b42e41").pack(side="left", padx=(int(8 * scale), 0))
        
        # Row 2: A4 Printer
        row2 = tk.Frame(info_frame, bg="white")
        row2.pack()
        tk.Label(row2, text="A4 Printer:", font=info_font2, bg="white", fg="#000").pack(side="left")
        tk.Label(row2, text=f"{int(color_ink_level)}%", font=info_font2, bg="white", fg="#b42e41").pack(side="left", padx=(int(8 * scale), 0))

        info_title_font = ("Arial", max(24, int(28 * scale)), "bold")
        tk.Label(container, text="WARNING", font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(int(8 * scale), int(6 * scale)))

        # Message
        msg_font = ("Arial", max(20, int(24 * scale)), "bold")
        tk.Label(container, text="Both A4 Printer and Letter Printer ink tank are empty.", font=msg_font, bg="white", fg="#333", justify="center", wraplength=modal_w - int(32 * scale)).pack(pady=(int(8 * scale), int(25 * scale)))
        tk.Label(container, text="Printing is not available at right now. Please contact us printqueuesk@gmail.com for assistance.", font=msg_font, bg="white", fg="#333", justify="center", wraplength=modal_w - int(32 * scale)).pack(pady=(0, int(12 * scale)))

        # Confirm button
        buttons = tk.Frame(container, bg="white")
        buttons.pack(pady=(int(20 * scale), 0))

        btn_font = ("Arial", max(16, int(20 * scale)), "bold")
        confirm_btn = tk.Button(
            buttons,
            text="Confirm",
            font=btn_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=int(28 * scale),
            pady=int(12 * scale),
            command=lambda: (modal_overlay.destroy(), self.show_main_view())
        )
        confirm_btn.pack()

        # Keep reference
        self._no_ink_modal = modal_overlay

    def close_no_ink_modal(self, modal_overlay):
        if modal_overlay and modal_overlay.winfo_exists():
            modal_overlay.destroy()
        if hasattr(self, '_no_ink_modal'):
            delattr(self, '_no_ink_modal')

    def fetch_ink_levels(self):
        """Fetch ink levels from Firebase and check if below threshold."""
        try:
            ink_ref = db.reference('resources/ink/printer_ink')
            ink_data = ink_ref.get()
            
            if not ink_data:
                # Initialize if not exists
                ink_data = {
                    'black_ink_level': 100,
                    'color_ink_level': 100,
                    'last_updated': None
                }
                ink_ref.set(ink_data)
            
            # Get ink levels
            black_ink_level = int(ink_data.get('black_ink_level', 100))
            color_ink_level = int(ink_data.get('color_ink_level', 100))
            
            # Store for later use
            self._black_ink_level = black_ink_level
            self._color_ink_level = color_ink_level
            
            # Check for no ink (both cartridges empty)
            if black_ink_level == 0 and color_ink_level == 0:
                self.show_no_ink_modal(black_ink_level, color_ink_level)
                return black_ink_level, color_ink_level

            # Check if low (threshold: 30%)
            LOW_INK_THRESHOLD = 30
            if black_ink_level <= LOW_INK_THRESHOLD or color_ink_level <= LOW_INK_THRESHOLD:
                self.show_low_ink_modal(black_ink_level, color_ink_level)

            return black_ink_level, color_ink_level
            
        except Exception as e:
            print(f"[HomeScreen] Error fetching ink levels: {e}")
            return 100, 100

    def fetch_paper_counts(self):
        """Fetch paper inventory counts from Firebase and update display."""
        try:
            # Fetch from printer_status (same path as dashboard)
            printer_status_ref = db.reference('resources/paper/printer_status')
            statuses = printer_status_ref.order_by_child('updated_at').limit_to_last(1).get()
            
            print(f"[HomeScreen] Printer status data: {statuses}")
            
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
                
                print(f"[HomeScreen] Letter: {letter_count}, A4: {a4_count}")
                # Store counts and update labels
                self._letter_count = letter_count
                self._a4_count = a4_count
                self.update_paper_count(letter_count, a4_count)
            else:
                print("[HomeScreen] No printer_status data found, using defaults")
                self.update_paper_count(100, 100)
            
        except Exception as e:
            print(f"[HomeScreen] Error fetching paper counts: {e}")
            import traceback
            traceback.print_exc()
            self.update_paper_count(100, 100)

    def show_remaining_paper_modal(self, letter_count, a4_count):
        """Display a modal that shows the remaining paper counts.
        This modal appears when the start button is clicked, regardless of paper levels.
        """
        # Create white overlay that covers the HomeScreen
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Scale based on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        # Modal size and rounded box
        modal_width = int(1050 * scale)
        modal_height = int(750 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Draw rounded rectangle modal box
        self._draw_round_rect(canvas, 0, 0, modal_width, modal_height,
                     radius, fill="white", outline='', width=0)
        # Inset outline
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_width - inset, modal_height - inset,
                     max(0, radius - inset), fill='', outline="#999999", width=2)

        # Main modal container
        modal_container = tk.Frame(canvas, bg="white")

        # Icon parameters (use information icon design - blue circle with 'i')
        icon_size = int(110 * scale)
        circle_color = "#2196F3"  # Blue color for information
        info_color = "#FFF"  # White for the 'i'

        # Compute circle center
        icon_cx = modal_width // 2
        top_margin = max(12, int(10 * scale))
        icon_cy = int(radius + top_margin + icon_size / 2)

        # Position the content window below the circle
        content_y = icon_cy + int(icon_size / 2) + int(2 * scale)
        canvas.create_window(modal_width // 2, content_y, window=modal_container, anchor='n')

        # Draw blue circle
        circle_id = canvas.create_oval(
            icon_cx - icon_size // 2,
            icon_cy - icon_size // 2,
            icon_cx + icon_size // 2,
            icon_cy + icon_size // 2,
            fill=circle_color,
            outline=circle_color,
            width=0
        )

        # Draw white 'i' character in the circle
        try:
            info_font_size = max(12, int(icon_size * 0.65))
            info_font = ("Arial", info_font_size, "bold")
        except Exception:
            info_font = ("Arial", int(icon_size * 0.65), "bold")

        info_id = canvas.create_text(icon_cx, icon_cy, text='i', font=info_font, fill=info_color, anchor='center')

        # Raise icon parts above the content window
        try:
            canvas.tag_raise(circle_id)
            canvas.tag_raise(info_id)
        except Exception:
            pass

        # Content
        padding = int(16 * scale)
        content = tk.Frame(modal_container, bg="white", padx=padding, pady=0)
        content.pack()

        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        tk.Label(content, text="Remaining Paper", font=title_font, bg="white", fg="#333").pack(pady=(int(18 * scale), int(8 * scale)))

        # Subtitle
        subtitle_font = ("Arial", max(18, int(20 * scale)), "bold")
        tk.Label(content, text="Current paper stock levels:", font=subtitle_font, bg="white", fg="#666", justify="center").pack(pady=(0, int(14 * scale)))

        # Show Letter and A4 counts — render labels black and numeric values in blue (information color)
        counts_font = ("Arial", max(22, int(26 * scale)), "bold")
        counts_frame = tk.Frame(content, bg="white")
        counts_frame.pack(pady=(0, int(16 * scale)))

        # Build structured items so we can color only the numbers
        count_items = []
        try:
            if isinstance(letter_count, (int, float)):
                count_items.append(("Letter", int(letter_count)))
            else:
                count_items.append(("Letter", 100))
        except Exception:
            count_items.append(("Letter", 100))
        
        try:
            if isinstance(a4_count, (int, float)):
                count_items.append(("A4", int(a4_count)))
            else:
                count_items.append(("A4", 100))
        except Exception:
            count_items.append(("A4", 100))

        if count_items:
            for i, (name, val) in enumerate(count_items):
                if i > 0:
                    sep = tk.Label(counts_frame, text=" | ", font=counts_font, bg="white", fg="#666")
                    sep.pack(side="left")

                tk.Label(counts_frame, text=f"{name}: ", font=counts_font, bg="white", fg="#000000").pack(side="left")
                tk.Label(counts_frame, text=str(val), font=counts_font, bg="white", fg="#b42e41").pack(side="left")
                # Suffix ' sheets' in black
                tk.Label(counts_frame, text=" sheets", font=counts_font, bg="white", fg="#000000").pack(side="left")
        else:
            tk.Label(counts_frame, text="Unknown", font=counts_font, bg="white", fg="#666").pack()

        # Informational message
        info_title = "INFORMATION"
        info_title_font = ("Arial", max(20, int(24 * scale)), "bold")
        tk.Label(content, text=info_title, font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(int(3 * scale), int(3 * scale)))

        # Instruction text - split into multiple rows
        info_sentence_1 = (
            "Please check the documents you need to print and verify the exact number of pages. "
            "Check the remaining paper available."
        )
        info_sentence_2 = (
            "If the document pages exceed the remaining paper stock:"
        )
        info_sentence_3 = (
            "⚠️ WARNING: Insufficient paper available."
        )
        info_sentence_4 = (
            "This is a self-service kiosk machine. Please contact our staff for paper replenishment before proceeding with your print job."
        )
        info_font = ("Arial", max(15, int(20 * scale)), "bold")
        tk.Label(content, text=info_sentence_1, font=info_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(4 * scale), int(4 * scale)))
        tk.Label(content, text=info_sentence_2, font=info_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(4 * scale), int(2 * scale)))
        tk.Label(content, text=info_sentence_3, font=info_font, bg="white", fg="#b42e41", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(6 * scale), int(4 * scale)))
        tk.Label(content, text=info_sentence_4, font=info_font, bg="white", fg="#333", justify="center", wraplength=modal_width - int(120 * scale)).pack(pady=(int(4 * scale), int(2 * scale)))

        # Button frame
        buttons_frame = tk.Frame(content, bg="white")
        buttons_frame.pack(pady=(int(15 * scale), 0))

        button_font = ("Arial", max(16, int(20 * scale)), "bold")
        button_padx = int(35 * scale)
        button_pady = int(14 * scale)

        # Understood button
        understood_button = tk.Button(
            buttons_frame,
            text="Got It",
            font=button_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=button_padx,
            pady=button_pady,
            command=lambda: self.close_remaining_paper_modal(modal_overlay)
        )
        understood_button.pack(side="left", padx=int(10 * scale))

        # Store reference so it can be closed later
        self._remaining_paper_modal = modal_overlay

    def close_remaining_paper_modal(self, modal_overlay):
        """Close the remaining paper modal."""
        if modal_overlay and modal_overlay.winfo_exists():
            modal_overlay.destroy()
        if hasattr(self, '_remaining_paper_modal'):
            delattr(self, '_remaining_paper_modal')

    def _show_low_paper_notice(self, letter_count, a4_count):
        """Display the low-paper notice frame with the accurate counts."""
        msgs = []
        try:
            if isinstance(letter_count, (int, float)) and int(letter_count) <= 30:
                msgs.append(f"Letter: {int(letter_count)} sheets")
        except Exception:
            pass
        try:
            if isinstance(a4_count, (int, float)) and int(a4_count) <= 30:
                msgs.append(f"A4: {int(a4_count)} sheets")
        except Exception:
            pass

        if not msgs:
            self._hide_notice()
            return

        text = "Low Paper Warning: " + ", ".join(msgs)
        try:
            self.notice_label.config(text=text)
            # Align with main content padding used elsewhere
            self.notice_frame.pack(fill="x", padx=89, pady=(8, 0))
        except Exception:
            pass

    def _hide_notice(self):
        try:
            if hasattr(self, 'notice_frame') and self.notice_frame.winfo_exists():
                self.notice_frame.pack_forget()
        except Exception:
            pass

    def update_status(self, data):
        # This can be expanded if you need to show a list of jobs
        document_name = data.get('document_name')
        status = data.get('status')
        print(f"Received update for {document_name}: {status}")
        self.set_status(f"Status for {document_name}: {status.upper()}")

    def load_data(self, data=None):
        # Only show wifi view if explicitly needed, not on initial load
        # Check if we're coming from another screen (data is provided)
        if data is not None:
            self.show_wifi_view()
        # Otherwise, keep the current view (main_view on initial launch)
        
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
    
    def show_transition_screen(self, message="Preparing your print job"):
        """Show a transition screen with an animated loading message."""
        # Hide any existing transition screen first
        self.hide_transition_screen()
        
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
        
        # Store the canvas and dot objects references
        self._dots_canvas = dots_canvas
        self._dot_objects = dot_objects
        
        # Start the animation and store its ID
        self.animation_id = None
        self._update_dots_animation(dots_canvas, dot_objects, 0)
        
        # Store the transition frame reference
        self._transition_frame = transition_frame
        
        # Do not globally lift the overlay; keep it scoped to HomeScreen to avoid covering other screens
        
        return transition_frame
    
    def show_payment_successful(self):
        """Show Payment Successful message."""
        self.hide_transition_screen()
        
        # Create a new frame for the success screen
        success_frame = tk.Frame(self, bg="white")
        success_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
        
        # Main container
        container = tk.Frame(success_frame, bg="white")
        container.pack(expand=True)
        
        # Success message
        text_label = tk.Label(
            container,
            text="Payment Successful!",
            font=("Bebas Neue", 50),
            bg="white",
            fg="#28a745"  # Green color for success
        )
        text_label.pack()
        
        # Store the frame reference
        self._transition_frame = success_frame
        
        return success_frame
    
    def show_printing_in_process(self):
        """Show Printing In Process message with animation."""
        return self.show_transition_screen("Printing In Process")
    
    def show_print_complete(self):
        """Show Print Complete message."""
        self.hide_transition_screen()
        
        # Create a new frame for the complete screen
        complete_frame = tk.Frame(self, bg="white")
        complete_frame.place(relx=0.5, rely=0.5, anchor='center', relwidth=1, relheight=1)
        
        # Main container
        container = tk.Frame(complete_frame, bg="white")
        container.pack(expand=True)
        
        # Complete message
        text_label = tk.Label(
            container,
            text="Print Complete!",
            font=("Bebas Neue", 50),
            bg="white",
            fg="#28a745"  # Green color for success
        )
        text_label.pack()
        
        # Store the frame reference
        self._transition_frame = complete_frame
        
        # Auto-return to main view after 3 seconds
        self.after(3000, self.return_to_main_view)
        
        return complete_frame
    
    def return_to_main_view(self):
        """Return to the main view after print complete."""
        self.hide_transition_screen()
        self.show_main_view()
        
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
    
    def launch_hotspot_screen(self):
        """Navigate to the hotspot screen within the same window."""
        try:
            # Navigate to the hotspot screen frame
            self.controller.show_frame("HotspotScreen")
            print("Navigated to hotspot screen")
        except Exception as e:
            print(f"Error navigating to hotspot screen: {e}")
            # Optionally show an error message to the user
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to navigate to hotspot screen: {str(e)}")