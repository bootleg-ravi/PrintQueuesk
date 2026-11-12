// Combined Coin and Bill Acceptor Counter with Change Hopper for Arduino Uno
// MEMORY OPTIMIZED VERSION - Uses simple pulse counting instead of timestamp arrays
// Coin acceptor connected to D2
// Bill acceptor (TB74-PH60Ni) connected to D3

// ========== COIN/BILL ACCEPTOR CONFIGURATION ==========
const byte coinPulsePin = 2;
const byte billPulsePin = 3;
volatile byte coinPulseCount = 0;
volatile byte billPulseCount = 0;
volatile unsigned long lastCoinPulseTime = 0;
volatile unsigned long lastBillPulseTime = 0;

// ========== COIN HOPPER CONFIGURATION A (1 Peso) ==========
const byte COIN_HOPPER_PIN_A = 7;
const byte RELAY_PIN_A = 8;
const byte COIN_VALUE_A = 1;
volatile unsigned int hopperCoinCountA = 0;
volatile unsigned int targetCoinCountA = 0;
unsigned long lastCoinTimeA = 0;

// ========== COIN HOPPER CONFIGURATION B (5 Peso) ==========
const byte COIN_HOPPER_PIN_B = 9;
const byte RELAY_PIN_B = 10;
const byte COIN_VALUE_B = 5;
volatile unsigned int hopperCoinCountB = 0;
volatile unsigned int targetCoinCountB = 0;
unsigned long lastCoinTimeB = 0;

// Signal stability
const byte minCoinInterval = 50;

// ========== PAYMENT SYSTEM CONFIGURATION ==========
int REQUIRED_PAYMENT = 0;
int totalPesos = 0;
int changeToDispense = 0;
bool paymentSet = false;
bool paymentProcessed = false;  // Track if payment has been processed
char inputBuffer[32];  // Fixed size buffer instead of String
byte bufferIndex = 0;

void setup() {
  Serial.begin(9600);
  
  pinMode(coinPulsePin, INPUT_PULLUP);  
  attachInterrupt(digitalPinToInterrupt(coinPulsePin), countCoinPulse, FALLING);
  
  pinMode(billPulsePin, INPUT_PULLUP);  
  attachInterrupt(digitalPinToInterrupt(billPulsePin), countBillPulse, FALLING);
  
  pinMode(COIN_HOPPER_PIN_A, INPUT_PULLUP);
  pinMode(RELAY_PIN_A, OUTPUT);
  digitalWrite(RELAY_PIN_A, HIGH);
  
  pinMode(COIN_HOPPER_PIN_B, INPUT_PULLUP);
  pinMode(RELAY_PIN_B, OUTPUT);
  digitalWrite(RELAY_PIN_B, HIGH);
  
  delay(1000);
  
  Serial.println(F("==========================================="));
  Serial.println(F("Payment System with Change Hopper Ready"));
  Serial.println(F("==========================================="));
  Serial.println(F("Coin Acceptor: D2"));
  Serial.println(F("Bill Acceptor: D3"));
  Serial.println(F("Coin Hopper A: D8 (Relay) / D7 (Sensor) - PHP 1"));
  Serial.println(F("Coin Hopper B: D10 (Relay) / D9 (Sensor) - PHP 5"));
  Serial.println(F("==========================================="));
  Serial.println(F("\nWaiting for payment amount from computer..."));
  Serial.println(F("Commands: SET_PAYMENT:<amount>, DISPENSE:<amount>"));
}

