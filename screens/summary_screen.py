# screens/summary_screen.py

import tkinter as tk
import os
from PIL import Image, ImageTk, ImageChops


class SummaryScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.data = {}
        # Idle timer for auto-return to home
        self._idle_timer = None
        # Bind events to reset global idle timer when user is active
        self.bind_all('<Any-KeyPress>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Any-Button>', lambda e: self.controller._reset_global_idle_timer())
        self.bind_all('<Motion>', lambda e: self.controller._reset_global_idle_timer())
        self._build_ui()

    # ---- Public API ----
    def load_data(self, data):
        self.data = data or {}

        # Unpack with defaults
        file_name = self.data.get("file_name", "")
        total_pages = int(self.data.get("total_pages", 1) or 1)
        pages_range = self.data.get("pages_range", "all")
        color_mode = self.data.get("color_mode", "colored")
        num_copies = int(self.data.get("num_copies", 1) or 1)
        page_size = self.data.get("page_size", "Letter Size")
        total_price = float(self.data.get("total_price", 0) or 0)

        # Pages display: "1 - N" if all
        if isinstance(pages_range, str) and pages_range.lower() == "all":
            pages_display = f"1 - {total_pages}"
        else:
            # normalize formats like "1-5" -> "1 - 5"
            pages_display = pages_range.replace("-", " - ")

        # Update UI labels
        self.lbl_file_name_val.config(text=self._make_breakable_filename(file_name))
        self.lbl_pages_val.config(text=pages_display)
        self.lbl_color_val.config(text=("Colored" if color_mode == "colored" else "Black & White"))
        self.lbl_copies_val.config(text=str(num_copies))
        self.lbl_paper_val.config(text=str(page_size))
        self.lbl_total_value.config(text=self._peso(total_price))

    # ---- Build UI ----
    def _build_ui(self):
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
        label_font = ("Arial", max(16, int(18 * scale)))
        label_bold = ("Arial", max(16, int(18 * scale)), "bold")
        # Slightly larger fonts for the price card
        price_title_font = ("Arial", max(26, int(28 * scale)), "bold")
        price_value_font = ("Arial", max(60, int(66 * scale)), "bold")
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
        tk.Label(header_inner, text="Print Summary", font=title_font, bg="white").pack(side="left", padx=int(16 * scale))

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

        # File Name in brand red
        brand_red = "#b42e41"
        tk.Label(left, text="File Name:", font=label_bold, fg="black", bg="white", anchor="w").pack(anchor="w")
        self.lbl_file_name_val = tk.Label(
            left,
            text="",
            font=label_bold,
            fg=brand_red,
            bg="white",
            anchor="w",
            wraplength=int(max(400, screen_w * 0.35)),
            justify="left",
        )
        self.lbl_file_name_val.pack(anchor="w", fill="x", pady=(0, int(8 * scale)))
        # Dynamically bind wraplength to the left card's width so long names never clip
        self._bind_wrap_to_parent(self.lbl_file_name_val, left, pad=int(8 * scale))

        # Other details
        row_gap = int(6 * scale)
        self._kv(left, "Pages to Print:", "", label_font, row_gap)
        self.lbl_pages_val = self._last_value_label
        self._kv(left, "Color Mode:", "", label_font, row_gap)
        self.lbl_color_val = self._last_value_label
        self._kv(left, "Copies:", "", label_font, row_gap)
        self.lbl_copies_val = self._last_value_label
        self._kv(left, "Paper Size:", "", label_font, row_gap)
        self.lbl_paper_val = self._last_value_label
        # Add a bottom spacer so the last line has proper breathing room
        tk.Frame(left, height=int(30 * scale), bg="white").pack(fill="x")

        # Right Card: Total Price (rounded)
        right_frame, right = self._rounded_container(
            cards, bg="white", radius=15, padding=int(18 * scale), fill_x=True, vcenter=True
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(int(15 * scale), int(15 * scale)))

        # Centered price block container so the title and value are truly centered
        price_box = tk.Frame(right, bg="white")
        price_box.pack(expand=True, fill="both")
        # Use expandable spacers to center vertically
        tk.Frame(price_box, bg="white").pack(side="top", expand=True, fill="y")
        price_content = tk.Frame(price_box, bg="white")
        price_content.pack(side="top")

        title_lbl = tk.Label(
            price_content,
            text="Total Price:",
            font=price_title_font,
            fg="black",
            bg="white",
        )
        title_lbl.pack(anchor="center", pady=(int(4 * scale), 0))

        self.lbl_total_value = tk.Label(
            price_content,
            text=self._peso(0),
            font=price_value_font,
            fg=brand_red,
            bg="white",
        )
        self.lbl_total_value.pack(anchor="center", pady=(int(10 * scale), 0))
        tk.Frame(price_box, bg="white").pack(side="top", expand=True, fill="y")

        # Bottom button inside container
        btn = tk.Button(container, text="Proceed to Payment", font=button_font, bg=brand_red, fg="white", bd=0, relief="flat",
                         padx=int(16 * scale), pady=int(6 * scale), command=self.proceed_to_payment)
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

    # --- Rounded container helpers ---
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

    def _peso(self, amount):
        try:
            return f"₱ {float(amount):.2f}"
        except Exception:
            return "₱ 0.00"

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
            print(f"[SummaryScreen] Logo load failed: {e}")
            import traceback
            traceback.print_exc()
            bg_color = parent.cget("bg") if hasattr(parent, "cget") else "white"
            tk.Label(parent, text="PRINTECH", font=("Arial", max(24, int(48 * scale)), "bold"), bg=bg_color, fg="#000").pack()

    # ---- Navigation ----
    def proceed_to_payment(self):
        # When proceeding to payment, fetch current coin (piso) counts
        # and show a confirmation modal that displays the values.
        job_id = self.data.get('job_id')

        def do_proceed():
            # Update job details in Firebase before proceeding to payment
            if job_id:
                try:
                    detail_ref = None
                    import time
                    from config.firebase_config import db
                    # Use NEW HIERARCHICAL STRUCTURE
                    detail_ref = db.reference(f'jobs/print_jobs/{job_id}/details/0')
                    detail_ref.update({
                        'file_name': self.data.get('file_name'),
                        'total_pages': self.data.get('total_pages'),
                        'num_copies': int(self.data.get('num_copies', 1) or 1),
                        'page_range': self.data.get('pages_range'),
                        'color_mode': self.data.get('color_mode', 'colored'),
                        'total_price': self.data.get('total_price', 0),
                        'page_size': self.data.get('page_size', 'Letter Size'),
                        'scale_mode': self.data.get('scale_mode', 'fit'),
                        'scale_percentage': self.data.get('scale_percentage', 100),
                        'status': 'configuring',
                        'updated_at': time.time()
                    })
                except Exception as e:
                    print(f"[SummaryScreen] Failed to update job details: {e}")
            payload = {
                'total_price': self.data.get('total_price', 0),
                'job_id': self.data.get('job_id'),
                'summary_context': self.data
            }
            self.controller.show_frame("PaymentScreen", data=payload)

        # First, check if there is sufficient paper for the print job
        try:
            from config.firebase_config import db
            printer_status_ref = db.reference('resources/paper/printer_status')
            statuses = printer_status_ref.order_by_child('updated_at').limit_to_last(1).get()
            
            remaining_letter = 100
            remaining_a4 = 100
            
            if statuses:
                latest_status = list(statuses.values())[0]
                remaining_letter = int(latest_status.get('remaining_paper_letter', 100) or 100)
                remaining_a4 = int(latest_status.get('remaining_paper_a4', 100) or 100)
            
            # Determine which paper type is being used and get the remaining count
            page_size = self.data.get('page_size', 'Letter Size')
            remaining_paper = remaining_letter if 'Letter' in page_size else remaining_a4
            
            # Calculate total pages needed (including copies)
            total_pages = int(self.data.get('total_pages', 1) or 1)
            num_copies = int(self.data.get('num_copies', 1) or 1)
            pages_range = self.data.get('pages_range', 'all')
            
            # If page range is specified (not 'all'), calculate pages in range
            if isinstance(pages_range, str) and pages_range.lower() != 'all':
                try:
                    # Parse page range like "1-5" or "1 - 5"
                    range_str = pages_range.replace(' - ', '-').replace(' ', '')
                    if '-' in range_str:
                        parts = range_str.split('-')
                        start_page = int(parts[0])
                        end_page = int(parts[1])
                        pages_in_range = max(0, end_page - start_page + 1)
                        total_pages_needed = pages_in_range * num_copies
                    else:
                        total_pages_needed = total_pages * num_copies
                except Exception:
                    total_pages_needed = total_pages * num_copies
            else:
                total_pages_needed = total_pages * num_copies
            
            print(f"[SummaryScreen] Pages needed: {total_pages_needed}, Remaining paper: {remaining_paper}")
            
            # Check if sufficient paper
            if total_pages_needed > remaining_paper:
                print(f"[SummaryScreen] Insufficient paper: need {total_pages_needed}, have {remaining_paper}")
                self.show_insufficient_paper_modal(
                    pages_needed=total_pages_needed,
                    remaining_paper=remaining_paper,
                    on_cancel=self.go_back_to_start_printing,
                    on_back_to_options=self.go_back_to_options
                )
                return
        except Exception as e:
            print(f"[SummaryScreen] Error checking paper availability: {e}")
            import traceback
            traceback.print_exc()
            # If there's an error checking paper, continue with normal flow

        try:
            from config.firebase_config import db
            coin_ref = db.reference('resources/coins/coin_counts')
            coin_data = coin_ref.get() or {}
            remaining_1peso = int(coin_data.get('1peso', 0) or 0)
            remaining_5peso = int(coin_data.get('5peso', 0) or 0)
        except Exception as e:
            print(f"[SummaryScreen] Failed to fetch coin counts: {e}")
            remaining_1peso = 0
            remaining_5peso = 0

        # If either coin type has reached zero, show a strict 'No Change' modal
        try:
            if (isinstance(remaining_1peso, int) and remaining_1peso == 0) or (
                isinstance(remaining_5peso, int) and remaining_5peso == 0
            ):
                self.show_no_change_modal(remaining_1peso, remaining_5peso, on_confirm=do_proceed)
                return
        except Exception:
            # If an error occurs checking zero, fall through to the warning modal
            pass

        # Show piso modal when coin counts reach the warning threshold.
        # If both counts are above the threshold, proceed immediately.
        try:
            WARNING_THRESHOLD = 100
            should_show = (
                (isinstance(remaining_1peso, int) and remaining_1peso <= WARNING_THRESHOLD) or
                (isinstance(remaining_5peso, int) and remaining_5peso <= WARNING_THRESHOLD)
            )
        except Exception:
            should_show = True

        if should_show:
            self.show_piso_modal(remaining_1peso, remaining_5peso, on_confirm=do_proceed)
        else:
            do_proceed()

    def show_piso_modal(self, one_peso, five_peso, on_confirm=None):
        """Show a modal displaying remaining 1-peso and 5-peso values and a short warning.
        on_confirm (callable) will be executed when the user confirms.
        """
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        modal_w = int(1050 * scale)
        modal_h = int(720 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_w, height=modal_h, bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Background
        self._draw_round_rect(canvas, 0, 0, modal_w, modal_h, radius, fill="white", outline='')
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_w - inset, modal_h - inset, max(0, radius - inset), fill='', outline="#999999", width=2)

        container = tk.Frame(canvas, bg="white", padx=int(16 * scale), pady=int(12 * scale))

        # Warning icon
        tri_color = "#ffc107"
        mark_color = "#000"
        icon_size = int(110 * scale)
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_w // 2
        top_margin = max(8, int(8 * scale))
        icon_cy = int(radius + top_margin + half)

        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri, icon_cx - half + inset_tri, icon_cy + half - inset_tri, icon_cx + half - inset_tri, icon_cy + half - inset_tri]
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

        # Place the content window below the icon and constrain its width so
        # the inner contents are centered and consistently wrapped.
        content_y = icon_cy + int(half) + int(8 * scale)
        content_width = max(300, modal_w - int(160 * scale))
        # Inner wrap margin to leave breathing room inside the container
        inner_wrap_margin = int(24 * scale)
        canvas.create_window(modal_w // 2, content_y, window=container, anchor='n', width=content_width)

        # Ensure icon is above the content
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        tk.Label(container, text="Coin Change Alert", font=title_font, bg="white", fg="#333").pack(pady=(0, int(12 * scale)))

        # Show status of 1-peso and 5-peso coins
        info_font = ("Arial", max(16, int(18 * scale)))
        counts_frame = tk.Frame(container, bg="white")
        counts_frame.pack(pady=(10, 12))

        def _status_text(val):  
            try:
                WARNING_THRESHOLD = 100
                if isinstance(val, int) and val <= WARNING_THRESHOLD:
                    return "LOW"    
                else:
                    return "OK"
            except Exception:
                return "LOW"

        tk.Label(counts_frame, text="1 Peso:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=_status_text(one_peso), font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#b42e41").pack(side="left", padx=(8, 18))
        tk.Label(counts_frame, text="5 Peso:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=_status_text(five_peso), font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#b42e41").pack(side="left", padx=(8, 0))

        # Prominent WARNING title
        info_title = "WARNING"
        info_title_font = ("Arial", max(22, int(26 * scale)), "bold")
        tk.Label(container, text=info_title, font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(12, 8))

        dispenser_line = "The coin change dispenser currently has a low supply of 1-peso and/or 5-peso coins."
        dispenser_font = ("Arial", max(18, int(20 * scale)), "bold")
        tk.Label(container, text=dispenser_line, font=dispenser_font, bg="white", fg="#333", justify="center", wraplength=content_width - inner_wrap_margin).pack(pady=(0, 12))

        warn = (
            "It is recommended to insert the exact amount to ensure your payment completes successfully. "
        )
        tk.Label(container, text=warn, font=("Arial", max(18, int(22 * scale)), "bold"), bg="white", fg="#333", wraplength=content_width - inner_wrap_margin, justify="center").pack(pady=(10, 18))
        tk.Frame(container, height=int(20 * scale), bg="white").pack(fill="x")

        # Buttons
        buttons = tk.Frame(container, bg="white")
        buttons.pack(pady=(int(12 * scale), 0))
        btn_font = ("Arial", max(16, int(20 * scale)), "bold")

        def _confirm():
            try:
                if on_confirm:
                    on_confirm()
            finally:
                try:
                    modal_overlay.destroy()
                except Exception:
                    pass

        def _cancel():
            try:
                modal_overlay.destroy()
            except Exception:
                pass
        
        cancel_btn = tk.Button(buttons, text="Cancel", font=btn_font, bg="#cccccc", fg="#000", bd=0, relief="flat", padx=int(22 * scale), pady=int(12 * scale), command=_cancel)
        cancel_btn.pack(side="left")
        
        confirm_btn = tk.Button(buttons, text="Proceed", font=btn_font, bg="#b42e41", fg="white", bd=0, relief="flat", padx=int(22 * scale), pady=int(12 * scale), command=_confirm)
        confirm_btn.pack(side="left", padx=(12, 18))

        # keep a reference in case other code needs to close it
        self._piso_modal = modal_overlay

    def show_no_change_modal(self, one_peso, five_peso, on_confirm=None):
        """Show a strict modal indicating no change coins are available.
        This uses the same layout as `show_piso_modal` but emphasises NO SUPPLY.
        """
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        # Increase modal size for prominence
        modal_w = int(1050 * scale)
        modal_h = int(720 * scale)
        radius = int(22 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_w, height=modal_h, bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Background
        self._draw_round_rect(canvas, 0, 0, modal_w, modal_h, radius, fill="white", outline='')
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_w - inset, modal_h - inset, max(0, radius - inset), fill='', outline="#999999", width=2)

        container = tk.Frame(canvas, bg="white", padx=int(16 * scale), pady=int(12 * scale))

        # Warning icon
        tri_color = "#ffc107"
        mark_color = "#000"
        icon_size = int(110 * scale)
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_w // 2
        top_margin = max(8, int(8 * scale))
        icon_cy = int(radius + top_margin + half)

        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri, icon_cx - half + inset_tri, icon_cy + half - inset_tri, icon_cx + half - inset_tri, icon_cy + half - inset_tri]
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

        # Place the content window below the icon and constrain its width so
        # the inner contents are centered and consistently wrapped.
        content_y = icon_cy + int(half) + int(8 * scale)
        content_width = max(260, modal_w - int(120 * scale))
        # Inner wrap margin to leave breathing room inside the container
        inner_wrap_margin = int(20 * scale)
        canvas.create_window(modal_w // 2, content_y, window=container, anchor='n', width=content_width)

        # Ensure icon is above the content
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        tk.Label(container, text="No Change Available", font=title_font, bg="white", fg="#333").pack(pady=(0, int(12 * scale)))

        # Show explicit
        info_font = ("Arial", max(18, int(20 * scale)))
        counts_frame = tk.Frame(container, bg="white")
        counts_frame.pack(pady=(6, 6))

        def _status_text(val):
            try:
                if isinstance(val, int) and val == 0:
                    return "Unavailable"
                else:
                    return "Available"
            except Exception:
                return "Unavailable"

        tk.Label(counts_frame, text="1 Peso:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=_status_text(one_peso), font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#b42e41").pack(side="left", padx=(10, 20))
        tk.Label(counts_frame, text="5 Peso:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=_status_text(five_peso), font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#b42e41").pack(side="left", padx=(10, 0))

        # Prominent WARNING title and dispenser status line
        info_title = "NOTICE"
        info_title_font = ("Arial", max(22, int(26 * scale)), "bold")
        tk.Label(container, text=info_title, font=info_title_font, bg="white", fg="#b42e41", justify="center").pack(pady=(12, 10))

        dispenser_line = "The coin change dispenser is out of 1‑peso and/or 5‑peso coins."
        dispenser_font = ("Arial", max(20, int(22 * scale)), "bold")
        tk.Label(container, text=dispenser_line, font=dispenser_font, bg="white", fg="#333", justify="center", wraplength=content_width - int(28 * scale)).pack(pady=(0, 14))

        # Instruction sentence
        warn = "To complete your payment, kindly insert the exact amount. If exact payment is not available, please cancel the transaction and seek assistance from our support personnel."
        tk.Label(container, text=warn, font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#333", wraplength=content_width - int(28 * scale), justify="center").pack(pady=(12, 20))
        tk.Frame(container, height=int(20 * scale), bg="white").pack(fill="x")

        # Buttons
        buttons = tk.Frame(container, bg="white")
        buttons.pack(pady=(int(12 * scale), 0))
        btn_font = ("Arial", max(16, int(20 * scale)), "bold")

        def _confirm():
            try:
                if on_confirm:
                    on_confirm()
            finally:
                try:
                    modal_overlay.destroy()
                except Exception:
                    pass

        def _cancel():
            try:
                modal_overlay.destroy()
            except Exception:
                pass
        
        cancel_btn = tk.Button(buttons, text="Cancel", font=btn_font, bg="#cccccc", fg="#000", bd=0, relief="flat", padx=int(22 * scale), pady=int(12 * scale), command=_cancel)
        cancel_btn.pack(side="left")
        
        confirm_btn = tk.Button(buttons, text="Continue", font=btn_font, bg="#b42e41", fg="white", bd=0, relief="flat", padx=int(22 * scale), pady=int(12 * scale), command=_confirm)
        confirm_btn.pack(side="left", padx=(12, 18))

        # keep a reference in case other code needs to close it
        self._no_change_modal = modal_overlay

    def show_insufficient_paper_modal(self, pages_needed, remaining_paper, on_reconfigure=None, on_cancel=None, on_back_to_options=None):
        """Show a modal indicating insufficient paper for the print job.
        
        Args:
            pages_needed: Number of pages needed to print
            remaining_paper: Number of sheets remaining
            on_reconfigure: Callback for reconfigure/edit page range button
            on_cancel: Callback for cancel button
            on_back_to_options: Callback for back to options button
        """
        modal_overlay = tk.Frame(self, bg="white")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))

        # Modal size
        modal_w = int(1050 * scale)
        modal_h = int(720 * scale)
        radius = int(20 * scale)

        canvas = tk.Canvas(modal_overlay, width=modal_w, height=modal_h, bg="white", highlightthickness=0)
        canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Background
        self._draw_round_rect(canvas, 0, 0, modal_w, modal_h, radius, fill="white", outline='')
        inset = 1
        self._draw_round_rect(canvas, inset, inset, modal_w - inset, modal_h - inset, max(0, radius - inset), fill='', outline="#999999", width=2)

        container = tk.Frame(canvas, bg="white", padx=int(16 * scale), pady=int(12 * scale))

        # Warning icon (red/orange triangle)
        tri_color = "#dc3545"  # Red for insufficient paper
        mark_color = "#000"
        icon_size = int(110 * scale)
        half = icon_size / 2.0 * 1.25
        icon_cx = modal_w // 2
        top_margin = max(8, int(8 * scale))
        icon_cy = int(radius + top_margin + half)

        inset_tri = max(0, int(icon_size * 0.02))
        pts = [icon_cx, icon_cy - half + inset_tri, icon_cx - half + inset_tri, icon_cy + half - inset_tri, icon_cx + half - inset_tri, icon_cy + half - inset_tri]
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

        # Place the content window below the icon
        content_y = icon_cy + int(half) + int(8 * scale)
        content_width = max(260, modal_w - int(120 * scale))
        inner_wrap_margin = int(20 * scale)
        canvas.create_window(modal_w // 2, content_y, window=container, anchor='n', width=content_width)

        # Ensure icon is above the content
        try:
            canvas.tag_raise(poly_id)
            canvas.tag_raise(text_id)
        except Exception:
            pass

        # Title
        title_font = ("Bebas Neue", max(34, int(36 * scale)), "bold")
        tk.Label(container, text="Not Enough Paper", font=title_font, bg="white", fg="#333").pack(pady=(0, int(12 * scale)))

        # Paper details with better formatting
        info_font = ("Arial", max(18, int(20 * scale)))
        counts_frame = tk.Frame(container, bg="white")
        counts_frame.pack(pady=(8, 12))

        tk.Label(counts_frame, text="You want to print:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=str(pages_needed) + " pages", font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#dc3545").pack(side="left", padx=(8, 20))
        tk.Label(counts_frame, text="Available paper:", font=info_font, bg="white", fg="#000").pack(side="left")
        tk.Label(counts_frame, text=str(remaining_paper) + " sheets", font=("Arial", max(20, int(22 * scale)), "bold"), bg="white", fg="#dc3545").pack(side="left", padx=(8, 0))

        # Notice
        notice_title = "WHAT SHOULD YOU DO?"
        notice_title_font = ("Arial", max(22, int(26 * scale)), "bold")
        tk.Label(container, text=notice_title, font=notice_title_font, bg="white", fg="#dc3545", justify="center").pack(pady=(14, 12))

        # Main message - friendlier tone
        message = "There is not enough paper to print your document. Please choose what to do:"
        message_font = ("Arial", max(20, int(22 * scale)))
        tk.Label(container, text=message, font=message_font, bg="white", fg="#333", justify="center", wraplength=content_width - inner_wrap_margin).pack(pady=(0, 14))

        # Instructions with button descriptions
        option_font = ("Arial", max(16, int(18 * scale)))
        
        # Option 1
        tk.Label(container, text="• Print Fewer Pages: Change your page selection and continue", font=option_font, bg="white", fg="#555", justify="left", wraplength=content_width - inner_wrap_margin).pack(anchor="w", padx=int(15 * scale), pady=(6, 4))
        
        # Option 2
        tk.Label(container, text="• Start Over: Go back home and choose a different file", font=option_font, bg="white", fg="#555", justify="left", wraplength=content_width - inner_wrap_margin).pack(anchor="w", padx=int(15 * scale), pady=(4, 4))
        
        # Option 3
        tk.Label(container, text="• Get Help: Ask our staff to load more paper", font=option_font, bg="white", fg="#555", justify="left", wraplength=content_width - inner_wrap_margin).pack(anchor="w", padx=int(15 * scale), pady=(4, 12))
        tk.Frame(container, height=int(10 * scale), bg="white").pack(fill="x")

        # Buttons
        buttons = tk.Frame(container, bg="white")
        buttons.pack(pady=(int(12 * scale), 0))
        btn_font = ("Arial", max(14, int(18 * scale)), "bold")

        def _cancel():
            try:
                modal_overlay.destroy()
                if on_cancel:
                    on_cancel()
            except Exception:
                pass

        def _back_options():
            try:
                modal_overlay.destroy()
                if on_back_to_options:
                    on_back_to_options()
            except Exception:
                pass

        cancel_btn = tk.Button(buttons, text="Cancel", font=btn_font, bg="#cccccc", fg="#000", bd=0, relief="flat", padx=int(16 * scale), pady=int(10 * scale), command=_cancel)
        cancel_btn.pack(side="left", padx=(4, 8))

        back_btn = tk.Button(buttons, text="Back to Option Screen", font=btn_font, bg="#b42e41", fg="white", bd=0, relief="flat", padx=int(16 * scale), pady=int(10 * scale), command=_back_options)
        back_btn.pack(side="left", padx=(4, 0))

        # Store reference
        self._insufficient_paper_modal = modal_overlay

    def go_back_to_options(self):
        preserved = {
            'preserved_options': {
                'page_range': self.data.get('pages_range'),
                'pages_range_mode': self.data.get('pages_range_mode'),
                'color_mode': self.data.get('color_mode'),
                'num_copies': self.data.get('num_copies'),
                'page_size': self.data.get('page_size'),
                'scale_mode': self.data.get('scale_mode'),
                'scale_percentage': self.data.get('scale_percentage'),
            }
        }
        options_data = {**getattr(self.controller, 'job_data', {}), **preserved}
        self.controller.show_frame("OptionsScreen", data=options_data)

    def go_back_to_start_printing(self):
        """Go back to home screen (start printing screen)."""
        # Cancel the job in Firebase before going back
        job_id = self.data.get('job_id')
        if job_id:
            try:
                from config.firebase_config import db
                import time
                
                print(f"[SummaryScreen] Cancelling job {job_id} before going back to start")
                
                # Update root level (NEW HIERARCHICAL STRUCTURE)
                root_ref = db.reference(f'jobs/print_jobs/{job_id}')
                root_ref.update({'status': 'cancelled', 'updated_at': time.time()})
                
                # Update details level
                details_ref = db.reference(f'jobs/print_jobs/{job_id}/details/0')
                details_ref.update({'status': 'cancelled', 'updated_at': time.time()})
                
                print(f"[SummaryScreen] Job {job_id} successfully cancelled")
            except Exception as e:
                print(f"[SummaryScreen] Error cancelling job: {e}")
                import traceback
                traceback.print_exc()
        
        home_screen = self.controller.frames.get("HomeScreen")
        if home_screen:
            home_screen.show_main_view()
        self.controller.show_frame("HomeScreen")

    def _add_back_icon_button(self, parent, size=80):
        """Create a circular back arrow canvas and return it so callers can pack/grid it."""
        # Colors
        circle_fill = "#e6e6e6"    
        circle_outline = "#e6e6e6"  
        arrow_color = "#000000"   
        canvas = tk.Canvas(parent, width=size, height=size, bg="white", highlightthickness=0)
        margin = max(4, int(size * 0.08))
        circle_w = 0 
        arrow_w = max(5, int(size * 0.09))
        circle = canvas.create_oval(margin, margin, size - margin, size - margin, outline=circle_outline, width=circle_w, fill=circle_fill)

        cx = size / 2.0
        cy = size / 2.0
        d = size - 2 * margin  
        arrow_span = 0.52 * d   
        head_len = 0.18 * d     
        head_half_h = 0.18 * d  

        head_tip_x = cx - arrow_span / 2.0
        head_base_x = head_tip_x + head_len
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
        canvas.bind("<Button-1>", lambda _: self.go_back_to_options())
        return canvas

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
