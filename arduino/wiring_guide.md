# Arduino UNO / Nano Hardware Wiring & Circuit Guide

本指南詳細說明 **Arduino UNO** 與 **24V 工業風扇**、**MOSFET 驅動模組** 以及 **台達 DVP-12SE11R PLC** 之間的實體接線圖與電氣安全規範。

---

## 1. 電氣安全原則（Critical Safety Rules）

> [!CAUTION]
> **嚴禁將 24V DC 電源直接連接至 Arduino 的任何引腳（VCC, GND 或 GPIO）。**
> Arduino 所有 GPIO 最高僅容許 **5.0V**，超壓將立即燒毀晶片。

1. **電源隔離與共地原則**：
   - Arduino 由 USB（5V）或獨立 7-12V DC 插頭供電。
   - 風扇必須使用獨立的 **24V DC 工業開關電源** 供電。
   - 24V 電源的 **GND（負極）** 與 Arduino 的 **GND** 必須單點連接（Common Ground），以建立共基準電位；若使用光耦隔離 MOSFET 模組（如 LR7843 或 PC817 光耦隔離板），控制側與負載側的地線可完全隔離。
2. **掉電/重啟防誤動作（Pull-Down Resistor）**：
   - Arduino 重啟或開機瞬間，Pin 9 處於高阻抗輸入態。
   - **必須在 Pin 9 與 GND 之間外接一顆 10kΩ 下拉電阻**，防止重啟期間閘極浮動導致風扇意外瞬間全速旋轉。

---

## 2. 引腳接線對照表（Pin Assignment Table）

| Arduino Pin | 方向 | 連接對象 | 信號說明 | 電氣規格 |
|---|---|---|---|---|
| **D9 (PWM)** | 輸出 | MOSFET 驅動模組 `PWM / SIG` | 控制風扇轉速之 PWM 信號 | 5V TTL, 490Hz / 25kHz |
| **D2 (INT0)** | 輸入 | 24V 風扇黃線（Tachometer） | 轉速脈衝回授（每轉 2 脈衝） | 5V 經內部/外接 Pull-up |
| **D4** | 輸入 | 台達 PLC `Y2`（經繼電器或光耦） | PLC 運轉允許信號（Interlock） | 5V 數位輸入（HIGH=運轉） |
| **D7** | 輸出 | 台達 PLC `X5`（經光耦隔離） | Arduino 系統健康/看門狗輸出 | 5V 數位輸出（HIGH=正常） |
| **D13** | 輸出 | 板載 LED | 運轉狀態與故障指示燈 | 板載 |
| **5V / GND** | 供電 | 各模組邏輯供電與共地 | 邏輯基準點 | 5V DC / 0V |

---

## 3. 電路示意圖（Circuit Schematic Diagram）

```text
+-------------------------------------------------------------+
|                      ARDUINO UNO / NANO                     |
|                                                             |
|   [D9 PWM] ----------+                                      |
|                      |                                      |
|                    [10kΩ] (External Pull-Down)              |
|                      |                                      |
|   [GND] -------------+---------------+                      |
|                                      |                      |
|   [D2 INT0] ---------+               |                      |
|                      |               |                      |
|                    [10kΩ]            |                      |
|                      |               |                      |
|   [5V] --------------+               |                      |
|                                      |                      |
|   [D4 IN]  <-- [PLC Y2 Relay COM/NO]--+ (5V Signal Loop)     |
|   [D7 OUT] --> [Optocoupler] -------> PLC X5 (24V Loop)     |
+-------------------------------------------------------------+
                       |               |
                       | (5V PWM)      | (Common GND)
                       v               v
+-------------------------------------------------------------+
|                  MOSFET DRIVER MODULE (LR7843)               |
|                                                             |
|  Control Side:  [PWM/SIG]   [GND]                           |
|  Load Side:     [VIN +]     [VIN -]   [OUT +]    [OUT -]    |
+--------------------+-----------+--------+----------+--------+
                     |           |        |          |
                     |           |        +-------+  |
       +24V DC ------+           |                |  |
       (Power Supply)            |                v  v
       GND ----------------------+          +--------------+
                                            | 24V DC FAN   |
       Tachometer (Yellow Wire) ----------->| +24V  (Red)  |
       (Open-collector to Arduino D2)       | GND   (Black)|
                                            +--------------+
```

---

## 4. 轉速感測線（Tachometer）接線注意事項

- 大多數 3-wire / 4-wire 風扇的轉速線（黃色或綠色）為 **Open-Collector（開集極）** 結構。
- Arduino 韌體已啟用 `pinMode(PIN_TACH_IN, INPUT_PULLUP)`，但建議在 D2 與 Arduino 5V 之間額外跨接一顆 **4.7kΩ ~ 10kΩ** 上拉電阻，避免長距離接線雜訊造成轉速跳動。
- **嚴禁將風扇黃線接觸 24V 電源**，否則會灌入 Arduino 引腳導致燒毀。