void loop() {
  // Check for serial commands
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (bufferIndex > 0) {
        inputBuffer[bufferIndex] = '\0';
        processCommand(inputBuffer);
        bufferIndex = 0;
      }
    } else if (bufferIndex < 31) {
      inputBuffer[bufferIndex++] = c;
    }
  }
  
  // Check for completed coin (no pulses for 500ms)
  if (coinPulseCount > 0 && (millis() - lastCoinPulseTime > 500)) {
    analyzeCoin();
  }
  
  // Check for completed bill (no pulses for 800ms)
  if (billPulseCount > 0 && (millis() - lastBillPulseTime > 800)) {
    analyzeBill();
  }
  
  // Check if payment is sufficient - ONLY process once per transaction
  if (paymentSet && REQUIRED_PAYMENT > 0 && totalPesos >= REQUIRED_PAYMENT && !paymentProcessed) {
    paymentProcessed = true;
    processPayment();
    // paymentProcessed stays true until RESET command is received
  }
}

// ========== SERIAL COMMAND PROCESSING ==========

void processCommand(char* cmd) {
  Serial.print(F("[CMD] Received: "));
  Serial.println(cmd);
  
  // SET_PAYMENT command
  if (strncmp(cmd, "SET_PAYMENT:", 12) == 0) {
    int amount = atoi(cmd + 12);
    if (amount > 0) {
      REQUIRED_PAYMENT = amount;
      paymentSet = true;
      Serial.print(F("[CMD] Payment amount set to: PHP "));
      Serial.println(REQUIRED_PAYMENT);
      Serial.println(F("[CMD] Ready to accept payment. Please insert bills/coins..."));
    } else {
      Serial.println(F("[CMD] ERROR: Invalid payment amount"));
    }
  }
  // DISPENSE command
  else if (strncmp(cmd, "DISPENSE:", 9) == 0) {
    int amount = atoi(cmd + 9);
    if (amount > 0) {
      Serial.print(F("[CMD] Manual dispense request: PHP "));
      Serial.println(amount);
      dispenseChange(amount);
    } else {
      Serial.println(F("[CMD] ERROR: Invalid dispense amount"));
    }
  }
  // STOP_HOPPER command
  else if (strcmp(cmd, "STOP_HOPPER") == 0) {
    Serial.println(F("[CMD] STOP_HOPPER command received"));
    digitalWrite(RELAY_PIN_A, HIGH);
    digitalWrite(RELAY_PIN_B, HIGH);
    Serial.println(F("[CMD] Both hoppers stopped"));
  }
  // RESET command
  else if (strcmp(cmd, "RESET") == 0) {
    REQUIRED_PAYMENT = 0;
    totalPesos = 0;
    changeToDispense = 0;
    paymentSet = false;
    paymentProcessed = false;  // Reset the payment processed flag
    coinPulseCount = 0;
    billPulseCount = 0;
    // Ensure hoppers are stopped
    digitalWrite(RELAY_PIN_A, HIGH);
    digitalWrite(RELAY_PIN_B, HIGH);
    Serial.println(F("[CMD] System reset. All state cleared. Waiting for new payment amount..."));
  }
  else {
    Serial.print(F("[CMD] ERROR: Unknown command: "));
    Serial.println(cmd);
  }
}

// ========== COIN ACCEPTOR FUNCTIONS ==========

void analyzeCoin() {
  int coinValue = mapCoin(coinPulseCount);
  
  if (coinValue > 0) {
    totalPesos += coinValue;
    Serial.print(F("[COIN] Inserted: PHP "));
    Serial.print(coinValue);
    Serial.print(F(" ("));
    Serial.print(coinPulseCount);
    Serial.println(F(" pulses)"));
    Serial.print(F("Total: PHP "));
    Serial.println(totalPesos);
  } else {
    Serial.print(F("[COIN] Unknown coin (pulses = "));
    Serial.print(coinPulseCount);
    Serial.println(F(")"));
  }
  
  coinPulseCount = 0;
}

void countCoinPulse() {
  unsigned long currentTime = millis();
  if (currentTime - lastCoinPulseTime > 50) {
    if (coinPulseCount < 20) {
      coinPulseCount++;
    }
    lastCoinPulseTime = currentTime;
  }
}

