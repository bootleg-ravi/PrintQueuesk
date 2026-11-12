# main_app.py

import tkinter as tk
import threading
import time
import socketio
import requests
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

# SocketIO Configuration
#SOCKETIO_SERVER = "http://localhost:5000"  # Local server


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

        # SocketIO setup
        self.socketio_client = socketio.Client(logger=True, engineio_logger=True)
        self.setup_socketio_events()
        self.start_socketio_connection()

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
        
        # Disconnect socket.io
        if self.socketio_client.connected:
            self.socketio_client.disconnect()
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
        # Fill rounded corners and edges
        canvas.create_oval(0, 0, radius*2, radius*2, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(modal_width - radius*2, 0, modal_width, radius*2, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(0, modal_height - radius*2, radius*2, modal_height, fill="white", outline="#999999", width=border_width)
        canvas.create_oval(modal_width - radius*2, modal_height - radius*2, modal_width, modal_height, fill="white", outline="#999999", width=border_width)
        
        # Rectangles for sides
        canvas.create_rectangle(radius, 0, modal_width - radius, modal_height, fill="white", outline="")
        canvas.create_rectangle(0, radius, modal_width, modal_height - radius, fill="white", outline="")
        
        # Draw visible borders on all sides
        canvas.create_line(radius, border_width//2, modal_width - radius, border_width//2, fill="#999999", width=border_width)
        canvas.create_line(modal_width - border_width//2, radius, modal_width - border_width//2, modal_height - radius, fill="#999999", width=border_width)
        canvas.create_line(radius, modal_height - border_width//2, modal_width - radius, modal_height - border_width//2, fill="#999999", width=border_width)
        canvas.create_line(border_width//2, radius, border_width//2, modal_height - radius, fill="#999999", width=border_width)
        
        # Create main container for content
        main_frame = tk.Frame(canvas, bg="white")
        
        # Icon parameters (red circle with '!')
        icon_size = int(110 * scale)
        circle_color = "#b42e41"  # Red color
        icon_color = "#FFF"  # White
        
        # Draw red circle icon at top
        icon_cx = modal_width // 2
        top_margin = int(25 * scale)
        icon_cy = int(top_margin + icon_size / 2)
        
        # Draw circle
        circle_id = canvas.create_oval(
            icon_cx - icon_size // 2,
            icon_cy - icon_size // 2,
            icon_cx + icon_size // 2,
            icon_cy + icon_size // 2,
            fill=circle_color,
            outline=circle_color,
            width=0
        )
        
        # Draw '!' character in circle
        try:
            icon_font_size = max(12, int(icon_size * 0.65))
            icon_font = ("Arial", icon_font_size, "bold")
        except Exception:
            icon_font = ("Arial", int(icon_size * 0.65), "bold")
        
        icon_id = canvas.create_text(icon_cx, icon_cy, text='!', font=icon_font, fill=icon_color, anchor='center')
        
        # Content position below icon
        content_y = icon_cy + int(icon_size / 2) + int(15 * scale)
        canvas.create_window(modal_width // 2, content_y, window=main_frame, anchor='n')
        
        # Content
        padding = int(12 * scale)
        content = tk.Frame(main_frame, bg="white", padx=padding, pady=padding)
        content.pack(expand=True)
        
        # Title
        title_font = ("Bebas Neue", max(34, int(40 * scale)), "bold")
        tk.Label(content, text="Are You Still There?", font=title_font, bg="white", fg="#333").pack(pady=(0, int(14 * scale)))
        
        # Subtitle line
        subtitle_font = ("Arial", max(12, int(14 * scale)))
        tk.Label(content, text="Session Timeout Warning", font=subtitle_font, bg="white", fg="#999999").pack(pady=(0, int(16 * scale)))
        
        # Message - professional and detailed
        message_font = ("Arial", max(14, int(18 * scale)))
        
        msg1 = tk.Label(content, text="Your session has been inactive for 5 minutes.", font=message_font, bg="white", fg="#333", justify="center")
        msg1.pack(pady=(0, int(8 * scale)))
        
        msg2 = tk.Label(content, text="For your security and to free up printing resources,", font=message_font, bg="white", fg="#555", justify="center")
        msg2.pack(pady=(0, int(6 * scale)))
        
        msg3 = tk.Label(content, text="your session will be ended if you do not confirm", font=message_font, bg="white", fg="#555", justify="center")
        msg3.pack(pady=(0, int(6 * scale)))
        
        msg4 = tk.Label(content, text="your presence within the next 10 seconds.", font=message_font, bg="white", fg="#555", justify="center")
        msg4.pack(pady=(0, int(24 * scale)))
        
        # Countdown timer label - MUCH BIGGER with red emphasis
        countdown_font = ("Arial", max(56, int(69 * scale)), "bold")
        countdown_label = tk.Label(content, text="10", font=countdown_font, bg="white", fg="#b42e41")
        countdown_label.pack(pady=(0, int(8 * scale)))
        
        # Seconds label
        seconds_label_font = ("Arial", max(14, int(16 * scale)))
        tk.Label(content, text="seconds remaining", font=seconds_label_font, bg="white", fg="#999999", justify="center").pack(pady=(0, int(24 * scale)))
        
        # Button
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
        
        # Raise icon elements above content
        try:
            canvas.tag_raise(circle_id)
            canvas.tag_raise(icon_id)
        except Exception:
            pass
        
        # Store references
        self._idle_modal = modal_overlay
        self._idle_countdown_label = countdown_label
        self._idle_countdown_seconds = 10
        
        # Set flag to prevent event bindings from resetting the timer during countdown
        self._countdown_active = True
        
        # Force update
        self.update_idletasks()
        
        # Print debug message
        print("[MainApp] Idle confirmation modal displayed with frame overlay")
        print(f"[MainApp] Modal overlay: {modal_overlay}")
        print(f"[MainApp] Canvas: {canvas}")
        print(f"[MainApp] Countdown label: {countdown_label}")
        
        # Start 10-second countdown
        self._update_idle_countdown()
    
    def _update_idle_countdown(self):
        """Update the countdown timer."""
        if not self.idle_modal_visible:
            return
        
        if not hasattr(self, '_idle_countdown_label') or self._idle_countdown_label is None:
            return
        
        try:
            # Check if label widget still exists
            if not self._idle_countdown_label.winfo_exists():
                return
            
            if hasattr(self, '_idle_countdown_seconds') and self._idle_countdown_seconds >= 0:
                remaining = self._idle_countdown_seconds
                self._idle_countdown_label.config(text=str(remaining))
                # Force visual update
                self._idle_countdown_label.update()
                self.update_idletasks()
                print(f"[MainApp] Countdown: {remaining} seconds")
                
                if remaining > 0:
                    self._idle_countdown_seconds -= 1
                    self.idle_confirmation_timer = self.after(1000, self._update_idle_countdown)
                else:
                    # 0 seconds elapsed, return to start
                    print("[MainApp] Idle timeout - returning to start")
                    self._return_to_start_from_idle()
        except Exception as e:
            print(f"[MainApp] Error updating countdown: {e}")
            self._return_to_start_from_idle()
    
    def _confirm_idle_activity(self):
        """User clicked 'Yes', reset the idle timer and stay on current screen."""
        print("[MainApp] User confirmed idle activity - closing modal and resetting timer")
        # Clear flag to allow normal operation to resume
        self._countdown_active = False
        self.idle_modal_visible = False
        self._close_idle_confirmation_modal()
        # Reset the idle timer (no event param, so allowed even though modal was visible)
        self._reset_global_idle_timer()
        print("[MainApp] User confirmed - modal closed and timer reset")
    
    def _confirm_idle_activity_with_modal(self, modal_window):
        """User clicked 'Yes', reset the idle timer and close the modal."""
        print("[MainApp] User confirmed idle activity - closing modal and resetting timer")
        try:
            if modal_window.winfo_exists():
                modal_window.destroy()
        except Exception as e:
            print(f"[MainApp] Error destroying modal: {e}")
        self._close_idle_confirmation_modal()
        # Reset the idle timer
        self._reset_global_idle_timer()
    
    def _close_idle_confirmation_modal(self):
        """Close the idle confirmation modal."""
        print("[MainApp] _close_idle_confirmation_modal called")
        
        # Cancel any pending countdown timer
        if self.idle_confirmation_timer:
            try:
                self.after_cancel(self.idle_confirmation_timer)
                self.idle_confirmation_timer = None
                print("[MainApp] Canceled pending countdown timer")
            except Exception as e:
                print(f"[MainApp] Error canceling countdown timer: {e}")
        
        # Destroy modal window (Toplevel)
        if hasattr(self, '_idle_modal') and self._idle_modal:
            try:
                if self._idle_modal.winfo_exists():
                    self._idle_modal.destroy()
                    print("[MainApp] Idle modal destroyed")
            except Exception as e:
                print(f"[MainApp] Error destroying idle modal: {e}")
        
        # Clean up references
        self._idle_modal = None
        self._idle_countdown_label = None
        self.idle_modal_visible = False
        self._countdown_active = False  # Clear flag to allow timer resets again
        
        # Re-bind HotspotScreen event bindings
        try:
            hotspot_frame = self.frames.get("HotspotScreen")
            if hotspot_frame:
                controller = self  # Capture MainApp instance
                hotspot_frame.bind_all('<Any-KeyPress>', lambda e, c=controller: c._reset_global_idle_timer())
                hotspot_frame.bind_all('<Any-Button>', lambda e, c=controller: c._reset_global_idle_timer())
                hotspot_frame.bind_all('<Motion>', lambda e, c=controller: c._reset_global_idle_timer())
                print("[MainApp] Rebound HotspotScreen event bindings after modal closed")
        except Exception as e:
            print(f"[MainApp] Could not rebind HotspotScreen events: {e}")
        
        print("[MainApp] Idle confirmation modal fully closed")
        
        if self.idle_confirmation_timer:
            try:
                self.after_cancel(self.idle_confirmation_timer)
            except Exception:
                pass
            self.idle_confirmation_timer = None
        
        print("[MainApp] Idle confirmation modal closed")
    
    def _cancel_active_jobs(self):
        """Cancel any active print jobs in Firebase when idle timeout occurs."""
        try:
            # Check all screens for active job_ids
            job_id = None
            
            # Check OptionsScreen
            options_screen = self.frames.get("OptionsScreen")
            if options_screen and hasattr(options_screen, 'job_id'):
                job_id = options_screen.job_id
            
            # Check SummaryScreen
            if not job_id:
                summary_screen = self.frames.get("SummaryScreen")
                if summary_screen and hasattr(summary_screen, 'job_id'):
                    job_id = summary_screen.job_id
            
            # Check PaymentScreen
            if not job_id:
                payment_screen = self.frames.get("PaymentScreen")
                if payment_screen and hasattr(payment_screen, 'job_id'):
                    job_id = payment_screen.job_id
            
            # If we found a job_id, cancel it in Firebase
            if job_id:
                print(f"[MainApp] Cancelling job {job_id} due to idle timeout")
                
                # Update root level status (for dashboard)
                job_ref = db.reference(f'jobs/print_jobs/{job_id}')
                job_ref.update({
                    'status': 'cancelled',
                    'updated_at': time.time()
                })
                
                # Also update details level status (for consistency)
                detail_ref = db.reference(f'jobs/print_jobs/{job_id}/details/0')
                detail_ref.update({
                    'status': 'cancelled',
                    'updated_at': time.time()
                })
                
                print(f"[MainApp] Job {job_id} successfully cancelled")
            else:
                print("[MainApp] No active job found to cancel")
        except Exception as e:
            print(f"[MainApp] Error cancelling active jobs: {e}")
    
    def _return_to_start_from_idle(self):
        """10 seconds passed without user confirmation, return to start button."""
        print("[MainApp] Returning to start from idle timeout")
        
        # Cancel any active print jobs in Firebase before returning to start
        self._cancel_active_jobs()
        
        # Close modal
        self._close_idle_confirmation_modal()
        
        # Show home screen
        self.show_frame("HomeScreen")
        
        # Return to main view (start button)
        try:
            home_frame = self.frames.get("HomeScreen")
            if home_frame and hasattr(home_frame, 'show_main_view'):
                home_frame.show_main_view()
                print("[MainApp] Returned to start button")
        except Exception as e:
            print(f"[MainApp] Error returning to main view: {e}")
    
    def _go_to_home_on_idle(self):
        """Return to home screen after 5 minutes of inactivity."""
        print("[MainApp] Idle timeout reached - returning to home screen")
        self.show_frame("HomeScreen")
        
        # If on HomeScreen, return to Start Printing button (main view)
        try:
            home_frame = self.frames.get("HomeScreen")
            if home_frame and hasattr(home_frame, 'show_main_view'):
                home_frame.show_main_view()
        except Exception as e:
            print(f"[MainApp] Error returning to main view: {e}")

    def lock_window(self, event=None):
        """Intercept Alt-Tab and keep the window on top."""
        try:
            self.attributes('-topmost', True)
            self.lift()
            self.focus_force()
        except Exception as e:
            print(f"Error locking window: {e}")

        return "break"

    # --- Socket.IO Methods ---
    def setup_socketio_events(self):
        @self.socketio_client.on('connect')
        def on_connect():
            print("Successfully connected to the server.")

        @self.socketio_client.on('disconnect')
        def on_disconnect():
            print("Disconnected from the server.")

        @self.socketio_client.on('file_uploaded')
        def on_file_uploaded(data):
            print(f"[DEBUG] Received file_uploaded event: {data}")
            self.job_data = data
            self.download_and_proceed()

        @self.socketio_client.on('file_status_update')
        def on_status_update(data):
            # Pass status update to the HomeScreen
            home_frame = self.frames.get("HomeScreen")
            if home_frame:
                self.after(0, home_frame.update_status, data)

    def start_socketio_connection(self):
        """Start SocketIO connection in a separate thread with reconnection logic."""
        def connect_loop():
            while True:
                try:
                    if not self.socketio_client.connected:
                        print(f"Attempting to connect to {SOCKETIO_SERVER}...")
                        self.socketio_client.connect(SOCKETIO_SERVER, transports=['polling'], wait_timeout=30)
                except Exception as e:
                    print(f"Socket.IO connection failed: {e}. Retrying in 10 seconds.")
                time.sleep(10)

        socketio_thread = threading.Thread(target=connect_loop, daemon=True)
        socketio_thread.start()

    def start_downloads_cleanup(self):
        """Start automatic cleanup of old files in downloads folder (5+ minutes old)."""
        def cleanup_loop():
            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
            
            while True:
                try:
                    # Wait 1 minute between cleanup checks
                    time.sleep(60)
                    
                    if not os.path.exists(downloads_dir):
                        continue
                    
                    current_time = time.time()
                    files_deleted = 0
                    
                    # Iterate through all files in downloads directory
                    for filename in os.listdir(downloads_dir):
                        file_path = os.path.join(downloads_dir, filename)
                        
                        # Skip if not a file
                        if not os.path.isfile(file_path):
                            continue
                        
                        try:
                            # Get file modification time
                            file_age = current_time - os.path.getmtime(file_path)
                            
                            # Delete if older than 5 minutes (300 seconds)
                            if file_age > 300:
                                os.remove(file_path)
                                files_deleted += 1
                                print(f"[Cleanup] Deleted old file: {filename} (age: {file_age:.0f}s)")
                        except Exception as e:
                            print(f"[Cleanup] Error deleting {filename}: {e}")
                    
                    if files_deleted > 0:
                        print(f"[Cleanup] Removed {files_deleted} old file(s) from downloads folder")
                        
                except Exception as e:
                    print(f"[Cleanup] Error during cleanup cycle: {e}")

        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        print("[Cleanup] Started automatic file cleanup (5 minute expiry)")

    def download_and_proceed(self):
        """Download the file from the server and transition to the Options screen."""
        download_url = self.job_data.get('download_url')
        file_name = self.job_data.get('file_name')
        
        if not all([download_url, file_name]):
            messagebox.showerror("Error", "Incomplete file data received from server.")
            return

        home_frame = self.frames.get("HomeScreen")
        if home_frame:
            # Show the transition screen
            transition_frame = home_frame.show_transition_screen()
            self.update()  # Force update to show the transition screen
            
            # Update status
            home_frame.set_status(f"Downloading {file_name}...")

        try:
            local_download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
            os.makedirs(local_download_dir, exist_ok=True)

            # Prefer a unique filename to avoid Windows permission/lock issues
            job_id = str(self.job_data.get('job_id') or '')
            base_name = f"{job_id}_{file_name}" if job_id else file_name
            local_file_path = os.path.join(local_download_dir, base_name)
            # If path exists and is locked/read-only, fall back to a unique suffix
            if os.path.exists(local_file_path):
                try:
                    os.remove(local_file_path)
                except Exception:
                    name, ext = os.path.splitext(base_name)
                    counter = 1
                    while True:
                        candidate = os.path.join(local_download_dir, f"{name}_{counter}{ext}")
                        if not os.path.exists(candidate):
                            local_file_path = candidate
                            break
                        counter += 1
            
            headers = {'User-Agent': 'PrintQueuesk-GUI/1.0', 'Accept': '*/*'}
            response = requests.get(download_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # Write to a temp file first, then atomically replace to target path
            try:
                with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir=local_download_dir, suffix='.part') as tmp:
                    temp_path = tmp.name
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            tmp.write(chunk)
                os.replace(temp_path, local_file_path)
            except PermissionError as pe:
                # Fallback to a unique name if replace fails due to lock
                name, ext = os.path.splitext(os.path.basename(local_file_path))
                counter = 1
                while True:
                    candidate = os.path.join(local_download_dir, f"{name}_{counter}{ext}")
                    try:
                        os.replace(temp_path, candidate)
                        local_file_path = candidate
                        break
                    except PermissionError:
                        counter += 1
                # Note: do not re-raise; continue
            
            if os.path.getsize(local_file_path) == 0:
                raise Exception("Downloaded file is empty.")

            self.job_data['file_path'] = local_file_path
            print(f"File downloaded to: {local_file_path}")

            # Prewarm Options preview (render first page in background if possible)
            try:
                options_frame = self.frames.get("OptionsScreen")
                if options_frame and hasattr(options_frame, 'prewarm_preview'):
                    options_frame.prewarm_preview(local_file_path, file_name)
            except Exception as _:
                pass

            # Hide the preparing overlay first, then navigate to Options
            if hasattr(home_frame, 'hide_transition_screen'):
                home_frame.hide_transition_screen()
            self.show_frame("OptionsScreen", data=self.job_data)

        except Exception as e:
            error_msg = f"Failed to download file: {str(e)}"
            print(f"[ERROR] {error_msg}")
            if hasattr(home_frame, 'hide_transition_screen'):
                home_frame.hide_transition_screen()
            messagebox.showerror("Download Error", error_msg)
            self.show_frame("HomeScreen")  # Go back home on error

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()