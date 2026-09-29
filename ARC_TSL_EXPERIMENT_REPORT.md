# ARC-TSL v0.1 實驗結果報告

**研究問題**：在固定 domain axioms（ML + DSA）之上，先從同一道 ARC task 的多個 IO pairs 誘導出
task-specific language `TSL_τ`（DreamCoder-style local wake → compression → re-wake），再做程序搜索，
是否比直接在固定完整 DSL 上搜索更有效率？

**一句話結論**：閉環可運行、可測試、可對照；在 `TSL_τ` 已存在的情況下 full-task 搜索成本下降 2–3 個數量級，
但誘導 `TSL_τ` 的 wake 成本高於它節省的搜索成本（總成本比 ≈ 0.4），且在真實 ARC 上受限於搜索深度
（可達 cost level 8，而多數可表達的 task 程式在 11–24），因此假設**在真實 ARC 上尚未被證實或否證**；
目前最有價值的產出是一組清楚的失敗案例與原因分析。

所有數字均由 repo 內指令產生，原始檔在 `results/arc_tsl/`（`main/`、`deep/`、`smoke/`、`synthetic_demo.md`）。
程式碼、測試（51 項）與設計說明見 `arc_tsl/README.md`、`docs/ARC_TSL_DESIGN.md`。

---

## 1. 實驗設定

| 項目 | 設定 |
|---|---|
| 資料 | ARC-AGI-1 training（400 題），其中 262 題 train 輸出形狀 = 輸入形狀（v0.1 in scope） |
| 任務選擇 | 確定性：sorted ids → `random.Random(0).shuffle` → 取前 130 題 in-scope |
| 條件 | A `baseline`（固定 ML+DSA）；B `tsl`（A_τ，均勻 θ）；C `reweight`（僅 θ_τ）；D `tsl_reweight`（A_τ + θ_τ） |
| 搜索引擎 | 自底向上、cost-ordered、typed enumeration + observational equivalence（所有條件共用） |
| 主實驗預算（每次搜索） | max cost 10、300k expanded states、30 s（wake 每 pair 20 s），lambda 深度 2 |
| Cost convention | 每個 production 1（ML 邏輯/算術 combinators 2，固定先驗）、application 0、λ 1；`L(A)=Σ(L(body)+1)`；所有條件相同 |
| 物件抽取 | 8-connectivity、background = color 0（可配置） |
| 環境 | 4 CPU、純 Python（無 torch / ghc / stitch） |

## 2. 主實驗（130 題，`results/arc_tsl/main`）

### 2.1 Solve rate

| 條件 | 解出 | 狀態分佈 |
|---|---:|---|
| baseline | 2 / 130 | 128 SEARCH_TIMEOUT |
| tsl | 2 / 130 | 127 NO_PAIRWISE_SOLUTION、1 NO_SHARED_PROGRAM |
| reweight | 2 / 130 | 同上 |
| tsl_reweight | 2 / 130 | 同上 |

兩題（`3c9b0459` 每物件旋轉 180°；`3aa6fb7a` 填滿每物件 bbox）所有條件都解出；沒有任何條件解出對方解不出的題。

### 2.2 已解題上的搜索成本（n = 2）

| task | baseline states / s / L | tsl states / s / L | reweight states / s / L | tsl_reweight states / s / L | wake 成本 (states / s) |
|---|---:|---:|---:|---:|---:|
| 3aa6fb7a | 42 241 / 4.59 / 7 | 162 / 0.011 / 3 | 1 694 / 0.145 / 7 | 112 / 0.009 / 3 | 78 587 / 5.25 |
| 3c9b0459 | 6 570 / 0.14 / 6 | 106 / 0.005 / 2 | 313 / 0.046 / 6 | 7 / 0.009 / 2 | 20 932 / 0.25 |

幾何平均比值（baseline / method）：

| 條件 | expanded states | first-solution states | 搜索時間 | 含 wake 的總 states |
|---|---:|---:|---:|---:|
| tsl | **127×** | 127× | 115× | 0.41× |
| reweight | 22.9× | 22.9× | 9.8× | 0.40× |
| tsl_reweight | **595×** | 595× | 94× | 0.41× |