int mapCoin(byte pulses) {
  switch (pulses) {
    case 1: return 1;
    case 5: return 5;
    case 10: return 10;
    case 20: return 20;
    default: return 0;
  }
}

// ========== BILL ACCEPTOR FUNCTIONS ==========

void analyzeBill() {
  int billValue = mapBill(billPulseCount);
  
  if (billValue > 0) {
    totalPesos += billValue;
    Serial.print(F("[BILL] Inserted: PHP "));
    Serial.print(billValue);
    Serial.print(F(" ("));
    Serial.print(billPulseCount);
    Serial.println(F(" pulses)"));
    Serial.print(F("Total: PHP "));
    Serial.println(totalPesos);
  } else {
    Serial.print(F("[BILL] Unknown bill (pulses = "));
    Serial.print(billPulseCount);
    Serial.println(F(")"));
  }
  
  billPulseCount = 0;
}

void countBillPulse() {
  unsigned long currentTime = millis();
  if (currentTime - lastBillPulseTime > 80) {
    if (billPulseCount < 60) {
      billPulseCount++;
    }
    lastBillPulseTime = currentTime;
  }
}

int mapBill(byte pulses) {
  switch (pulses) {
    case 2: return 20;
    case 5: return 50;   // Fixed: Your hardware sends 5 pulses for 50 pesos
    case 10: return 100;
    case 20: return 200;
    case 50: return 500;
    default: return 0;
  }
}

// ========== PAYMENT PROCESSING ==========

void processPayment() {
  Serial.println(F("\n==========================================="));
  Serial.println(F("[PAYMENT_COMPLETE]"));
  Serial.println(F("==========================================="));
  Serial.print(F("Required Payment: PHP "));
  Serial.println(REQUIRED_PAYMENT);
  Serial.print(F("Amount Received: PHP "));
  Serial.println(totalPesos);
  
  changeToDispense = totalPesos - REQUIRED_PAYMENT;
  Serial.print(F("Change to Return: PHP "));
  Serial.println(changeToDispense);
  
  if (changeToDispense > 0) {
    Serial.println(F("\n[WAITING_FOR_DISPENSE_COMMAND]"));
    Serial.println(F("Waiting for Python to send DISPENSE command..."));
  } else {
    Serial.println(F("\nExact payment received. No change needed."));
    Serial.println(F("[NO_CHANGE_NEEDED]"));
  }
  
  Serial.println(F("==========================================="));
}

// ========== COIN HOPPER FUNCTIONS ==========

