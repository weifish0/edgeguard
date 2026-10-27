# Delta DVP-12SE11R PLC Safety Controller

本目錄包含 **EdgeGuard 邊緣工業防護系統** 針對 **台達電子（Delta Electronics）DVP-12SE11R 乙太網型 PLC** 開發之階梯圖程式（Ladder Logic）、指令表（Instruction List）、Modbus TCP 位址對照表與測試驗證工具。

---

## 1. 核心安全架構與互鎖設計原則

1. **硬體優先與實體互鎖（Hardware Interlock Priority）**：
   - 實體急停開關（E-Stop, X1）採用常閉（NC, Normally Closed）接線。一旦線路斷開或被拍下，PLC 階梯圖即刻自鎖置位 `M20` 警報旗標，硬體繼電器 `Y0` 即時斷開風扇負載電源。
   - 模式選擇開關（X0）：
     - **MANUAL 模式（X0 = 0）**：系統**絕對拒絕**任何來自 AI 模型或上位機的遠端控制指令（`M0` AI 停機、`M30` 遠端啟動均被互鎖屏蔽），所有操作權限歸屬於現場操作人員。
     - **AUTO 模式（X0 = 1）**：系統進入 AI 輔助防護狀態，允許 AI 觸發受限的安全降速與停機請求。
2. **通訊心跳看門狗（Communication Watchdog, T0）**：
   - 上位機網關 / 儀表板必須每秒向 PLC 暫存器 `D10` 寫入遞增的心跳數值。
   - 若通訊中斷超過 3.0 秒（`T0 = K30`），PLC 自動判定通訊故障（`M100 = 1`），觸發安全停機保護，避免 AI 斷線造成盲區。
3. **明確人工復歸流程（Manual Reset Required）**：
   - 當限制區被闖入或急停觸發後，狀態將持續自鎖於 `M20 = 1`（`D1 = 2` TRIPPED）。
   - 人員離開危險區**絕不自動重新啟動**設備，必須由現場人員確認無安全疑慮後，按下實體復歸按鈕（X2）或上位機確認復歸（M21），並確認 X1 正常閉合，方可解除警報。

---

## 2. 檔案說明

- `edgeguard_dvp12se_ladder.il`：標準指令表原始碼（Mnemonic / Instruction List），可直接複製貼入 Delta WPLSoft 或 ISPSoft。
- `edgeguard_dvp12se_ladder.txt`：ASCII 階梯圖視覺化結構與詳細註解。
- `modbus_mapping.md`：完整 Modbus TCP 暫存器（D Registers）、線圈（M Coils）、數位輸入（X）、數位輸出（Y）對照表。
- `modbus_mapping.json`：機器可讀 JSON 格式的 Modbus 點位配置，供上位機或 Dashboard 自動載入。
- `test_plc_modbus.py`：Python 終端診斷腳本，用於現場快速驗證 PLC 網路通訊與點位狀態。

---

## 3. 上載至台達 PLC 步驟（WPLSoft / ISPSoft）

### 使用 ISPSoft 3.x / WPLSoft 2.5x：
1. 使用 RJ45 網路線將電腦連接至 Delta DVP-12SE11R 的 Ethernet 埠（預設 IP：`192.168.1.5`）。
2. 打開 **Delta COMMGR**，建立一個 Driver：
   - 選擇通訊類型：`Ethernet`
   - 輸入 PLC IP 位址：`192.168.1.5`
   - Port：`502`
3. 打開 **WPLSoft** 或 **ISPSoft**：
   - 新增專案，機型選擇 `DVP-SE`。
   - 建立新的階梯圖程式。
   - 將 `edgeguard_dvp12se_ladder.il` 中的指令複製並貼入編輯器（或手動繪製對應階梯圖）。
4. 點選 **編譯（Compile）**，確認語法檢查 0 錯誤。
5. 點選 **下載至 PLC（Download to PLC）**。
6. 將 PLC 側邊運轉撥鈕切換至 **RUN** 模式。