MDL：兩題 `L(A_τ)=6/7`，`L(p_τ|TSL_τ)=3/2`，total MDL = 9；baseline 程式長度 7/6。
兩個 abstraction 都是（近似）整個程式（`#f0 = λo. add_region o rg_bbox c1`、`#f0 = map (λo. rotate o r180) $0`），
因為各 pair 的局部程式完全相同。這是 MDL 上正確的行為，但**不構成組合式重用的證據**。

### 2.3 消融解讀

* θ_τ（僅重加權，不加 abstraction）單獨就給 ~20× 的 states 減少：收益一大部分來自「task-local primitive prior」而非新 abstraction。
* A_τ 在 θ_τ 之上再給 ~25×（595 vs 23）。
* 兩者都無法改變 solve rate。

## 3. 失敗分析（主要發現）

### 3.1 搜索深度是瓶頸，不是 ontology

`python -m arc_tsl.experiments.diagnose --all --out results/arc_tsl/main`
用人工撰寫的參考程式（僅供診斷、搜索絕不讀取）檢查可表達性：

| task | 參考程式（cost） | 搜索到達 level | 分類 |
|---|---|---:|---|
| 67385a82 | `map (λo. if_obj (lt i2 (size o)) (recolor o c8) o)`（13） | 8 | 可表達，超出到達深度 |
| bb43febb | `map (λo. add_region (recolor (remove_region o rg_boundary) c2) rg_neighbors8 c5)`（11） | 8 | 可表達，超出到達深度 |
| 5521c0d9 | `map (λo. translate o (vec (neg (height o)) i0))`（11） | 7 | 可表達，超出到達深度 |
| b27ca6d3 | 對 size-2 物件加 8 鄰域外框（14） | 7 | 可表達，超出到達深度 |
| d2abd087 / 6e82a1ae / aabf363d | 依 size / 最小物件顏色的條件重著色（18 / 24 / 17） | 7 | 可表達，超出到達深度 |
| d364b489、913fb3ed | 依方向 / 依顏色的外框 | – | v0.1 不可表達 |

主實驗 baseline 的 `max_cost_reached` 分佈：5:1、6:23、7:48、8:51、9:6、10:1；平均每題 24 s。
自底向上枚舉每上升一個 cost level 約成長一個數量級（level 8 含數十萬個 observationally distinct terms）。

### 3.2 Wake 比 full search 深一層，但只深一層

在 53% 的題目中，單一 pair 的 wake 到達的 cost level 比全 pair 搜索高 1（單 pair 的 OE 等價類更少）。
這正是假設所依賴的機制，但 8 → 11–18 的差距不是一層能補上的。

### 3.3 最有資訊量的失敗：`63613498`（`results/arc_tsl/main/trace_63613498.md`）

* wake：3/3 pairs 解出，程式僅差一個顏色常數：`map (λo. replace_color o c6 c5) $0`、`… c9 …`、`… c1 …`
* sleep：誘導出 `#f0 = λ(x0:Color, x1:ObjectSet). map (λo. replace_color o x0 c5) x1`，MDL 21 → 17，
  frontiers 改寫為 `(#f0 c6 $0)`、`(#f0 c9 $0)`、`(#f0 c1 $0)`
* re-wake：目標程式形如 `(#f0 ⟨關係式 Color 表達式⟩ $0)`——abstraction 已精確隔離出需要跨 pair 泛化的部分，
  但該 Color 表達式（與模板物件同形狀之物件的顏色）仍超出可達深度；30 s 內僅到 level 7，600k states 時到 level 8。

這是「機制正確運作、直到搜索預算用盡」的案例，也是本假設在真實 ARC 上最接近被驗證的點。

## 4. 加大預算的診斷實驗（6 題，人工挑選，`results/arc_tsl/deep`）

預算 600k states / 300 s，2 workers（1M states 時 worker 因記憶體 cgroup 被 kill，單 worker 達 4.4 GB）。