void dispenseChange(int changeAmount) {
  Serial.println(F("\n==========================================="));
  Serial.println(F("[CHANGE_DISPENSING_START]"));
  Serial.print(F("Total change to dispense: PHP "));
  Serial.println(changeAmount);
  
  int fivePesoCoins = changeAmount / COIN_VALUE_B;
  int onePesoCoins = changeAmount % COIN_VALUE_B;
  
  Serial.println(F("Change breakdown:"));
  if (fivePesoCoins > 0) {
    Serial.print(F("  - "));
    Serial.print(fivePesoCoins);
    Serial.print(F(" x PHP 5 = PHP "));
    Serial.println(fivePesoCoins * COIN_VALUE_B);
  }
  if (onePesoCoins > 0) {
    Serial.print(F("  - "));
    Serial.print(onePesoCoins);
    Serial.print(F(" x PHP 1 = PHP "));
    Serial.println(onePesoCoins * COIN_VALUE_A);
  }
  Serial.println();
  
  int actualFivePesoCoins = 0;
  int actualOnePesoCoins = 0;
  
  if (fivePesoCoins > 0) {
    Serial.print(F("[PRIMARY] Dispensing "));
    Serial.print(fivePesoCoins);
    Serial.print(F(" x PHP "));
    Serial.print(COIN_VALUE_B);
    Serial.println(F(" coins from Hopper B..."));
    actualFivePesoCoins = dispenseFromHopperB(fivePesoCoins);
  }
  
  if (onePesoCoins > 0) {
    Serial.print(F("[SECONDARY] Dispensing "));
    Serial.print(onePesoCoins);
    Serial.print(F(" x PHP "));
    Serial.print(COIN_VALUE_A);
    Serial.println(F(" coins from Hopper A..."));
    actualOnePesoCoins = dispenseFromHopperA(onePesoCoins);
  }
  
  int totalDispensed = (actualFivePesoCoins * COIN_VALUE_B) + (actualOnePesoCoins * COIN_VALUE_A);
  Serial.println();
  Serial.print(F("Total dispensed: PHP "));
  Serial.print(totalDispensed);
  Serial.print(F(" ("));
  if (actualFivePesoCoins > 0) {
    Serial.print(actualFivePesoCoins);
    Serial.print(F(" x PHP5"));
  }
  if (actualOnePesoCoins > 0) {
    if (actualFivePesoCoins > 0) Serial.print(F(" + "));
    Serial.print(actualOnePesoCoins);
    Serial.print(F(" x PHP1"));
  }
  Serial.println(F(")"));
  
  if (totalDispensed == changeAmount) {
    Serial.println(F("[CHANGE_COMPLETE]"));
    Serial.println(F("Change dispensing successful!"));
  } else {
    Serial.println(F("[CHANGE_ERROR]"));
    Serial.print(F("ERROR: Expected "));
    Serial.print(changeAmount);
    Serial.print(F(" but dispensed "));
    Serial.println(totalDispensed);
  }
  Serial.println(F("===========================================\n"));
  
  // RESET SYSTEM STATE AFTER CHANGE DISPENSING
  Serial.println(F("[AUTO_RESET] Resetting system for next transaction..."));
  REQUIRED_PAYMENT = 0;
  totalPesos = 0;
  changeToDispense = 0;
  paymentSet = false;
  coinPulseCount = 0;
  billPulseCount = 0;
  Serial.println(F("[AUTO_RESET] System ready for next payment. Waiting for new payment amount..."));
}

int dispenseFromHopperA(int coinsToDispense) {
  if (coinsToDispense <= 0) {
    Serial.println(F("  Hopper A: No coins to dispense"));
    return 0;
  }
  
  noInterrupts();
  hopperCoinCountA = 0;
  targetCoinCountA = coinsToDispense;
  lastCoinTimeA = millis();
  interrupts();
  
  digitalWrite(RELAY_PIN_A, LOW);
  Serial.print(F("  Hopper A motor started, target: "));
  Serial.print(coinsToDispense);
  Serial.println(F(" coins"));
  
  unsigned long startTime = millis();
  unsigned long timeout = 30000;
  unsigned long lastCoinDetected = millis();
  
  // Keep motor running until we reach exact target
  while (hopperCoinCountA < coinsToDispense) {
    if (millis() - startTime > timeout) {
      Serial.println(F("  WARNING: Hopper A timeout!"));
      break;
    }
    
    // Check for coin detection
    int prevCount = hopperCoinCountA;
    checkForHopperCoinA();
    
    // If coin was detected, update timestamp
    if (hopperCoinCountA > prevCount) {
      lastCoinDetected = millis();
    }
    
    // Safety: if no coin for 3 seconds, stop motor (don't wait for at least 1 coin)
    if (millis() - lastCoinDetected > 3000) {
      Serial.println(F("  WARNING: No coins detected for 3s - STOPPING HOPPER A!"));
      digitalWrite(RELAY_PIN_A, HIGH);
      delay(100);
      break;
    }
    
    delay(1); // Small delay to prevent tight loop
  }
  
  digitalWrite(RELAY_PIN_A, HIGH);
  Serial.println(F("  Hopper A motor stopped"));
  
  delay(200); // Allow motor to fully stop
  
  Serial.print(F("  Hopper A dispensed "));
  Serial.print(hopperCoinCountA);
  Serial.print(F(" x PHP "));
  Serial.print(COIN_VALUE_A);
  Serial.println(F(" coins"));
  
  return hopperCoinCountA;
}

