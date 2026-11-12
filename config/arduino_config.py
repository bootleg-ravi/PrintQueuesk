"""
Arduino Coin and Bill Acceptor Configuration and Communication
This module handles serial communication with the Arduino coin and bill acceptor.
Supports coin acceptor (D2), bill acceptor (D4), DC motors (D3,D5,D6,D9,D10,D11), and coin hoppers (D7,D8,D12,D13).
"""

import serial
import serial.tools.list_ports
import threading
import time


class ArduinoCoinAcceptor:
    def __init__(self, port=None, baudrate=9600, timeout=1):
        self.port = port or self.auto_detect_port()
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.last_coin = None
        self.total = 0
        self._stop_event = threading.Event()
        self._thread = None
        self.payment_complete = False
        self.serial_lock = threading.Lock()  # Lock for serial port access to prevent race conditions
        self.required_payment = 0  # Dynamic payment amount
        self.change_dispensing = False  # Flag to track if change is being dispensed
        self.change_dispensed_callback = None  # Callback when change dispensing completes
        self._stop_event = threading.Event()
        self._thread = None
        self.payment_complete = False
        self.serial_lock = threading.Lock()  # Added for compatibility/thread safety
        self.required_payment = 0  # Dynamic payment amount
        self.change_dispensing = False  # Flag to track if change is being dispensed
        self.change_dispensed_callback = None  # Callback when change dispensing completes

    def process_coin(self, coin_value, total_price):
        """
        Process a coin value: increment total, check if payment is complete, and return status.
        Returns: (total_amount, remaining, payment_complete)
        """
        if self.payment_complete:
            return self.total, max(0, total_price - self.total), True
        if isinstance(coin_value, (int, float)) and coin_value > 0:
            self.total += coin_value
        remaining = max(0, total_price - self.total)
        if self.total >= total_price:
            self.payment_complete = True
            self.required_payment = total_price  # Store for change calculation
        return self.total, remaining, self.payment_complete

    @staticmethod
    def auto_detect_port():
        """
        Auto-detects the Arduino COM port by looking for common Arduino USB serial descriptions.
        Returns the port name (e.g., 'COM4') or None if not found.
        Prints all available ports for debugging.
        """
        try:
            ports = serial.tools.list_ports.comports()
            print("[Arduino] Available serial ports:")
            for port in ports:
                print(f"  {port.device}: {port.description}")
            for port in ports:
                desc = port.description.lower()
                # Common Arduino Uno descriptors
                if ('arduino uno' in desc) or ('arduino' in desc) or ('ch340' in desc) or ('usb serial device' in desc):
                    print(f"[Arduino] Auto-detected port: {port.device} ({port.description})")
                    return port.device
            # Fallback: return first available port
            if ports:
                print(f"[Arduino] Fallback to first port: {ports[0].device} ({ports[0].description})")
                return ports[0].device
            print("[Arduino] No Arduino port found.")
        except Exception as e:
            print(f"[Arduino] Port auto-detect error: {e}")
        return None
    
    def connect(self):
        if not self.port:
            self.port = self.auto_detect_port()
        if not self.port:
            print("[Arduino] No COM port found for Arduino.")
            return False
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(2)  # Wait for Arduino to reset
            print(f"[Arduino] Connected to {self.port}")
            return True
        except serial.SerialException as e:
            print(f"[Arduino] Serial connection error: {e}")
            return False

    def start_listening(self, callback=None):
        if not self.ser:
            if not self.connect():
                return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen, args=(callback,))
        self._thread.daemon = True
        self._thread.start()
        return True

    def _listen(self, callback):
        while not self._stop_event.is_set():
            try:
                with self.serial_lock:  # Thread-safe serial read
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('utf-8').strip()
                    else:
                        line = None
                
                if line:
                    print(f"[Arduino] Received: {line}")  # Debug: show every line from Arduino
                    
                    # Check for payment completion signal
                    if "[PAYMENT_COMPLETE]" in line:
                        print("[Arduino] Payment complete signal received from Arduino")
                        # The Python side will handle this through the total check
                        continue
                    
                    # STOP processing coins if payment is complete or change is being dispensed
                    if self.payment_complete or self.change_dispensing:
                        print(f"[Arduino] Ignoring coin input - payment_complete={self.payment_complete}, change_dispensing={self.change_dispensing}")
                        continue
                    
                    # Process coin/bill insertions only if payment not complete
                    coin_value = self._process_arduino_line(line)
                    if coin_value:
                        self.last_coin = coin_value
                        if callback:
                            callback(coin_value, None)  # GUI will handle total
            except Exception as e:
                print(f"[Arduino] Read error: {e}")
            time.sleep(0.1)

    def _process_arduino_line(self, line):
        """
        Process a line from Arduino serial output.
        Returns the coin/bill value sent by Arduino, or None if not valid.
        Supports both formats:
        - [COIN] Inserted: PHP 5 (5 pulses)
        - [BILL] Inserted: PHP 20 (2 pulses)
        """
        # Check for new format with [COIN] or [BILL] prefix
        if ('[COIN]' in line or '[BILL]' in line) and 'Inserted: PHP' in line:
            try:
                # Extract the value between "PHP" and the opening parenthesis
                # Example: "[COIN] Inserted: PHP 5 (5 pulses)"
                parts = line.split('PHP')
                if len(parts) > 1:
                    value_part = parts[1].strip().split('(')[0].strip()
                    value = int(value_part)
                    return value
            except Exception as e:
                print(f"[Arduino] Parse error: {e}")
                return None
        
        # Fallback: check for old format (backward compatibility)
        if line.startswith('Inserted: PHP'):
            try:
                parts = line.split()
                value = int(parts[2])
                return value
            except Exception:
                return None
        
        # Ignore other Arduino messages (like "Total: PHP X")
        return None

    def stop_listening(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def dispense_change(self, callback=None):
        """
        Dispense change based on total paid vs required payment.
        Sends a command to Arduino to dispense the exact change amount.
        Returns the change amount dispensed.
        Callback is called when dispensing completes with (success, amount_dispensed, message)
        """
        if not self.ser or not self.ser.is_open:
            print("[Arduino] Serial port not open. Cannot dispense change.")
            if callback:
                callback(False, 0, "Serial port not open")
            return 0
        
        if self.required_payment <= 0:
            print("[Arduino] No required payment set. Cannot calculate change.")
            if callback:
                callback(False, 0, "No required payment set")
            return 0
        
        change_amount = int(self.total - self.required_payment)
        
        if change_amount <= 0:
            print("[Arduino] No change to dispense (exact payment or underpayment).")
            if callback:
                callback(True, 0, "No change needed")
            return 0
        
        print(f"[Arduino] Dispensing change: PHP {change_amount}")
        self.change_dispensing = True
        self.change_dispensed_callback = callback
        
        # Send dispense command to Arduino
        try:
            command = f"DISPENSE:{change_amount}\n"
            with self.serial_lock:  # Thread-safe serial write
                self.ser.write(command.encode('utf-8'))
            print(f"[Arduino] Sent command: {command.strip()}")
            
            # Start a thread to monitor the dispensing process
            monitor_thread = threading.Thread(target=self._monitor_change_dispensing, args=(change_amount,))
            monitor_thread.daemon = True
            monitor_thread.start()
            
            return change_amount
        except Exception as e:
            print(f"[Arduino] Error sending dispense command: {e}")
            self.change_dispensing = False
            if callback:
                callback(False, 0, f"Error: {e}")
            return 0

    def _monitor_change_dispensing(self, expected_amount):
        """
        Monitor serial output for change dispensing completion.
        Looks for messages like "[CHANGE_COMPLETE]" or "[CHANGE_ERROR]"
        Automatically sends RESET command after change dispensing completes.
        If hopper is running for 3 seconds without detecting a coin, it will stop the hopper.
        """
        timeout = 60  # 60 second timeout for change dispensing
        start_time = time.time()
        last_coin_time = time.time()  # Track last coin detection time
        coin_timeout = 3  # Stop hopper if no coin detected in 3 seconds
        hopper_running = False  # Track if hopper is currently running
        
        while self.change_dispensing and (time.time() - start_time) < timeout:
            try:
                with self.serial_lock:  # Thread-safe serial read
                    if self.ser.in_waiting:
                        line = self.ser.readline().decode('utf-8').strip()
                    else:
                        line = None
                
                if line:
                    print(f"[Arduino Change Monitor] {line}")
                    
                    # Track when hopper starts running (coin value detected)
                    if "COIN_DETECTED" in line or "1" in line or "5" in line:
                        hopper_running = True
                        last_coin_time = time.time()
                        print(f"[Arduino] Hopper started - coin detected, timer reset")
                    
                    # Check for completion or error messages
                    if "[CHANGE_COMPLETE]" in line:
                        print(f"[Arduino] Change dispensing completed successfully!")
                        self.change_dispensing = False
                        hopper_running = False
                        # Send RESET command to Arduino to prepare for next transaction
                        self._send_reset_command()
                        if self.change_dispensed_callback:
                            self.change_dispensed_callback(True, expected_amount, "Change dispensed successfully")
                        return
                    elif "[CHANGE_ERROR]" in line:
                        print(f"[Arduino] Change dispensing error!")
                        self.change_dispensing = False
                        hopper_running = False
                        # Still send RESET to clean up state even on error
                        self._send_reset_command()
                        if self.change_dispensed_callback:
                            self.change_dispensed_callback(False, 0, "Change dispensing error")
                        return
                    elif "[CHANGE_TIMEOUT]" in line:
                        print(f"[Arduino] Change dispensing timeout!")
                        self.change_dispensing = False
                        hopper_running = False
                        # Send RESET to recover from timeout
                        self._send_reset_command()
                        if self.change_dispensed_callback:
                            self.change_dispensed_callback(False, 0, "Change dispensing timeout")
                        return
                
                # Check if hopper has been running for more than 5 seconds without coin detection
                if hopper_running and (time.time() - last_coin_time) > coin_timeout:
                    print(f"[Arduino] No coin detected for {coin_timeout} seconds - STOPPING HOPPER!")
                    hopper_running = False
                    # Send STOP command to Arduino to stop the hopper
                    try:
                        stop_command = "STOP_HOPPER\n"
                        with self.serial_lock:
                            self.ser.write(stop_command.encode('utf-8'))
                        print(f"[Arduino] Sent STOP_HOPPER command")
                    except Exception as e:
                        print(f"[Arduino] Error sending STOP_HOPPER command: {e}")
                    
            except Exception as e:
                print(f"[Arduino] Change monitor error: {e}")
            
            time.sleep(0.1)
        
        # Timeout reached
        if self.change_dispensing:
            print(f"[Arduino] Change dispensing monitor timeout after {timeout}s")
            self.change_dispensing = False
            # Send RESET even on monitor timeout
            self._send_reset_command()
            if self.change_dispensed_callback:
                self.change_dispensed_callback(False, 0, "Monitor timeout")

    def _send_reset_command(self):
        """Send RESET command to Arduino to clear state for next transaction"""
        try:
            if self.ser and self.ser.is_open:
                time.sleep(0.5)  # Brief delay before sending reset
                command = "RESET\n"
                with self.serial_lock:  # Thread-safe serial write
                    self.ser.write(command.encode('utf-8'))
                print(f"[Arduino] Sent RESET command for next transaction")
        except Exception as e:
            print(f"[Arduino] Error sending RESET command: {e}")

    def set_required_payment(self, amount):
        """
        Set the required payment amount dynamically.
        This is used to calculate change.
        """
        self.required_payment = float(amount)
        print(f"[Arduino] Required payment set to: PHP {self.required_payment}")
        
        # Also send to Arduino so it knows when payment is complete
        if self.ser and self.ser.is_open:
            try:
                command = f"SET_PAYMENT:{int(amount)}\n"
                with self.serial_lock:  # Thread-safe serial write
                    self.ser.write(command.encode('utf-8'))
                print(f"[Arduino] Sent command: {command.strip()}")
            except Exception as e:
                print(f"[Arduino] Error sending payment amount: {e}")

    def reset_payment(self):
        """
        Reset payment tracking for a new transaction.
        """
        self.total = 0
        self.required_payment = 0
        self.payment_complete = False
        self.change_dispensing = False
        self.change_dispensed_callback = None
        print("[Arduino] Payment tracking reset for new transaction")

    def close(self):
        self.stop_listening()
        if self.ser:
            self.ser.close()
            self.ser = None