| task | baseline | tsl | reweight | tsl_reweight | wake | 備註 |
|---|---:|---:|---:|---:|---:|---|
| 25ff71a9 | 7 370 states, L=6 | **106**, L=2, MDL 9 | 391 | **7** | 18 388 | 整程式 abstraction |
| a79310a0 | 93 743 states, L=8 | **106**, L=2, MDL 11 | 3 879 | **7** | 207 071 | 整程式 abstraction |
| bb43febb | timeout @ 8 | timeout @ 8 | timeout | timeout | 1.2 M | 參考 cost 11 |
| 5521c0d9 | timeout @ 8 | timeout @ 8 | timeout | timeout | 1.8 M | 參考 cost 11 |
| 67385a82 | timeout @ 8 | timeout @ 8 | timeout | timeout | 2.4 M | 參考 cost 13；一個 pair 到 9 |
| 63613498 | timeout @ 8 | 誘導出 `#f0(Color, Set)`，timeout @ 8 | timeout | timeout | 0.19 M | 見 §3.3 |

已解兩題的幾何平均：tsl 248×、reweight 21×、tsl_reweight 3 755×（states）；含 wake 總成本比仍 ≈ 0.42。
把 states 預算加倍（300k → 600k）沒有多到達任何一個 cost level。

## 5. 合成範例（`results/arc_tsl/synthetic_demo.md`）

三個 pair 由 `map (λo. recolor (translate o v) c2) $0`、`v ∈ {down, up, left}` 生成；task-level 目標用未見過的 `v = right`。
wake 找到三個具體程式 → compression 誘導 `#f0 = λ(v, s). map (λo. translate (recolor o c2) v) s`（MDL 24 → 18）
→ full-task 搜索在 `TSL_τ` 中需 **148** states，在固定 DSL 中需 **93 456** states（631×），程式長度 3 vs 8；
wake 成本 188 448 states。這清楚展示了 pairwise programs → learned local abstraction → reduced search 的機制。

## 6. 結論

1. **已建立**：ML / DSA / TSL 三層分離的可運行閉環，含確定性 cost convention、MDL 記帳、expansion / contraction、
   三個對照條件、完整搜索統計、失敗分類工具與 51 項測試。沒有任何 task-specific primitive 或 hard-code。
2. **已觀察**：當 `TSL_τ` 捕捉到共享結構時，full-task re-wake 便宜 10²–10³ 倍、程式短 2–3 倍；θ_τ 單獨約 10–20×。
3. **未證實**：計入 wake 後，在 baseline 已能解的題上整體更貴（≈0.4×）；真正能獲益的區域
   （pairwise 可解、全題不可解，例如 `63613498` 與主實驗中 6 題「至少一個 pair 局部解出但 baseline 失敗」）
   目前被搜索深度擋住，因此假設在真實 ARC 上尚無法回答。
4. **限制**：僅 same-shape 題；無整格旋轉 / 翻轉；OE 使單 pair frontier 幾乎只有一個程式（abstraction 只能來自跨 pair 反統一）；
   壓縮器不是原版 DreamCoder compressor（無 version space、無 inside-outside 擬合、greedy、單位 cost）；記憶體隨保留 term 數線性成長。

## 7. 建議的下一步（不改研究設計）

* 以 grammar prior 驅動的 top-down / best-first 枚舉器取代純 level-by-level 自底向上枚舉，讓 θ_τ 與 A_τ 能**剪枝**而非只是重排序，
  這是把可達深度從 8 推到 11+ 的最直接手段。
* 讓 wake 在單 pair 內產生多樣 frontier（例如對 top-level 以外的 cell 放寬 OE），使 compression 能在 pair 內反統一。
* 記憶體受限的 OE（不保存每個 retained term 的完整 values）。
* 在上述改進後，優先在 `63613498` 類型（pairwise 可解、全題不可解）的題目上重跑 A/B/C/D。

## 附錄：重現指令

```bash
python -m pytest tests/arctsl -q
python -m arc_tsl.experiments.run_all --tasks 130 --seed 0 --in-scope-only --time-limit 30 --wake-time-limit 20 --out results/arc_tsl/main --workers 4
python -m arc_tsl.experiments.diagnose --all --out results/arc_tsl/main
python -m arc_tsl.experiments.trace --out results/arc_tsl/main --task 63613498
python -m arc_tsl.experiments.run_all --task-ids 25ff71a9,a79310a0,bb43febb,5521c0d9,67385a82,63613498 --max-states 600000 --time-limit 300 --out results/arc_tsl/deep --workers 2
python -m arc_tsl.experiments.synthetic_demo --out results/arc_tsl/synthetic_demo.md
```