int dispenseFromHopperB(int coinsToDispense) {
  if (coinsToDispense <= 0) {
    Serial.println(F("  Hopper B: No coins to dispense"));
    return 0;
  }
  
  noInterrupts();
  hopperCoinCountB = 0;
  targetCoinCountB = coinsToDispense;
  lastCoinTimeB = millis();
  interrupts();
  
  digitalWrite(RELAY_PIN_B, LOW);
  Serial.print(F("  Hopper B motor started, target: "));
  Serial.print(coinsToDispense);
  Serial.println(F(" coins"));
  
  unsigned long startTime = millis();
  unsigned long timeout = 30000;
  unsigned long lastCoinDetected = millis();
  
  // Keep motor running until we reach exact target
  while (hopperCoinCountB < coinsToDispense) {
    if (millis() - startTime > timeout) {
      Serial.println(F("  WARNING: Hopper B timeout!"));
      break;
    }
    
    // Check for coin detection
    int prevCount = hopperCoinCountB;
    checkForHopperCoinB();
    
    // If coin was detected, update timestamp
    if (hopperCoinCountB > prevCount) {
      lastCoinDetected = millis();
    }
    
    // Safety: if no coin for 3 seconds, stop motor (don't wait for at least 1 coin)
    if (millis() - lastCoinDetected > 3000) {
      Serial.println(F("  WARNING: No coins detected for 3s - STOPPING HOPPER B!"));
      digitalWrite(RELAY_PIN_B, HIGH);
      delay(100);
      break;
    }
    
    delay(1); // Small delay to prevent tight loop
  }
    // Run motor a bit longer to ensure last coin is ejected
    int postDispenseDelay = 100; // ms, tune as needed
    delay(postDispenseDelay);
    digitalWrite(RELAY_PIN_B, HIGH);
    Serial.println(F("  Hopper B motor stopped"));
    delay(200); // Allow motor to fully stop
    Serial.print(F("  Hopper B dispensed "));
    Serial.print(hopperCoinCountB);
    Serial.print(F(" x PHP "));
    Serial.print(COIN_VALUE_B);
    Serial.println(F(" coins"));
    return hopperCoinCountB;
}

void checkForHopperCoinA() {
  static int lastCoinStateA = HIGH;
  int coinState = digitalRead(COIN_HOPPER_PIN_A);
  unsigned long currentTime = millis();
  
  if (lastCoinStateA == HIGH && coinState == LOW) {
    if (currentTime - lastCoinTimeA > minCoinInterval) {
      hopperCoinCountA++;
      lastCoinTimeA = currentTime;
      
      Serial.print(F("    Coin A dispensed! Count: "));
      Serial.print(hopperCoinCountA);
      Serial.print(F("/"));
      Serial.println(targetCoinCountA);
      
      // DON'T stop motor here - let the main loop handle it for accuracy
    }
  }
  
  lastCoinStateA = coinState;
}

void checkForHopperCoinB() {
  static int lastCoinStateB = HIGH;
  int coinState = digitalRead(COIN_HOPPER_PIN_B);
  unsigned long currentTime = millis();
  
  if (lastCoinStateB == HIGH && coinState == LOW) {
    if (currentTime - lastCoinTimeB > minCoinInterval) {
      hopperCoinCountB++;
      lastCoinTimeB = currentTime;
      
      Serial.print(F("    Coin B dispensed! Count: "));
      Serial.print(hopperCoinCountB);
      Serial.print(F("/"));
      Serial.println(targetCoinCountB);
      
      // DON'T stop motor here - let the main loop handle it for accuracy
    }
  }
  
  lastCoinStateB = coinState;
}
