; ==============================================================================
; EdgeGuard Safety & Fan Interlock Controller
; Target PLC: Delta Electronics DVP-12SE11R (Ethernet Slim Series)
; Programming Language: Instruction List (IL) / Mnemonic
; Compatible Tools: Delta ISPSoft 3.x / WPLSoft 2.5x
; ==============================================================================

; --- Network 1: Mode Evaluation & Register Reflection ---
; Read physical switch X0: High = AUTO mode (M10), Low = MANUAL mode (M11)
LD      X0
OUT     M10
MOV     K1          D0

LDI     X0
OUT     M11
MOV     K0          D0

; --- Network 2: Hardware Emergency Stop Detection ---
; X1 is wired NC (Normally Closed) for fail-safety.
; If wire breaks or button is pushed, X1 becomes 0 (LDI X1 = TRUE) -> Latches M20.
LDI     X1
SET     M20

; --- Network 3: AI Restricted Zone Intrusion Interlock ---
; AI Trip Request (M0) is ONLY accepted when in AUTO mode (M10).
; In MANUAL mode (M11), AI requests are completely rejected by hardware interlock.
LD      M10
AND     M0
SET     M20

; --- Network 4: Communication Watchdog Fault Interlock ---
; If Gateway heartbeat freezes for > 3.0 seconds during AUTO mode, trip system.
LD      M10
AND     M100
SET     M20

; --- Network 5: Latched Safety Trip Handling & Alarm Strobe Output ---
; When M20 is set, turn on physical alarm strobe (Y1) and set D1 = 2 (TRIPPED).
LD      M20
OUT     Y1
MOV     K2          D1

; When no trip is active, clear alarm and reflect normal state.
LDI     M20
RST     Y1
LD      M1013
ANI     M20
MOV     K0          D1

; --- Network 6: Safety Reset & Acknowledgment ---
; System can be unlatched ONLY IF physical E-Stop (X1) is healthy (closed),
; and either physical Reset PB (X2) or Software Reset (M21) is pulsed.
LD      X2
OR      M21
AND     X1
RST     M20
RST     M0
RST     M21
MOV     K0          D1

; --- Network 7: Equipment Main Contactor Run Control (AUTO Mode) ---
; In AUTO mode, fan run is started by Remote Start (M30) or Local PB (X3),
; conditioned on Stop PB (X4), healthy Arduino (X5), no safety trip (M20), and no watchdog alarm (M100).
LD      M10
AND(
LD      M30
OR      X3
)
AND     X4
AND     X5
ANI     M20
ANI     M100
SET     Y0

; Immediate Stop in AUTO mode if Stop PB is hit, remote stop requested, or trip latched.
LD      M10
AND(
LDI     X4
OR      M31
OR      M20
OR      M100
)
RST     Y0

; --- Network 8: Equipment Main Contactor Run Control (MANUAL Mode) ---
; In MANUAL mode, only local physical pushbuttons operate the machine.
LD      M11
AND     X3
AND     X4
ANI     M20
SET     Y0

LD      M11
AND(
LDI     X4
OR      M20
)
RST     Y0

; --- Network 9: Arduino Speed Enable Signal (Y2) ---
; Speed Gate Y2 activates when main contactor Y0 is ON and safety is cleared.
LD      Y0
ANI     M20
OUT     Y2

; --- Network 10: AI Gateway Watchdog Timer (3.0s Timeout) ---
; Compares D10 (Gateway written counter) with D11 (PLC internal copy).
; If equal for > 30 * 100ms = 3.0s, timer T0 triggers M100.
LD=     D10         D11
TMR     T0          K30

LD      T0
SET     M100

; If D10 changes, update D11 and reset watchdog timer.
LD<>    D10         D11
MOV     D10         D11
RST     T0
RST     M100

; --- Network 11: Heartbeat Blinker Output (Y3) ---
; M1013 is Delta PLC internal special register for 1.0 second clock pulse (0.5s ON, 0.5s OFF).
LD      M1013
OUT     Y3

; --- Network 12: End of Execution ---
END
