# main_app.py

import tkinter as tk
import threading
import time
import base64
import tempfile
import os
import sys
from tkinter import messagebox

# Import screen modules
from screens.home_screen import HomeScreen
from screens.hotspot_screen import HotspotScreen
from screens.options_screen import OptionsScreen
from screens.summary_screen import SummaryScreen
from screens.payment_screen import PaymentScreen
from screens.usb_drive_screen import USBDriveScreen

# Firebase config
from config.firebase_config import db

# Set to True to keep the app always-on-top and intercept Alt-Tab.
# When False, the app behaves like a normal window.
LOCK_WINDOW = True

class MainApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("PrintQueuesk")
        self.configure(bg="white")
        self.attributes('-fullscreen', True)

        # Optional lock mode: keep window on top and intercept Alt-Tab.
        if LOCK_WINDOW:
            self.attributes('-topmost', True)
            self.bind("<Alt-Tab>", self.lock_window)

        self.bind("<Escape>", self.close_application)

        # Container for all frames/screens
        container = tk.Frame(self, bg="white")
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        # Initialize all screens
        for F in (HomeScreen, HotspotScreen, OptionsScreen, SummaryScreen, PaymentScreen, USBDriveScreen):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Start Firebase Realtime Database listener for serverless web uploads
        self.start_firebase_listener()

        # Application state variables
        self.job_data = {}
        self.global_idle_timer = None
        self.idle_confirmation_timer = None
        self.idle_modal_visible = False
        self.idle_timeout = 300000  # 5 minutes in milliseconds (300000ms = 300 seconds)
        self.idle_confirmation_timeout = 10000  # 10 seconds in milliseconds
        self.current_frame = "HomeScreen"
        self._on_qr_code_view = False  # Track if user is on QR code view within HomeScreen
        self._countdown_active = False  # Flag to completely block timer resets during countdown

        self.start_downloads_cleanup()
        self.show_frame("HomeScreen")
        self._reset_global_idle_timer()

    def show_frame(self, page_name, data=None):
        if self.idle_modal_visible:
            print(f"[MainApp] Idle modal visible - ignoring frame switch request to {page_name}")
            return
        
        # Store current frame
        self.current_frame = page_name
        print(f"[MainApp] Switching to frame: {page_name}")
        
        # Ensure any HomeScreen transition overlay is hidden when switching away from Home
        if page_name != "HomeScreen":
            try:
                home_frame = self.frames.get("HomeScreen")
                if home_frame and hasattr(home_frame, 'hide_transition_screen'):
                    home_frame.hide_transition_screen()
            except Exception:
                pass

        frame = self.frames[page_name]
        # Raise first so the user immediately sees the target screen
        frame.tkraise()
        
        # Handle idle timer based on current frame
        if page_name == "HomeScreen":
            # On home screen, cancel the global 5-minute timer
            print("[MainApp] On HomeScreen - canceling global idle timer")
            self._cancel_global_idle_timer()
        else:
            # On other frames (like WiFi/QR), start the 5-minute timer
            print(f"[MainApp] On {page_name} - starting global idle timer")
            self._reset_global_idle_timer()
        
        # Always call load_data if the method exists, passing data if available
        if hasattr(frame, 'load_data'):
            try:
                self.after(0, frame.load_data, data)
            except Exception:
                # Fallback to direct call if scheduling fails
                frame.load_data(data)

    def close_application(self, event=None):
        """Cleanly close the application."""
        # Stop hotspot server if running
        hotspot_frame = self.frames.get("HotspotScreen")
        if hotspot_frame and hasattr(hotspot_frame, 'stop_server'):
            hotspot_frame.stop_server()
        
        self.quit()

    def _cancel_global_idle_timer(self):
        """Cancel the global idle timer without restarting it."""
        if self.global_idle_timer:
            try:
                self.after_cancel(self.global_idle_timer)
            except Exception:
                pass
            self.global_idle_timer = None
        
        # Also cancel idle confirmation if visible
        if self.idle_confirmation_timer:
            try:
                self.after_cancel(self.idle_confirmation_timer)
            except Exception:
                pass
            self.idle_confirmation_timer = None
        
        self.idle_modal_visible = False
    
    def _reset_global_idle_timer(self, event=None):
        """Reset the global 5-minute idle timer."""
        # If countdown is active, don't allow any timer resets from events
        if self._countdown_active:
            if event is not None:
                print("[MainApp] Countdown active - ignoring idle timer reset request")
            return
        
        # Cancel the existing timer if any
        if self.global_idle_timer:
            try:
                self.after_cancel(self.global_idle_timer)
            except Exception:
                pass
        
        if self.idle_confirmation_timer:
            try:
                self.after_cancel(self.idle_confirmation_timer)
            except Exception:
                pass
        
        if self.current_frame != "HomeScreen" or hasattr(self, '_on_qr_code_view') and self._on_qr_code_view:
            self.global_idle_timer = self.after(self.idle_timeout, self._show_idle_confirmation_modal)
            print(f"[MainApp] Idle timer set for {self.idle_timeout}ms on {self.current_frame}")
    
    def _show_idle_confirmation_modal(self):
        """Show confirmation modal asking if user is still there - using remaining paper modal design."""
        print("[MainApp] _show_idle_confirmation_modal called")
        print(f"[MainApp] Setting idle_modal_visible to True (currently: {self.idle_modal_visible})")
        self.idle_modal_visible = True
        print(f"[MainApp] idle_modal_visible is now: {self.idle_modal_visible}")
        
        try:
            hotspot_frame = self.frames.get("HotspotScreen")
            if hotspot_frame:
                hotspot_frame.unbind_all('<Any-KeyPress>')
                hotspot_frame.unbind_all('<Any-Button>')
                hotspot_frame.unbind_all('<Motion>')
                print("[MainApp] Unbound HotspotScreen event bindings during modal")
        except Exception as e:
            print(f"[MainApp] Could not unbind HotspotScreen events: {e}")
        
        # Create dark overlay frame on main app (dark background for visual separation)
        print("[MainApp] Creating modal overlay frame...")
        modal_overlay = tk.Frame(self, bg="#ffffff")
        modal_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Bring overlay to the front
        modal_overlay.lift()
        
        # Bind all events on the overlay to prevent interaction with background
        modal_overlay.bind_all('<Button-1>', lambda e: None)
        modal_overlay.bind_all('<Button-2>', lambda e: None)
        modal_overlay.bind_all('<Button-3>', lambda e: None)
        modal_overlay.bind_all('<MouseWheel>', lambda e: None)
        
        print("[MainApp] Modal overlay created and lifted to front")
        
        # Scale based on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        scale = max(1.0, min(screen_w / 1366, screen_h / 768))
        
        # Modal size - SAME as remaining paper modal
        modal_width = int(1050 * scale)
        modal_height = int(750 * scale)
        radius = int(25 * scale)
        border_width = int(3 * scale)
        
        # Create canvas for rounded rectangle design
        canvas = tk.Canvas(modal_overlay, width=modal_width, height=modal_height,
                          bg="white", highlightthickness=0, relief="flat")
        canvas.place(relx=0.5, rely=0.5, anchor="center")
        
        # Draw white rounded rectangle with visible border
        canvas.create_oval(0, 0, radius*2, radius*2, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(modal_width - radius*2, 0, modal_width, radius*2, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(0, modal_height - radius*2, radius*2, modal_height, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(modal_width - radius*2, modal_height - radius*2, modal_width, modal_height, fill="white", outline="#999999", width=border_width)
        
        canvas.create_rectangle(radius, 0, modal_width - radius, modal_height, fill="white", outline="")
        canvas.create_rectangle(0, radius, modal_width, modal_height - radius, fill="white", outline="")
        
        canvas.create_line(radius, border_width//2, modal_width - radius, border_width//2, fill="#999999", width=border_width)
        canvas.create_line(modal_width - border_width//2, radius, modal_width - border_width//2, modal_height - radius, fill="#999999", width=border_width)
        canvas.create_line(radius, modal_height - border_width//2, modal_width - radius, modal_height - border_width//2, fill="#999999", width=border_width)
        canvas.create_line(border_width//2, radius, border_width//2, modal_height - radius, fill="#999999", width=border_width)
        
        main_frame = tk.Frame(canvas, bg="white")
        
        icon_size = int(110 * scale)
        circle_color = "#b42e41"  # Red color
        icon_color = "#FFF"  # White
        
        icon_cx = modal_width // 2
        top_margin = int(25 * scale)
        icon_cy = int(top_margin + icon_size / 2)
        
        circle_id = canvas.create_oval(
            icon_cx - icon_size // 2,
            icon_cy - icon_size // 2,
            icon_cx + icon_size // 2,
            icon_cy + icon_size // 2,
            fill=circle_color,
            outline=circle_color,
            width=0
        )
        
        try:
            icon_font_size = max(12, int(icon_size * 0.65))
            icon_font = ("Arial", icon_font_size, "bold")
        except Exception:
            icon_font = ("Arial", int(icon_size * 0.65), "bold")
        
        icon_id = canvas.create_text(icon_cx, icon_cy, text='!', font=icon_font, fill=icon_color, anchor='center')
        
        content_y = icon_cy + int(icon_size / 2) + int(15 * scale)
        canvas.create_window(modal_width // 2, content_y, window=main_frame, anchor='n')
        
        padding = int(12 * scale)
        content = tk.Frame(main_frame, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)
        
        title_font = ("Bebas Neue", max(34, int(40 * scale)), "bold")
        tk.Label(content, text="Are You Still There?", font=title_font, bg="white", fg="#333").pack(pady=(0, int(14 * scale)))
        
        subtitle_font = ("Arial", max(12, int(14 * scale)))
        tk.Label(content, text="Session Timeout Warning", font=subtitle_font, bg="white", fg="#999999").pack(pady=(0, int(16 * scale)))
        
        message_font = ("Arial", max(14, int(18 * scale)))
        
        tk.Label(content, text="Your session has been inactive for 5 minutes.", font=message_font, bg="white", fg="#333", justify="center").pack(pady=(0, int(8 * scale)))
        tk.Label(content, text="For your security and to free up printing resources,", font=message_font, bg="white", fg="#555", justify="center").pack(pady=(0, int(6 * scale)))
        tk.Label(content, text="your session will be ended if you do not confirm", font=message_font, bg="white", fg="#555", justify="center").pack(pady=(0, int(6 * scale)))
        tk.Label(content, text="your presence within the next 10 seconds.", font=message_font, bg="white", fg="#555", justify="center").pack(pady=(0, int(24 * scale)))
        
        countdown_font = ("Arial", max(56, int(69 * scale)), "bold")
        countdown_label = tk.Label(content, text="10", font=countdown_font, bg="white", fg="#b42e41")
        countdown_label.pack(pady=(0, int(8 * scale)))
        
        seconds_label_font = ("Arial", max(14, int(16 * scale)))
        tk.Label(content, text="seconds remaining", font=seconds_label_font, bg="white", fg="#999999", justify="center").pack(pady=(0, int(24 * scale)))
        
        button_font = ("Arial", max(16, int(20 * scale)), "bold")
        yes_button = tk.Button(
            content,
            text="Yes, I'm Here",
            font=button_font,
            bg="#b42e41",
            fg="white",
            bd=0,
            relief="flat",
            padx=int(50 * scale),
            pady=int(16 * scale),
            command=self._confirm_idle_activity
        )
        yes_button.pack()
        
        try:
            canvas.tag_raise(circle_id)
            canvas.tag_raise(icon_id)
        except Exception:
            pass
        
        self._idle_modal = modal_overlay
        self._idle_countdown_label = countdown_label
        self._idle_countdown_seconds = 10
        self._countdown_active = True
        
        self.update_idletasks()
        self._update_idle_countdown()
    
    def _update_idle_countdown(self):
        """Update the countdown timer."""
        if not self.idle_modal_visible:
            return
        
        if not hasattr(self, '_idle_countdown_label') or self._idle_countdown_label is None:
            return
        
        try:
            if not self._idle_countdown_label.winfo_exists():
                return
            
            if hasattr(self, '_idle_countdown_seconds') and self._idle_countdown_seconds >= 0:
                remaining = self._idle_countdown_seconds
                self._idle_countdown_label.config(text=str(remaining))
                self._idle_countdown_label.update()
                self.update_idletasks()
                
                if remaining > 0:
                    self._idle_countdown_seconds -= 1
                    self.idle_confirmation_timer = self.after(1000, self._update_idle_countdown)
                else:
                    self._return_to_start_from_idle()
        except Exception as e:
            print(f"[MainApp] Error updating countdown: {e}")
            self._return_to_start_from_idle()
    
    def _confirm_idle_activity(self):
        """User clicked 'Yes', reset the idle timer and stay on current screen."""
        self._countdown_active = False
        self.idle_modal_visible = False
        self._close_idle_confirmation_modal()
        self._reset_global_idle_timer()
    
    def _close_idle_confirmation_modal(self):
        """Close the idle confirmation modal."""
        if self.idle_confirmation_timer:
            try:
                self.after_cancel(self.idle_confirmation_timer)
                self.idle_confirmation_timer = None
            except Exception:
                pass
        
        if hasattr(self, '_idle_modal') and self._idle_modal:
            try:
                if self._idle_modal.winfo_exists():
                    self._idle_modal.destroy()
            except Exception:
                pass
        
        self._idle_modal = None
        self._idle_countdown_label = None
        self.idle_modal_visible = False
        self._countdown_active = False
        
        try:
            hotspot_frame = self.frames.get("HotspotScreen")
            if hotspot_frame:
                controller = self
                hotspot_frame.bind_all('<Any-KeyPress>', lambda e, c=controller: c._reset_global_idle_timer())
                hotspot_frame.bind_all('<Any-Button>', lambda e, c=controller: c._reset_global_idle_timer())
                hotspot_frame.bind_all('<Motion>', lambda e, c=controller: c._reset_global_idle_timer())
        except Exception:
            pass

    def _cancel_active_jobs(self):
        """Cancel any active print jobs in Firebase when idle timeout occurs."""
        try:
            job_id = None
            for screen_name in ("OptionsScreen", "SummaryScreen", "PaymentScreen"):
                screen = self.frames.get(screen_name)
                if screen and hasattr(screen, 'job_id') and screen.job_id:
                    job_id = screen.job_id
                    break
            
            if job_id:
                db.reference(f'jobs/print_jobs/{job_id}').update({
                    'status': 'cancelled',
                    'updated_at': time.time()
                })
        except Exception as e:
            print(f"[MainApp] Error cancelling active jobs: {e}")
    
    def _return_to_start_from_idle(self):
        """10 seconds passed without user confirmation, return to start button."""
        self._cancel_active_jobs()
        self._close_idle_confirmation_modal()
        self.show_frame("HomeScreen")
        try:
            home_frame = self.frames.get("HomeScreen")
            if home_frame and hasattr(home_frame, 'show_main_view'):
                home_frame.show_main_view()
        except Exception:
            pass

    def lock_window(self, event=None):
        """Intercept Alt-Tab and keep the window on top."""
        try:
            self.attributes('-topmost', True)
            self.lift()
            self.focus_force()
        except Exception as e:
            print(f"Error locking window: {e}")
        return "break"

    # --- Firebase Realtime Database Listener ---
    def start_firebase_listener(self):
        """Listen to Firebase Realtime Database for new print jobs from the web portal."""
        def listener_loop():
            def stream_handler(event):
                try:
                    if event.event_type in ('put', 'patch') and event.data:
                        jobs = event.data if isinstance(event.data, dict) else {event.path.strip('/'): event.data}
                        for job_id, job_info in jobs.items():
                            if isinstance(job_info, dict) and job_info.get('status') == 'pending':
                                print(f"[Firebase Listener] New pending job detected: {job_id}")
                                self.after(0, lambda j_id=job_id, j_info=job_info: self.process_firebase_job(j_id, j_info))
                except Exception as e:
                    print(f"[Firebase Listener] Stream error: {e}")

            ref = db.reference('jobs/print_jobs')
            ref.listen(stream_handler)

        listener_thread = threading.Thread(target=listener_loop, daemon=True)
        listener_thread.start()
        print("[Firebase] Realtime Database listener started successfully")

    def process_firebase_job(self, job_id, job_data):
        """Decode incoming Base64 file data from Firebase and proceed to Options screen."""
        file_name = job_data.get('file_name')
        file_base64 = job_data.get('file_data')
        
        if not file_name or not file_base64:
            print("[ERROR] Incomplete job data received.")
            return

        home_frame = self.frames.get("HomeScreen")
        if home_frame:
            home_frame.show_transition_screen()
            self.update()
            home_frame.set_status(f"Processing {file_name}...")

        try:
            local_download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
            os.makedirs(local_download_dir, exist_ok=True)
            local_file_path = os.path.join(local_download_dir, f"{job_id}_{file_name}")

            # Strip base64 data URL header if present (e.g. "data:application/pdf;base64,...")
            if ',' in file_base64:
                _, encoded_str = file_base64.split(',', 1)
            else:
                encoded_str = file_base64

            # Decode base64 bytes and save locally
            file_bytes = base64.b64decode(encoded_str)
            with open(local_file_path, 'wb') as f:
                f.write(file_bytes)

            print(f"[SUCCESS] File saved locally to: {local_file_path}")

            # Update job status in Firebase to 'processing'
            db.reference(f'jobs/print_jobs/{job_id}').update({
                'status': 'processing',
                'updated_at': time.time()
            })

            self.job_data = {
                'job_id': job_id,
                'file_name': file_name,
                'file_path': local_file_path
            }

            # Prewarm Options preview if method exists
            try:
                options_frame = self.frames.get("OptionsScreen")
                if options_frame and hasattr(options_frame, 'prewarm_preview'):
                    options_frame.prewarm_preview(local_file_path, file_name)
            except Exception:
                pass

            if hasattr(home_frame, 'hide_transition_screen'):
                home_frame.hide_transition_screen()

            # Transition to Options screen
            self.show_frame("OptionsScreen", data=self.job_data)

        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            print(f"[ERROR] {error_msg}")
            if hasattr(home_frame, 'hide_transition_screen'):
                home_frame.hide_transition_screen()
            messagebox.showerror("Processing Error", error_msg)
            self.show_frame("HomeScreen")

    def start_downloads_cleanup(self):
        """Start automatic cleanup of old files in downloads folder (5+ minutes old)."""
        def cleanup_loop():
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
            while True:
                try:
                    time.sleep(60)
                    if not os.path.exists(downloads_dir):
                        continue
                    current_time = time.time()
                    for filename in os.listdir(downloads_dir):
                        file_path = os.path.join(downloads_dir, filename)
                        if not os.path.isfile(file_path):
                            continue
                        if current_time - os.path.getmtime(file_path) > 300:
                            os.remove(file_path)
                except Exception as e:
                    print(f"[Cleanup] Error: {e}")

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()