# screens/usb_drive_screen.py

import tkinter as tk
from tkinter import messagebox
import os
import shutil
import threading
import time
from pathlib import Path
from PIL import Image, ImageTk
import hashlib
import json
from config.firebase_config import db
from config.hotspot_config import save_file_to_firebase

class USBDriveScreen(tk.Frame):
    """Screen for USB flash drive file transfer with virus detection."""
    
    # Virus signature database (malware hashes)
    VIRUS_SIGNATURES = {
        # Add known malware hashes here (SHA256)
        # Format: "malware_hash": "Malware.Name"
        # This is a basic implementation - in production, use a real antivirus API
    }
    
    # Suspicious file patterns
    SUSPICIOUS_PATTERNS = [
        '.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar',
        '.zip', '.rar', '.7z'  # Archives that might contain executables
    ]
    
    def __init__(self, parent, controller):
        super().__init__(parent, bg="white")
        self.controller = controller
        self.usb_monitor_thread = None
        self.usb_detected = False
        self.detected_drives = {}
        self.current_files = []
        self.selected_files = []
        self.is_monitoring = False
        self.scan_in_progress = False
        self.virus_detection_enabled = True
        self.create_widgets()
        
    def create_widgets(self):
        """Create the UI widgets for USB drive screen with modern design."""
        # Get screen dimensions for responsive scaling
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        scale_factor = min(screen_width / 1920, screen_height / 1080)
        
        # Fonts with scaling
        title_font = ("Bebas Neue", max(28, int(40 * scale_factor)), "bold")
        subtitle_font = ("Arial", max(12, int(16 * scale_factor)))
        section_font = ("Arial", max(14, int(20 * scale_factor)), "bold")
        base_font = ("Arial", max(12, int(16 * scale_factor)))
        button_font = ("Arial", max(14, int(18 * scale_factor)), "bold")
        
        # Padding
        side_pad = int(60 * scale_factor)
        top_pad = int(40 * scale_factor)
        
        # Main container with better padding
        main_frame = tk.Frame(self, bg="white")
        main_frame.pack(fill="both", expand=True, padx=side_pad, pady=top_pad)
        
        # Top section with back button and centered logo
        top_frame = tk.Frame(main_frame, bg="white", height=int(90 * scale_factor))
        top_frame.pack(fill="x", pady=(0, int(20 * scale_factor)))
        top_frame.pack_propagate(False)
        
        # Back button on the left
        back_button = tk.Button(
            top_frame,
            text="← Back to Home",
            font=button_font,
            bg="#959595",
            fg="white",
            activebackground="#777777",
            relief="flat",
            bd=0,
            padx=int(30 * scale_factor),
            pady=int(12 * scale_factor),
            command=self.go_back,
            cursor="hand2"
        )
        back_button.place(x=0, y=int(10 * scale_factor))
        
        # Logo centered absolutely
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(base_dir, 'static', 'img', 'logo.png')
            logo_img = Image.open(logo_path).resize(
                (max(150, int(screen_width * 0.22)), max(45, int(screen_height * 0.09))),
                Image.Resampling.LANCZOS
            )
            self.logo_tk = ImageTk.PhotoImage(logo_img)
            
            # Place logo at absolute center
            logo_label = tk.Label(top_frame, image=self.logo_tk, bg="white")
            logo_label.place(relx=0.5, rely=0.5, anchor="center")
        except Exception as e:
            print(f"Error loading USB screen logo: {e}")
        
        # Title section
        title_frame = tk.Frame(main_frame, bg="white")
        title_frame.pack(fill="x", pady=(0, int(10 * scale_factor)))
        
        title_label = tk.Label(
            title_frame,
            text="USB Flash Drive Transfer",
            font=title_font,
            bg="white",
            fg="#333333"
        )
        title_label.pack(anchor="w")
        
        # Subtitle with icon
        subtitle_label = tk.Label(
            title_frame,
            text="🔒 Secure file transfer from USB drive • Files are automatically scanned",
            font=subtitle_font,
            bg="white",
            fg="#666666"
        )
        subtitle_label.pack(anchor="w", pady=(int(5 * scale_factor), 0))
        
        # Separator line
        separator = tk.Frame(main_frame, bg="#e0e0e0", height=2)
        separator.pack(fill="x", pady=int(20 * scale_factor))
        
        # Content area with two columns
        content_frame = tk.Frame(main_frame, bg="white")
        content_frame.pack(fill="both", expand=True)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)
        
        # LEFT COLUMN - Status and Info
        left_column = tk.Frame(content_frame, bg="white")
        left_column.grid(row=0, column=0, sticky="nsew", padx=(0, int(30 * scale_factor)))
        
        # Status card
        tk.Label(
            left_column,
            text="USB Drive Status",
            font=section_font,
            bg="white",
            fg="#333333"
        ).pack(anchor="w", pady=(0, int(10 * scale_factor)))
        
        self.status_frame = tk.Frame(left_column, bg="#f9f9f9", relief="solid", bd=1, highlightbackground="#e0e0e0")
        self.status_frame.pack(fill="both", expand=True, pady=(0, int(20 * scale_factor)))
        
        status_padding = tk.Frame(self.status_frame, bg="#f9f9f9")
        status_padding.pack(fill="both", expand=True, padx=int(30 * scale_factor), pady=int(30 * scale_factor))
        
        # Center content vertically
        center_container = tk.Frame(status_padding, bg="#f9f9f9")
        center_container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Status icon and text
        self.status_label = tk.Label(
            center_container,
            text="🔍 Scanning for USB drives...",
            font=("Arial", max(16, int(22 * scale_factor)), "bold"),
            bg="#f9f9f9",
            fg="#b42e41",
            justify="center"
        )
        self.status_label.pack(pady=(0, int(10 * scale_factor)))
        
        self.drive_info_label = tk.Label(
            center_container,
            text="Please insert a USB flash drive",
            font=base_font,
            bg="#f9f9f9",
            fg="#666666",
            justify="center"
        )
        self.drive_info_label.pack(pady=(0, int(20 * scale_factor)))
        
        # Refresh button
        refresh_button = tk.Button(
            center_container,
            text="🔄 Refresh Detection",
            font=button_font,
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049",
            relief="flat",
            bd=0,
            padx=int(25 * scale_factor),
            pady=int(12 * scale_factor),
            command=self.manual_refresh,
            cursor="hand2"
        )
        refresh_button.pack(pady=(int(10 * scale_factor), 0))
        
        # RIGHT COLUMN - Files List
        right_column = tk.Frame(content_frame, bg="white")
        right_column.grid(row=0, column=1, sticky="nsew")
        
        # Files section header
        files_header_frame = tk.Frame(right_column, bg="white")
        files_header_frame.pack(fill="x", pady=(0, int(10 * scale_factor)))
        
        tk.Label(
            files_header_frame,
            text="Available Files",
            font=section_font,
            bg="white",
            fg="#333333"
        ).pack(side="left")
        
        # Files count badge
        self.files_count_label = tk.Label(
            files_header_frame,
            text="0 files",
            font=("Arial", max(10, int(14 * scale_factor))),
            bg="#e0e0e0",
            fg="#666666",
            padx=int(10 * scale_factor),
            pady=int(4 * scale_factor),
            relief="flat"
        )
        self.files_count_label.pack(side="left", padx=int(10 * scale_factor))
        
        # Files list container with border
        files_container = tk.Frame(right_column, bg="#e0e0e0", bd=2, relief="solid")
        files_container.pack(fill="both", expand=True, pady=(0, int(15 * scale_factor)))
        
        # Files list frame with scrollbar
        files_list_frame = tk.Frame(files_container, bg="white")
        files_list_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        scrollbar = tk.Scrollbar(files_list_frame, bg="#f5f5f5")
        scrollbar.pack(side="right", fill="y")
        
        self.files_listbox = tk.Listbox(
            files_list_frame,
            font=base_font,
            bg="white",
            fg="#333333",
            selectmode=tk.SINGLE,
            relief="flat",
            bd=0,
            yscrollcommand=scrollbar.set,
            activestyle="none",
            selectbackground="#b42e41",
            selectforeground="white",
            highlightthickness=0
        )
        self.files_listbox.pack(side="left", fill="both", expand=True, padx=int(10 * scale_factor), pady=int(10 * scale_factor))
        self.files_listbox.bind("<<ListboxSelect>>", self._on_file_selection)
        scrollbar.config(command=self.files_listbox.yview)
        
        # No files placeholder - centered in a frame overlaying the listbox
        self.no_files_frame = tk.Frame(files_list_frame, bg="white")
        self.no_files_label = tk.Label(
            self.no_files_frame,
            text="No USB drive detected\nor no compatible files found\n\n📄 Supported: PDF, DOCX",
            font=("Arial", max(14, int(18 * scale_factor))),
            bg="white",
            fg="#999999",
            justify="center"
        )
        self.no_files_label.pack(expand=True)
        
        # Action buttons frame
        buttons_frame = tk.Frame(right_column, bg="white")
        buttons_frame.pack(fill="x", pady=(int(10 * scale_factor), 0))
        
        # Buttons row aligned to the right
        buttons_row = tk.Frame(buttons_frame, bg="white")
        buttons_row.pack(anchor="e")
        
        # Clear selection button
        clear_button = tk.Button(
            buttons_row,
            text="Clear",
            font=button_font,
            bg="#959595",
            fg="white",
            activebackground="#777777",
            relief="flat",
            bd=0,
            padx=int(30 * scale_factor),
            pady=int(12 * scale_factor),
            command=self.clear_selection,
            cursor="hand2"
        )
        clear_button.pack(side="left", padx=(0, int(12 * scale_factor)))
        
        # Transfer button
        self.transfer_button = tk.Button(
            buttons_row,
            text="Receive Selected File",
            font=button_font,
            bg="#b42e41",
            fg="white",
            activebackground="#d12246",
            relief="flat",
            bd=0,
            padx=int(35 * scale_factor),
            pady=int(12 * scale_factor),
            command=self.transfer_files,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.transfer_button.pack(side="left")
        
        # Progress label
        self.progress_label = tk.Label(
            right_column,
            text="",
            font=("Arial", max(10, int(13 * scale_factor))),
            bg="white",
            fg="#666666",
            justify="left"
        )
        self.progress_label.pack(anchor="w", pady=(int(10 * scale_factor), 0))
    
    def load_data(self, data=None):
        """Load screen data when switching to this screen."""
        print("[USBDriveScreen] Loading screen...")
        # Reset progress label when entering the screen
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text="")
        self.is_monitoring = True
        self.start_usb_monitoring()
    
    def start_usb_monitoring(self):
        """Start monitoring for USB drives in a background thread."""
        if self.usb_monitor_thread and self.usb_monitor_thread.is_alive():
            return
        
        self.usb_monitor_thread = threading.Thread(target=self._monitor_usb_drives, daemon=True)
        self.usb_monitor_thread.start()
    
    def _monitor_usb_drives(self):
        """Monitor USB drives periodically."""
        while self.is_monitoring:
            try:
                drives = self._get_removable_drives()
                self.detected_drives = drives
                self.after(0, self._update_ui_with_drives, drives)
                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"[USBDriveScreen] Error monitoring USB drives: {e}")
                time.sleep(2)
    
    def _get_removable_drives(self):
        """Get list of removable drives (USB flash drives)."""
        drives = {}
        
        if os.name == 'nt':  # Windows
            try:
                # Try using win32file for drive type detection
                try:
                    import win32file
                    for drive_letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                        drive_path = f"{drive_letter}:\\"
                        try:
                            # GetDriveType: 2 = DRIVE_REMOVABLE
                            drive_type = win32file.GetDriveType(drive_path)
                            if drive_type == 2:
                                if os.path.exists(drive_path):
                                    drives[drive_letter] = drive_path
                                    print(f"[USBDriveScreen] Detected removable drive: {drive_letter}")
                        except Exception:
                            pass
                except ImportError:
                    print("[USBDriveScreen] win32file not available, using simple detection")
                    # Simple detection - just check if drive exists
                    for drive_letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
                        drive_path = f"{drive_letter}:\\"
                        try:
                            if os.path.exists(drive_path):
                                # Try to list files to verify it's accessible
                                os.listdir(drive_path)
                                drives[drive_letter] = drive_path
                                print(f"[USBDriveScreen] Detected drive: {drive_letter}")
                        except Exception:
                            pass
            except Exception as e:
                print(f"[USBDriveScreen] Error in _get_removable_drives: {e}")
                drives = self._get_removable_drives_fallback()
        else:  # Linux/Mac
            drives = self._get_removable_drives_unix()
        
        print(f"[USBDriveScreen] Found drives: {list(drives.keys())}")
        return drives
    
    def _get_removable_drives_fallback(self):
        """Fallback method to detect USB drives without win32api."""
        drives = {}
        
        # Check all drive letters
        for drive_letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
            drive_path = f"{drive_letter}:\\"
            if os.path.exists(drive_path):
                try:
                    # Try to list directory - if successful, drive is accessible
                    os.listdir(drive_path)
                    # Assume D-Z are potential removable drives (C is usually system)
                    drives[drive_letter] = drive_path
                except PermissionError:
                    pass
                except Exception:
                    pass
        
        return drives
    
    def _get_removable_drives_unix(self):
        """Get removable drives on Unix-like systems (Linux/Mac)."""
        drives = {}
        
        common_paths = [
            '/media',
            '/mnt',
            '/Volumes'  # macOS
        ]
        
        for base_path in common_paths:
            if os.path.exists(base_path):
                try:
                    for item in os.listdir(base_path):
                        mount_path = os.path.join(base_path, item)
                        if os.path.isdir(mount_path) and os.access(mount_path, os.R_OK):
                            drives[item] = mount_path
                except Exception:
                    pass
        
        return drives
    
    def _update_ui_with_drives(self, drives):
        """Update UI to show detected drives and files."""
        if not drives:
            self.usb_detected = False
            self.status_label.config(
                text="⚠️ No USB Drive Detected",
                fg="#b42e41"
            )
            self.drive_info_label.config(text="Please insert a USB flash drive")
            # Show placeholder, clear listbox
            self.files_listbox.delete(0, tk.END)
            if hasattr(self, 'no_files_label'):
                self.no_files_label.config(text="No USB drive detected\n\n📄 Supported: PDF, DOCX")
            if hasattr(self, 'no_files_frame'):
                self.no_files_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.transfer_button.config(state=tk.DISABLED)
            self.current_files = []
            # Update files count
            if hasattr(self, 'files_count_label'):
                self.files_count_label.config(text="0 files")
            return
        
        # Found drives
        self.usb_detected = True
        drive_list = ", ".join([f"{letter}:" for letter in drives.keys()])
        self.status_label.config(
            text="✓ USB Drive Detected",
            fg="#4CAF50"
        )
        self.drive_info_label.config(text=f"Drive: {drive_list}")
        
        # Scan for files
        all_files = []
        for drive_letter, drive_path in drives.items():
            files = self._scan_drive_for_files(drive_path)
            all_files.extend(files)
        
        # Check files for viruses
        safe_files, unsafe_files = self._check_files_for_viruses(all_files)
        
        # Alert user if any unsafe files detected
        if unsafe_files:
            unsafe_list = "\n".join([f"• {f['name']}: {f['threat']}" for f in unsafe_files])
            messagebox.showwarning(
                "⚠️ Security Warning",
                f"The following potentially unsafe files were detected and blocked:\n\n{unsafe_list}\n\n"
                f"Only verified PDF and DOCX files will be available for transfer."
            )
        
        self.current_files = safe_files
        
        # Update files count badge
        if hasattr(self, 'files_count_label'):
            count = len(safe_files)
            self.files_count_label.config(
                text=f"{count} file{'s' if count != 1 else ''}",
                bg="#4CAF50" if count > 0 else "#e0e0e0",
                fg="white" if count > 0 else "#666666"
            )
        
        # Only update file list if files changed
        self._update_files_list_if_changed(safe_files)
    
    def _scan_drive_for_files(self, drive_path):
        """Recursively scan drive for PDF and DOCX files."""
        files = []
        
        try:
            for root, dirs, filenames in os.walk(drive_path):
                # Skip system folders
                dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ['system volume information', '$recycle.bin']]
                
                for filename in filenames:
                    if filename.lower().endswith(('.pdf', '.docx')):
                        full_path = os.path.join(root, filename)
                        # Get relative path for display
                        relative_path = os.path.relpath(full_path, drive_path)
                        files.append({
                            'name': filename,
                            'full_path': full_path,
                            'display': relative_path,
                            'drive': os.path.splitdrive(drive_path)[0]
                        })
        except PermissionError:
            print(f"[USBDriveScreen] Permission denied scanning {drive_path}")
        except Exception as e:
            print(f"[USBDriveScreen] Error scanning {drive_path}: {e}")
        
        return files
    
    def _update_files_list_if_changed(self, files):
        """Update the files listbox only if files have changed."""
        # Get current listbox contents
        current_items = list(self.files_listbox.get(0, tk.END)) if self.files_listbox.size() > 0 else []
        new_items = [f"{f['display']} ({f['drive']})" for f in files] if files else []
        
        # Only update if files changed
        if current_items != new_items:
            current_selection = self.files_listbox.curselection()
            self.files_listbox.delete(0, tk.END)
            
            if not files:
                # Show centered placeholder for "No files found"
                if hasattr(self, 'no_files_label'):
                    self.no_files_label.config(text="No PDF or DOCX files found on USB drive\n\n📄 Supported: PDF, DOCX")
                if hasattr(self, 'no_files_frame'):
                    self.no_files_frame.place(relx=0.5, rely=0.5, anchor="center")
                self.transfer_button.config(state=tk.DISABLED)
            else:
                # Hide placeholder when files exist
                if hasattr(self, 'no_files_frame'):
                    self.no_files_frame.place_forget()
                for i, file_info in enumerate(files):
                    display_text = f"{file_info['display']} ({file_info['drive']})"
                    self.files_listbox.insert(i, display_text)
                # Keep selection disabled until user selects again
                if not current_selection:
                    self.transfer_button.config(state=tk.DISABLED)
    
    def _update_files_list(self, files):
        """Update the files listbox with available files."""
        self.files_listbox.delete(0, tk.END)
        self.selected_files = []
        
        if not files:
            # Show centered placeholder
            if hasattr(self, 'no_files_label'):
                self.no_files_label.config(text="No PDF or DOCX files found on USB drive\n\n📄 Supported: PDF, DOCX")
            if hasattr(self, 'no_files_frame'):
                self.no_files_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.transfer_button.config(state=tk.DISABLED)
        else:
            # Hide placeholder when files exist
            if hasattr(self, 'no_files_frame'):
                self.no_files_frame.place_forget()
            for i, file_info in enumerate(files):
                display_text = f"{file_info['display']} ({file_info['drive']})"
                self.files_listbox.insert(i, display_text)
            self.transfer_button.config(state=tk.NORMAL)
    
    def clear_selection(self):
        """Clear all selected files."""
        self.files_listbox.selection_clear(0, tk.END)
        self.selected_files = []
        self.transfer_button.config(state=tk.DISABLED if not self.current_files else tk.NORMAL)
        self.progress_label.config(text="")
    
    def _on_file_selection(self, event=None):
        """Handle file selection in the listbox."""
        selection = self.files_listbox.curselection()
        if selection:
            self.transfer_button.config(state=tk.NORMAL)
        else:
            self.transfer_button.config(state=tk.DISABLED)
    
    def transfer_files(self):
        """Transfer selected files from USB drive."""
        selection = self.files_listbox.curselection()
        
        if not selection:
            messagebox.showwarning("No Selection", "Please select a file to transfer.")
            return
        
        # Get selected files
        selected_files = [self.current_files[i] for i in selection]
        self.selected_files = selected_files
        
        # Disable button during transfer
        self.transfer_button.config(state=tk.DISABLED)
        self.progress_label.config(text="Preparing transfer...")
        self.update_idletasks()
        
        # Transfer in a background thread
        transfer_thread = threading.Thread(
            target=self._perform_file_transfer,
            args=(selected_files,),
            daemon=True
        )
        transfer_thread.start()
    
    def _perform_file_transfer(self, files):
        """Perform the actual file transfer."""
        try:
            # Create a temporary directory for the files
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'usb_transfers')
            os.makedirs(temp_dir, exist_ok=True)
            
            transferred_files = []
            total = len(files)
            
            for idx, file_info in enumerate(files):
                try:
                    source_path = file_info['full_path']
                    filename = file_info['name']
                    dest_path = os.path.join(temp_dir, filename)
                    
                    # Handle duplicate filenames
                    counter = 1
                    name, ext = os.path.splitext(filename)
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(temp_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    # Update progress
                    progress_text = f"Transferring file {idx + 1} of {total}: {filename}..."
                    self.after(0, self.progress_label.config, {'text': progress_text})
                    self.after(0, self.update_idletasks)
                    
                    # Copy file
                    shutil.copy2(source_path, dest_path)
                    transferred_files.append({
                        'original_name': filename,
                        'temp_path': dest_path
                    })
                    
                    print(f"[USBDriveScreen] Transferred: {filename}")
                    
                except Exception as e:
                    print(f"[USBDriveScreen] Error transferring {file_info['name']}: {e}")
                    self.after(0, lambda: messagebox.showerror(
                        "Transfer Error",
                        f"Error transferring {file_info['name']}: {str(e)}"
                    ))
            
            if transferred_files:
                # Update progress
                self.after(0, self.progress_label.config, {
                    'text': f"✓ Successfully transferred {len(transferred_files)} file(s). Processing..."
                })
                self.after(0, self.update_idletasks)
                
                # Store in controller for next screen
                self.controller.usb_files = transferred_files
                
                # Wait a moment for user to see the success message
                time.sleep(1.5)
                
                # Navigate to options screen with the first file
                self.after(0, self._proceed_to_options, transferred_files)
            else:
                self.after(0, lambda: messagebox.showerror(
                    "Transfer Failed",
                    "No files were successfully transferred."
                ))
                self.after(0, self._reset_transfer_ui)
        
        except Exception as e:
            print(f"[USBDriveScreen] Transfer error: {e}")
            self.after(0, lambda: messagebox.showerror(
                "Transfer Error",
                f"Error during file transfer: {str(e)}"
            ))
            self.after(0, self._reset_transfer_ui)
    
    def _proceed_to_options(self, transferred_files):
        """Proceed to options screen with transferred files and save to Firebase."""
        try:
            # Save first file to Firebase
            first_file = transferred_files[0]
            file_path = first_file['temp_path']
            file_name = first_file['original_name']
            
            # Save to Firebase to create a job entry visible in web app
            job_data = save_file_to_firebase(file_path, file_name)
            
            if job_data:
                print(f"[USBDriveScreen] File saved to Firebase with job ID: {job_data.get('job_id')}")
                # Add USB source identifier
                job_data['upload_source'] = 'usb_drive'
                job_data['all_files'] = transferred_files
                
                # Navigate to OptionsScreen
                self.controller.show_frame("OptionsScreen", data=job_data)
            else:
                messagebox.showerror(
                    "Firebase Error",
                    "Failed to save file information to database.\nPlease try again."
                )
                self._reset_transfer_ui()
        
        except Exception as e:
            print(f"[USBDriveScreen] Error proceeding to options: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Error processing file: {str(e)}")
            self._reset_transfer_ui()
    
    def _reset_transfer_ui(self):
        """Reset the transfer UI after transfer completion or error."""
        self.transfer_button.config(state=tk.NORMAL if self.current_files else tk.DISABLED)
        self.progress_label.config(text="")
    
    def go_back(self):
        """Go back to home screen."""
        self.is_monitoring = False
        self.controller.show_frame("HomeScreen")
    
    def on_screen_hide(self):
        """Called when screen is hidden."""
        self.is_monitoring = False
        if self.usb_monitor_thread:
            self.usb_monitor_thread.join(timeout=1)
    
    def manual_refresh(self):
        """Manually refresh USB drive detection."""
        if self.scan_in_progress:
            messagebox.showinfo("Scanning", "USB scan already in progress, please wait...")
            return
        
        self.scan_in_progress = True
        self.progress_label.config(text="⏳ Refreshing USB drive detection...")
        self.update_idletasks()
        
        # Run refresh in background thread
        refresh_thread = threading.Thread(target=self._do_refresh, daemon=True)
        refresh_thread.start()
    
    def _do_refresh(self):
        """Perform refresh operation in background."""
        try:
            time.sleep(0.5)
            drives = self._get_removable_drives()
            self.detected_drives = drives
            self.after(0, self._update_ui_with_drives, drives)
            self.after(0, lambda: self.progress_label.config(text=""))
        except Exception as e:
            print(f"[USBDriveScreen] Error during refresh: {e}")
            self.after(0, lambda: messagebox.showerror("Refresh Error", f"Error refreshing drives: {str(e)}"))
        finally:
            self.scan_in_progress = False
    
    def _scan_file_for_virus(self, file_path):
        """
        Scan file for potential threats.
        Returns: (is_safe: bool, threat_type: str or None)
        """
        try:
            filename = os.path.basename(file_path).lower()
            
            # Check 1: File extension blacklist
            for suspicious_ext in self.SUSPICIOUS_PATTERNS:
                if filename.endswith(suspicious_ext):
                    return (False, f"Suspicious file type: {suspicious_ext}")
            
            # Check 2: File size (extremely large files might be suspicious)
            file_size = os.path.getsize(file_path)
            if file_size > 500 * 1024 * 1024:  # 500 MB
                return (False, "File size exceeds safe limit (500 MB)")
            
            # Check 3: Hash-based detection (signature database)
            if self.virus_detection_enabled:
                try:
                    file_hash = self._calculate_file_hash(file_path)
                    if file_hash in self.VIRUS_SIGNATURES:
                        return (False, f"Known malware detected: {self.VIRUS_SIGNATURES[file_hash]}")
                except Exception as e:
                    print(f"[USBDriveScreen] Hash calculation error: {e}")
            
            # Check 4: Check for suspicious patterns in filename
            suspicious_keywords = ['virus', 'malware', 'trojan', 'ransomware', 'worm']
            if any(keyword in filename for keyword in suspicious_keywords):
                return (False, "Suspicious filename detected")
            
            return (True, None)
            
        except Exception as e:
            print(f"[USBDriveScreen] Virus scan error: {e}")
            return (True, None)  # Default to safe on error
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of file for virus signature checking."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _check_files_for_viruses(self, files):
        """
        Check multiple files for viruses.
        Returns: (safe_files: list, unsafe_files: list)
        """
        safe_files = []
        unsafe_files = []
        
        for file_info in files:
            is_safe, threat = self._scan_file_for_virus(file_info['full_path'])
            if is_safe:
                safe_files.append(file_info)
            else:
                unsafe_files.append({
                    'name': file_info['name'],
                    'threat': threat
                })
        
        return safe_files, unsafe_files

