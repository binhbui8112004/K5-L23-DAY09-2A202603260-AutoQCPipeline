# Báo cáo Day 09 — Bùi Bình, 2A202603260

## 1. Kết luận trước
Pipeline kết luận **Hold** (mã thoát `10`). Từ **224 ảnh** đầu vào (`data/raw`), Bước 1 (intake) loại **22/224 ảnh** (`9.8%`) vi phạm lỗi bắt buộc về file ảnh, kích thước, trùng lặp và rò rỉ tập test; nhận **202/224 ảnh** (`90.2%`) vào luồng QC và xuất bản nháp **202 ảnh** (gồm **744 box**: `0: car = 100`, `1: person = 573`, `2: truck = 41`, `3: bus = 30`) ra `submission/export/clean_v1/`.

**Lý do chính:** Sau sửa tự động (`autofix`) và mô phỏng người duyệt hết ngân sách **80/202 ảnh** đầu hàng đợi (`05_review_queue.csv`), toàn bộ lỗi bắt buộc (`ERROR`) đã giảm về **0/202 ảnh** (bao gồm `6/6` ảnh thiếu file nhãn đã được người gán bổ sung), nhưng vẫn còn **44/202 ảnh (`21.78%`)** chưa được người duyệt có cảnh báo (`WARN`), vượt ngưỡng chặn `gate.warn_ratio_hold = 10.0%` nên chưa đủ điều kiện phát hành chính thức (`Release`).

---

## 2. Lỗi và phân việc
Bảng dưới đây tổng hợp toàn bộ **20 mã lỗi/cảnh báo** (**225 dòng**: **58 `ERROR`** + **167 `WARN`**) có mặt trong lô dữ liệu từ `submission/reports/02_error_list_v1.txt` (quét `224` ảnh ở Bước 1 và `202` ảnh được nhận ở vòng QC 1):

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 / 224 ảnh (`img_0010`, `img_0136`) | **Máy** (loại ở Bước 1 / `remove_image`) | File ảnh hỏng byte (`UnidentifiedImageError`, `OSError`), không thể giải mã pixel để gán nhãn hay huấn luyện. |
| `BAD_SIZE` | 3 / 224 ảnh (`img_0107`, `img_0113`, `img_0122`) | **Máy** (loại ở Bước 1 / `remove_image`) | Cạnh ngắn `180px`, `226px` `< min_side_px = 250px` theo quy tắc cố định của dự án; kiểm tra hoàn toàn xác định. |
| `DUP_IMAGE_EXACT` | 8 / 224 ảnh | **Máy** (loại ở Bước 1 / `remove_image`) | Trùng từng byte (`md5`) với ảnh đứng trước trong lô; giữ bản đầu tiên và xoá bản sao là an toàn tuyệt đối. |
| `DUP_IMAGE_NEAR` | 4 / 224 ảnh (`img_0076`, `img_0143`, `img_0186`, `img_0223`) | **Máy** (loại ở Bước 1 / `remove_image`) | Trùng gần đúng (`phash_dist <= 12`, thực tế `dist = 0, 0, 10, 6`) với ảnh đã giữ (`img_0042`, `img_0037`, `img_0061`, `img_0077`). |
| `LEAK_TEST` | 5 / 224 ảnh (`img_0049`, `img_0101`, `img_0167`, `img_0174`, `img_0221`) | **Máy** (loại ở Bước 1 / `remove_image`) | Trùng `md5` hoặc `phash <= 12` với ảnh trong `data/test/images`; bắt buộc loại để chống rò rỉ tập đánh giá. |
| `BAD_CLASS_NAME` | 2 dòng / `data.yaml` (`'Person'` id 1, `'Bus'` id 3) | **Máy** (`autofix`: `rename_classes`) | Sai chữ hoa/thường so với danh sách lớp chuẩn `[car, person, truck, bus]`; máy chuẩn hoá lại `data.yaml` an toàn. |
| `BAD_FORMAT` | 3 dòng / 3 ảnh (`img_0014:1`, `img_0022:1`, `img_0179:1`) | **Máy** (`autofix`: `drop_line`) | Dòng chứa `nan` hoặc chỉ có 4 cột số; cú pháp hỏng không thể suy diễn toạ độ nên máy xoá dòng và gắn cờ `FIXED_DROP_LINE`. |
| `BAD_CLASS_ID` | 6 dòng / 6 ảnh (id `-1`, `4`, `7`, `93` trên 202 ảnh) | **Máy** (`autofix`: `drop_line`) | ID lớp nằm ngoài `0..3` (rác từ chỉ số lớp COCO gốc); máy xoá dòng hỏng và cộng điểm ưu tiên để người kiểm lại ảnh. |
| `BOX_ZERO` | 4 dòng / 4 ảnh (`img_0050:1`, `img_0066:3`, `img_0092:2`, `img_0185:10`) | **Máy** (`autofix`: `drop_line`) | Box suy biến có `w <= 0` hoặc `h <= 0` (diện tích bằng 0), không mang thông tin hình học hợp lệ. |
| `DUP_BOX` | 7 dòng / 7 ảnh (trên 202 ảnh) | **Máy** (`autofix`: `drop_line`) | Hai dòng cùng lớp trong một ảnh có `IoU > 0.90`; máy giữ box trước và xoá dòng lặp phía sau. |
| `BOX_OUT_OF_IMAGE` | 8 dòng / 8 ảnh (tràn mép `0.023..0.060 > 0.002`) | **Máy** (`autofix`: `clip_box`) | Box tràn nhẹ ra ngoài biên `[0, 1]`; máy cắt (`clip`) các mép về `[0, 1]` và giữ nguyên nhãn lớp. |
| `MISSING_LABEL_FILE` | 6 / 202 ảnh (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`) | **Người** (`autofix` ghi `needs_label` -> đầu hàng đợi) | Máy **không được tạo file nhãn rỗng** (vì file rỗng đồng nghĩa với "ảnh nền không có vật"); chỉ người mới nhìn ảnh để gán box được. |
| `BOX_HUGE` | 3 dòng / 3 ảnh (`img_0018:1`, `img_0128:1`, `img_0196:1`) | **Người** (hàng đợi duyệt, `WARN`) | Box chiếm `97.0%..98.8% > 95%` diện tích ảnh; có thể là vật chụp cận cảnh thật hoặc box bao trùm sai, cần người xác nhận. |
| `BOX_TINY` | 6 dòng / 4 ảnh (`img_0026`, `img_0051`, `img_0069`, `img_0161`) | **Người** (hàng đợi duyệt, `WARN`) | Cạnh ngắn `8.9px..11.9px < 12px` (sau khi `clip_box` ở v2 tăng thêm 1 dòng `img_0030:9` `9.8px` thành 7 dòng / 5 ảnh); cần người xem là nhiễu hay vật ở xa. |
| `CLASS_RARE` | 4 dòng cấp `<dataset>` (lớp `-1`, `4`, `7`, `93` có 1–2 box) | **Máy** (tự hết sau khi `autofix` xoá `BAD_CLASS_ID`) | Cảnh báo thống kê cấp toàn tập dữ liệu do các token ID lớp lạ sinh ra; sau khi `autofix` xoá 6 dòng `BAD_CLASS_ID`, 4 lớp chính đều có `>= 30 box >= 5`. |
| `EMPTY_LABEL` | 12 / 202 ảnh ở v1 (15 / 202 ảnh ở v2 sau `drop_line`) | **Người** (hàng đợi duyệt, `WARN`) | File `.txt` rỗng: máy không phân biệt được ảnh nền thật sự hay ảnh bị bỏ sót toàn bộ đối tượng (như `img_0004`, `img_0065` thực chất bị thiếu nhãn). |
| `POSSIBLE_WRONG_CLASS` | 18 dòng / 18 ảnh (trên 202 ảnh) | **Người** (hàng đợi duyệt, `WARN`) | Nhãn và dự đoán của `yolo26l` trùng vị trí (`IoU >= 0.50`) nhưng khác lớp (vd. `car` vs `person`); xung đột ngữ nghĩa cần người phân xử. |
| `POSSIBLE_MISSING` | 68 dòng / 60 ảnh ở v1 (67 dòng / 59 ảnh ở v2) | **Người** (hàng đợi duyệt, `WARN`) | Model `yolo26l` (`conf >= 0.50`, diện tích `>= 600px²`) thấy đối tượng nhưng nhãn không có box nào khớp (`IoU < 0.30`). |
| `POSSIBLE_LOOSE_BOX` | 31 dòng / 26 ảnh ở v1 (32 dòng / 27 ảnh ở v2) | **Người** (hàng đợi duyệt, `WARN`) | Nhãn cùng lớp với `yolo26l` nhưng `0.30 <= IoU < 0.50` (sau khi `clip_box` dòng `img_0108:1` thì dòng này chuyển từ `POSSIBLE_FALSE_POS` `IoU=0.30` sang `POSSIBLE_LOOSE_BOX` `IoU=0.45`). |
| `POSSIBLE_FALSE_POS` | 25 dòng / 24 ảnh ở v1 (24 dòng / 23 ảnh ở v2) | **Người** (hàng đợi duyệt, `WARN`) | Box nhãn không khớp với bất kỳ dự đoán nào của `yolo26l` có `conf >= 0.10` (`IoU < 0.30`); nghi ngờ box thừa hoặc vẽ sai vị trí. |

### Cơ chế xếp hạng hàng đợi `05_review_queue.csv` và hiệu quả ngân sách 80 ảnh
Hàng đợi `05_review_queue.csv` (gồm **130/202 ảnh** cần người xem sau vòng QC 2) tính điểm ưu tiên `priority` cho mỗi ảnh theo công thức trong `pipeline/steps/review_queue.py`:
$$\text{priority}(\text{img}) = \sum_{i \in \text{WARN}(\text{img})} w(\text{code}_i)\cdot(1 + \text{conf}_i) + \sum_{f \in \text{FIX}(\text{img})} w(\text{action}_f)$$

1. **Vì sao các ảnh đứng đầu hàng đợi được xếp như vậy?**
   - Hạng 1 là **`img_0020` (`priority = 14.527`, mã `FIXED_DROP_LINE;POSSIBLE_MISSING;POSSIBLE_WRONG_CLASS`)**: ảnh này hội tụ cả 3 nguồn rủi ro: vừa bị máy xoá 1 dòng `BAD_CLASS_ID` (`id=93` -> `+2.0`), vừa có 1 cảnh báo `POSSIBLE_WRONG_CLASS` (`truck` vs `bus` với `conf=0.95` -> `3 \times 1.95 = +5.85`), vừa có 2 cảnh báo `POSSIBLE_MISSING` (`person` với `conf=0.84` và `0.50` -> `2 \times 1.84 + 2 \times 1.50 = +6.68`).
   - Hạng 2 là **`img_0185` (`priority = 10.052`, mã `FIXED_DROP_LINE;POSSIBLE_MISSING;POSSIBLE_WRONG_CLASS`)**: kết hợp `FIXED_DROP_LINE` (`+2.0`), `POSSIBLE_WRONG_CLASS` (`conf=0.68` -> `+5.04`) và `POSSIBLE_MISSING` (`conf=0.51` -> `+3.02`).
   - Hạng 3 đến hạng 8 là **toàn bộ 6/6 ảnh thiếu file nhãn** (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219` với `NEEDS_LABEL = 10.0`). Trọng số `10.0` đảm bảo mọi ảnh còn lỗi bắt buộc `MISSING_LABEL_FILE` luôn nằm trong top đầu để người gán nhãn trước, không làm tắc cửa chặn (`Rework`).
   - Nhân hệ số `(1 + conf)` giúp trong cùng một loại cảnh báo ngữ nghĩa, những ảnh mà model `yolo26l` tự tin hơn (vd. `img_0067` có 3 `POSSIBLE_MISSING` đạt `9.892`, hay nhóm `POSSIBLE_WRONG_CLASS` có `conf = 0.91..0.95` đạt `5.72..5.83`) luôn được đẩy lên trước các cảnh báo mơ hồ hoặc lỗi hình học nhẹ (`BOX_HUGE = 0.5`, `BOX_TINY = 0.3` nằm ở cuối hàng đợi `127..130`).

2. **Với ngân sách 80 ảnh (`80/130 = 61.5%` hàng đợi, `80/202 = 39.6%` dataset), người duyệt xem và giải quyết được bao nhiêu lỗi?**
   - **Lỗi bắt buộc thiếu file nhãn:** Người duyệt xử lý trọn vẹn **6/6 ảnh (`100%`)** `MISSING_LABEL_FILE` (`NEEDS_LABEL`), đưa số lỗi bắt buộc toàn pipeline từ `6` về **`0`**.
   - **Lỗi ngữ nghĩa (`second_opinion`):** Ở vòng 2 (`04_error_list_v2.csv`), có tổng cộng **141 cảnh báo ngữ nghĩa trên 109/202 ảnh**. Ngân sách **80 ảnh đầu hàng đợi** đã bao phủ tới **106/141 cảnh báo ngữ nghĩa (`75.2%`) trên 74/109 ảnh (`67.9%`)**:
     - `POSSIBLE_WRONG_CLASS`: duyệt **18/18 cảnh báo (`100.0%`)** trên **18/18 ảnh** (không còn ảnh chưa duyệt nào dính lỗi nhầm lớp).
     - `POSSIBLE_MISSING`: duyệt **59/67 cảnh báo (`88.1%`)** trên **51/59 ảnh** (chỉ còn 8 cảnh báo trên 8 ảnh ngoài top-80).
     - `POSSIBLE_FALSE_POS`: duyệt **13/24 cảnh báo (`54.2%`)** trên **12/23 ảnh** (còn 11 cảnh báo trên 11 ảnh ngoài top-80).
     - `POSSIBLE_LOOSE_BOX`: duyệt **16/32 cảnh báo (`50.0%`)** trên **11/27 ảnh** (còn 16 cảnh báo trên 16 ảnh ngoài top-80).
     - Ngoài ra, người duyệt cũng kiểm tra **11/15 ảnh (`73.3%`)** `EMPTY_LABEL` (toàn bộ 11 ảnh file rỗng mà `yolo26l` phát hiện có vật bị bỏ sót đều nằm trong top-80; chỉ còn 4 ảnh `EMPTY_LABEL` ngoài top-80).

---

## 3. Calibration (2 ngưỡng)
Kết quả chạy `python -m pipeline.calibrate --sweep duplicates.phash_dist=2,4,6,8,10,12,14,16,20 --sweep second_opinion.conf=0.1,0.25,0.4,0.5,0.6,0.7,0.8 --out submission/calibration` trên bộ `data/calib/` (**39 ảnh**, `MANIFEST.csv` có sẵn đáp án lỗi chèn; toàn bộ 8 mã lỗi cú pháp đạt `P = 1.00 / R = 1.00 / F1 = 1.00`):

| Tham số | Khởi đầu | Đã chọn | Precision / Recall / F1 trên `calib` (trước → sau) | Lý do (đánh đổi) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`12`** | `DUP_IMAGE_EXACT`: `1.00 / 1.00 / 1.00` → `1.00 / 1.00 / 1.00` (`3/3` ảnh)<br>`DUP_IMAGE_NEAR`: `1.00 / 0.50 / 0.67` (`TP=3/6, FP=0, FN=3`) → **`1.00 / 0.67 / 0.80`** (`TP=4/6, FP=0, FN=2`) | Tăng ngưỡng từ `2` lên `12` giúp bắt thêm các ảnh trùng bị resize/chỉnh sáng vừa phải (`calib_036`, và trên `raw` bắt thêm 3 ảnh trùng/rò rỉ thật có `dist = 6..10`) mà vẫn giữ **Precision = 1.00** (không xoá nhầm ảnh sạch). Không chọn `16` vì trên `raw` ngưỡng `16` xoá nhầm 8 ảnh khác nhau. |
| `second_opinion.conf` | `0.25` | **`0.50`** | `POSSIBLE_MISSING`: `0.50 / 1.00 / 0.67` (`TP=8, FP=8`) → **`0.57 / 1.00 / 0.73`** (`TP=8, FP=6`)<br>`POSSIBLE_WRONG_CLASS`: `0.56 / 0.83 / 0.67` (`TP=5/6, FP=4`) → **`0.56 / 0.83 / 0.67`** (`TP=5/6, FP=4`)<br>`POSSIBLE_LOOSE_BOX`: `0.29 / 0.40 / 0.33` (`TP=2/5, FP=5`) → **`0.20 / 0.20 / 0.20`** (`TP=1/5, FP=4`)<br>`POSSIBLE_FALSE_POS`: `0.36 / 1.00 / 0.53` → **`0.36 / 1.00 / 0.53`** (dùng `fp_conf=0.10`) | Tăng `conf` từ `0.25` lên `0.50` loại bỏ các dự đoán độ tự tin thấp của `yolo26l`, giúp `POSSIBLE_MISSING` giữ nguyên **Recall = 100% (`8/8`)** trong khi giảm báo động giả (`F1` tăng `0.67 → 0.73`) và giữ nguyên Recall `0.83` (`5/6`) của `POSSIBLE_WRONG_CLASS`, giúp hàng đợi 80 ảnh tập trung vào các lỗi ngữ nghĩa có xác suất đúng cao nhất. |

### Một chỗ calibration có thể đánh lừa và bằng chứng từ dữ liệu thật (`data/raw`)
**Bẫy calibration (`phash_dist = 16` trên tập `calib` nhỏ vs tập `raw` lớn):**
- Nếu chỉ nhìn bảng số liệu trên tập `data/calib/` (`39` ảnh, tương ứng $\binom{39}{2} = 741$ cặp ảnh), ngưỡng `duplicates.phash_dist = 16` trông hoàn hảo nhất: `DUP_IMAGE_NEAR` đạt **`Precision = 1.00, Recall = 0.83, F1 = 0.91`** (`TP = 5/6, FP = 0`, bắt được thêm `calib_037` là bản biến đổi mức 3 của `calib_015` có `phash_dist = 16`), cao hơn hẳn vùng `phash_dist = 4..14` (`Recall = 0.67, F1 = 0.80`).
- Tuy nhiên, khi đưa lên lô dữ liệu thật `data/raw/` (**224 ảnh** so nội bộ và so với **140 ảnh** kho `test` + `gold_val`, tổng cộng $\binom{224}{2} + 224 \times 140 = 56.336$ cặp so sánh — **lớn gấp 76 lần số cặp của `calib`**), xác suất hai ảnh hoàn toàn khác nhau ngẫu nhiên có khoảng cách Hamming `phash == 16` tăng vọt:
  - Ở **`phash_dist = 2` (khởi đầu)**: Bước 1 chỉ phát hiện **14 ảnh** trùng/rò rỉ (`8 DUP_IMAGE_EXACT`, `2 DUP_IMAGE_NEAR` có `dist = 0`, `4 LEAK_TEST`), bỏ lọt **3 ảnh trùng/rò rỉ thật** có `dist = 6..10`.
  - Ở **`phash_dist = 12` (đã chọn)**: Bước 1 phát hiện **17 ảnh** trùng/rò rỉ (+3 ảnh so với `dist = 2`), và **cả 3 ảnh bắt thêm đều là trùng thật 100%**:
    1. `img_0223` (`375x309`) trùng gần đúng với `img_0077` (`500x412`) ở `phash_dist = 6` (tương quan pixel `corr = 0.983` — cùng một cảnh bị resize).
    2. `img_0186` (`640x425`) trùng gần đúng với `img_0061` (`544x361`) ở `phash_dist = 10` (`corr = 0.928` — cùng cảnh bị thu nhỏ và đổi nhẹ độ sáng).
    3. `img_0101` (`450x450`) rò rỉ với `test/test_039.jpg` (`612x612`) ở `phash_dist = 6` (`corr = 0.753` — bản resize/chỉnh màu của ảnh trong tập test).
    Cộng thêm `2 CORRUPT_IMAGE` và `3 BAD_SIZE`, việc loại **22/224 ảnh** ở Bước 1 là hoàn toàn chính xác (`Precision = 100%`).
  - Ở **`phash_dist = 16` (bẫy overfitting vào `calib`)**: Số ảnh bị báo trùng/rò rỉ trên `raw` nhảy từ `17` lên **26 ảnh** (+9 ảnh bị xoá tự động ở `dist = 16`). Mở kiểm tra trực tiếp 9 cặp ảnh ở `dist = 16` này thì chỉ có **1 cặp trùng thật** (`img_0084` `480x640` vs `img_0074` `352x470`, `corr = 0.825`), còn **8/9 cặp là báo động giả (FP) giữa hai ảnh hoàn toàn khác nội dung**:
    - 2 cặp `DUP_IMAGE_NEAR` giả: `img_0011` (`640x427`) vs `img_0008` (`640x480`, `corr = 0.071`) và `img_0177` (`640x425`) vs `img_0113` (`240x226`, `corr = 0.444`).
    - 6 cặp `LEAK_TEST` giả: `img_0013` vs `test/test_087.jpg` (`corr = -0.170`), `img_0017` vs `test/test_071.jpg` (`corr = -0.222`), `img_0021` vs `test/test_048.jpg` (`corr = 0.010`), `img_0033` vs `test/test_070.jpg` (`corr = 0.223`), `img_0038` vs `test/test_002.jpg` (`corr = 0.356`), và `img_0115` vs `test/test_088.jpg` (`corr = 0.221`).
- **Bài học thiết kế:** Vì `duplicates` gán `severity = ERROR` và Bước 1 (`intake`) lẫn `autofix` **xoá thẳng ảnh mà không qua người duyệt**, một báo động giả (`FP`) đồng nghĩa với việc làm mất vĩnh viễn dữ liệu sạch. Do đó, phải chọn `phash_dist = 12` để giữ `Precision = 1.00` trên dữ liệu thật, và ghi nhận các cặp trùng biến đổi mạnh (`dist >= 16`) như một điểm mù có chủ đích ở Mục 4.

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

### (a) Chứng minh cửa chặn (`gate`) chặn đúng khi còn lỗi bắt buộc
Khi chạy lệnh thí nghiệm không có ngân sách người duyệt:
```bash
python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```
- **Diễn biến trong pipeline:** Bước 1 vẫn nhận `202/224` ảnh. Vòng QC 1 phát hiện `36` lỗi bắt buộc (`ERROR`) và `167` cảnh báo (`WARN`). Bước `autofix` sửa tự động được `30` lỗi cú pháp (xoá dòng hỏng/lặp, cắt box tràn, sửa `data.yaml`), nhưng với **6 ảnh `MISSING_LABEL_FILE`** (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`), máy chỉ ghi `action = "needs_label"` vào `03_fixes.csv` chứ không tự bịa file nhãn.
- **Tại Bước 3 & Bước 4 (vòng 3):** Vì `--budget 0`, số ảnh được người duyệt là `reviewed = 0/202`. Sang vòng QC 3, cả 6 ảnh thiếu file nhãn vẫn còn nguyên lỗi `MISSING_LABEL_FILE` (`severity = ERROR`), cùng với `118/202` ảnh (`58.42%`) có cảnh báo `WARN`.
- **Phán quyết của Gate (`work/rep_nb/08_summary.json`):**
  - `verdict.decision = "Rework"`, `n_errors = 6`, `n_warn_images = 118`, `n_images = 202`, `warn_ratio = 0.5842`, `reasons = ["còn 6 lỗi bắt buộc chưa sửa"]`.
  - Pipeline dừng ở Bước 5 với thông báo `"Bước 5/5 KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3"`, trả về **mã thoát `20`** (`EXIT["Rework"] = 20`).
  - Trường `"exported": null` trong `work/rep_nb/08_summary.json` và thư mục `work/exp_nb/clean_v1` **hoàn toàn không được tạo ra**, chứng minh cửa chặn ngăn chặn tuyệt đối việc phát hành dữ liệu còn lỗi bắt buộc.

### (b) Các điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng từ dữ liệu)
Ngay cả khi toàn bộ unit test xanh và các check chạy đúng thiết kế, pipeline vẫn có **4 điểm mù bản chất**:

1. **Nhầm lớp ngữ nghĩa khi model kiểm (`yolo26l`) cũng mắc cùng lỗi với model gán sơ bộ (`yolo26n`) hoặc dự đoán dưới ngưỡng `conf = 0.50`:**
   - *Cơ chế:* `second_opinion` dùng `yolo26l` làm "ý kiến thứ hai". Nếu cả hai model cùng nhầm một đối tượng (do góc chụp khó, vật bị che khuất hoặc hình dáng nhập nhằng giữa `car`, `truck`, `bus`), hai model sẽ "đồng thuận sai" và không sinh cảnh báo nào.
   - *Bằng chứng:*
     - Trên tập `data/calib/`, lỗi chèn `WRONG_CLASS` ở **`calib_009.txt` dòng 6** (`truck -> bus`) không được `yolo26l` bắt ở mọi mức `conf = 0.10..0.80` (`FN = 1`, khiến Recall của `POSSIBLE_WRONG_CLASS` chỉ đạt tối đa `5/6 = 0.83`).
     - Trên tập `data/raw/`, đối chiếu nhãn xuất ở các ảnh không có bất kỳ cảnh báo nào trong `07_error_list_v3.txt` với nhãn chuẩn `data/review_reference/labels/` cho thấy: ảnh **`img_0007`** có box gán lớp `0 (car)` nhưng thực tế là `2 (truck)` (`IoU = 0.884`); ảnh **`img_0153`** có 2 box gán `3 (bus)` và `0 (car)` nhưng nhãn chuẩn đều là `2 (truck)` (`IoU = 0.916` và `0.785`), nhưng cả hai ảnh đều hoàn toàn im lặng ở vòng 3.

2. **Box lỏng hoặc lệch mức trung bình (`0.50 <= IoU < 0.70`):**
   - *Cơ chế:* Quy tắc `POSSIBLE_LOOSE_BOX` chỉ gắn cờ khi box nhãn cùng lớp với dự đoán `yolo26l` có `iou_missing (0.30) <= IoU < iou_loose (0.50)`. Các box bị phóng to hoặc lệch tâm vừa phải có `IoU` trong khoảng `[0.50, 0.70)` (chưa đạt chuẩn khít `IoU >= 0.70` của gán nhãn chất lượng cao) được coi là "đã phủ vật" và bị bỏ qua.
   - *Bằng chứng:*
     - Trên tập `data/calib/`, có 5 lỗi chèn `LOOSE_BOX` (`scale = 1.45..1.58`), nhưng ở `conf = 0.50` pipeline chỉ bắt được `1/5` (`Recall = 0.20`), bỏ sót 4 ca (`calib_002:3` `scale=1.54`, `calib_006:1` `scale=1.48`, `calib_012:1` `scale=1.45`, `calib_024:1` `scale=1.54`).
     - Trên tập `data/raw/`, các ảnh không bị cảnh báo ở vòng 3 như **`img_0118`** (`person`, `IoU` so với nhãn chuẩn chỉ đạt `0.523`), **`img_0023`** (`person`, `IoU = 0.536`), **`img_0105`** (`person`, `IoU = 0.587`), **`img_0043`** (`person`, `IoU = 0.609`) vẫn còn nguyên box lỏng trong `clean_v1`.

3. **Ảnh trùng gần đúng nhưng bị biến đổi mạnh (`phash_dist > 12`):**
   - *Cơ chế:* Perceptual hash (`phash`) dựa trên tần số thấp DCT $8 \times 8$; khi ảnh bị crop lệch khung, xoay/lật hoặc biến đổi tương phản mạnh, khoảng cách Hamming vượt quá ngưỡng an toàn `phash_dist = 12`.
   - *Bằng chứng:*
     - Trên tập `data/calib/`, 2/6 ảnh trùng biến đổi mạnh trong `MANIFEST.csv` là **`calib_037`** (bản biến đổi mức 3 của `calib_015`, `phash_dist = 16`) và **`calib_038`** (bản biến đổi mức 4 của `calib_024`, `phash_dist = 22`) không bị bắt ở ngưỡng `12` (`FN = 2`, `Recall = 4/6 = 0.67`).
     - Trên tập `data/raw/`, cặp **`img_0084`** (`480x640`) và **`img_0074`** (`352x470`) có tương quan pixel rất cao (`corr = 0.825`, cùng một cảnh) nhưng có `phash_dist = 16 > 12`, nên cả hai ảnh đều lọt qua Bước 1 vào tập `202` ảnh.

4. **Thiếu nhãn trên vật nhỏ (`diện tích < 600 px²`) hoặc vật bị che khuất (`conf < 0.50`):**
   - *Cơ chế:* Để tránh ngập báo động giả, `second_opinion` lọc bỏ mọi dự đoán của `yolo26l` có diện tích `< min_area_px = 600 px²` hoặc `conf < 0.50`. Do đó, các đối tượng thật ở xa hoặc bị khuất mà người gán quy chuẩn vẫn gán sẽ không bao giờ kích hoạt `POSSIBLE_MISSING`.
   - *Bằng chứng:* Trong tập `202` ảnh xuất ra, các ảnh không có cảnh báo ở v3 như **`img_0074`** (thiếu 1 box `person` diện tích `589 px² < 600 px²`), **`img_0158`** (thiếu 1 box `car` diện tích `216 px² < 600 px²`), hoặc **`img_0182`** (thiếu 2 box `bus` diện tích `7238 px²` và `8898 px²` bị khuất mà `yolo26l` không phát hiện với `conf >= 0.50`) đều bị bỏ lọt.

---

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
**Trạng thái:** **Chưa chạy** (`python scripts/check_submission.py --no-train`).

**Lý do:** Môi trường làm bài hiện tại chỉ cài đặt các thư viện cốt lõi (`requirements.txt`: `pillow`, `imagehash`, `pyyaml`, `pytest`) và sử dụng dự đoán lưu sẵn trong `data/cache/checker_preds.json` để hoàn thành trọn vẹn Bước 1–5; máy không có GPU/Colab để chạy `scripts/train_compare.py` (`yolo26n`, 20 epochs × 2 seeds trên `raw` và `clean`). Tuân thủ tuyệt đối `RULES.md`, báo cáo không suy đoán hay tự tạo file trong `submission/results/`.

**Khung phân tích và giả thuyết thực nghiệm khi chạy trên Colab:**
- Khi thực hiện train đa seed (`seeds = 0, 1`), chênh lệch $\Delta \text{mAP50} = \text{mAP50}_{\text{clean}} - \text{mAP50}_{\text{raw}}$ bắt buộc phải được đặt cạnh **độ lệch chuẩn giữa các seed ($\sigma_{\text{seed}}$)**: nếu $|\Delta \text{mAP50}| \lesssim \sigma_{\text{seed}}$, kết luận trung thực phải là **chưa thể kết luận `clean` vượt `raw` một cách có ý nghĩa thống kê** (khác biệt nằm trong biên độ nhiễu ngẫu nhiên của huấn luyện).
- **2 giả thuyết giải thích hiện tượng `raw` có thể đạt mAP50 xấp xỉ hoặc cao giả tạo so với `clean` và cách kiểm chứng:**
  1. *Giả thuyết 1 — Rò rỉ tập test (`LEAK_TEST`) và kích thước mẫu trong `raw`:* Tập `raw` (`224` ảnh) chứa **5 ảnh trùng trực tiếp với tập `data/test/images`** (`img_0049` $\leftrightarrow$ `test_033`, `img_0101` $\leftrightarrow$ `test_039`, `img_0167` $\leftrightarrow$ `test_044`, `img_0174` $\leftrightarrow$ `test_085`, `img_0221` $\leftrightarrow$ `test_009`) cùng 12 ảnh trùng nội bộ, khiến model train trên `raw` được học trước 5% số ảnh của tập test (`100` ảnh) và có số bước cập nhật gradient mỗi epoch nhiều hơn `clean` (`202` ảnh). *Cách kiểm:* Chấm lại cả 2 model trên tập `data/test/` đã loại bỏ 5 ảnh bị rò rỉ (`95` ảnh còn lại) hoặc chấm độc lập trên `data/gold_val/` (`40` ảnh).
  2. *Giả thuyết 2 — Phần nhãn máy sơ bộ còn lại trong `clean` (`122/202` ảnh ngoài ngân sách duyệt) và độ nhiễu của tập test nhỏ (`100` ảnh):* Trong `clean_v1`, mới có `80/202` ảnh được thay bằng nhãn người chuẩn (`review_reference`), còn `122/202` ảnh vẫn giữ nhãn máy sơ bộ (`yolo26n`, trong đó còn `44` ảnh có cảnh báo `WARN` và các điểm mù ở Mục 4b). *Cách kiểm:* So sánh thêm biến thể `clean` khi tăng `--budget` lên `130` (duyệt hết hàng đợi) và đánh giá riêng mAP50 theo từng lớp (`car`, `person`, `truck`, `bus`) đặc biệt trên hai lớp ít mẫu là `truck` (`41` box) và `bus` (`30` box) vốn rất nhạy với vài ca `POSSIBLE_WRONG_CLASS`.

---

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối và lộ trình chuyển từ Hold sang Release
- **Quyết định cuối cùng:** **Hold** (`0` lỗi bắt buộc; `44/202` ảnh = `21.78%` còn cảnh báo chưa được người duyệt $\ge$ ngưỡng `10.0%`). Bản xuất `submission/export/clean_v1/` hiện tại được đánh dấu rõ trong `manifest.json` là **bản nháp thử nghiệm**, chưa phát hành cho sản xuất.
- **Cần làm gì để chuyển thành `Release` một cách trung thực?**
  - Không được nâng khống `second_opinion.conf` lên `> 0.85` để làm rỗng hàng đợi giả, và không được hạ `gate.warn_ratio_hold`.
  - Để tỉ lệ ảnh còn cảnh báo chưa duyệt xuống `< 10.0%` trên tổng số `202` ảnh, số ảnh còn cảnh báo chưa duyệt tối đa chỉ được phép là $\lfloor 0.10 \times 202 \rfloor - 1 = 19$ ảnh (tức `19/202 = 9.41% < 10.0%`, hoặc `20/202 = 9.90% < 10.0%`).
  - Hiện tại còn `44` ảnh chưa duyệt có cảnh báo (nằm ở các vị trí từ hạng **81 đến hạng 130** của `05_review_queue.csv`; trong 50 ảnh cuối hàng đợi này có 44 ảnh mang cảnh báo `WARN` và 6 ảnh chỉ mang cờ `FIXED_DROP_LINE` / `FIXED_CLIP_BOX` không còn `WARN`). Do đó, cần cấp thêm ngân sách người duyệt cho **ít nhất 24–30 ảnh tiếp theo trong hàng đợi `05_review_queue.csv`** (nâng tổng ngân sách duyệt từ `80` lên khoảng **`105–110` ảnh**, hoặc duyệt nốt toàn bộ **50 ảnh còn lại** trong hàng đợi lên `130` ảnh để đạt `0/202 = 0.0%` cảnh báo tồn đọng) rồi chạy `python -m pipeline.run --resume-after-review`. Khi đó gate sẽ chính thức kết luận **`Release`** (mã thoát `0`).

### (b) Nhật ký sử dụng AI (3 dòng theo `RULES.md` & `docs/PROMPTING.md`)
1. **Prompt chính (đủ 4 ý: định dạng vào, quy tắc kiểm, đầu ra, giới hạn an toàn):** *"Dựa trên docstring và unit test của 4 module `label_format.py`, `gate.py`, `autofix.py`, `second_opinion.py`, hãy viết hàm xử lý nhãn YOLO 5 cột chuẩn hoá `id cx cy w h` (lấy dòng gốc từ `ds.read_label_lines(stem)` và kích thước từ `ds.image_size(stem)`), trả về `list[Issue]` hoặc `list[dict]` đúng mã lỗi và khoá cấu hình trong `cfg`, tuyệt đối không viết cứng ngưỡng, không sửa `data/raw/` và không nuốt ngoại lệ bằng `except: pass`."*
2. **Cách kiểm tra code:** Đọc rà soát từng dòng để đảm bảo mọi ngưỡng đều đọc từ `cfg`, chạy toàn bộ **79/79 unit test & e2e test** (`pytest -q`), chạy `pipeline.calibrate` đối chiếu với đáp án `data/calib/MANIFEST.csv` (kiểm tra cả 8 mã lỗi cú pháp đạt `Precision = 1.00, Recall = 1.00`), và kiểm tra chéo các cặp ảnh bị loại trên `data/raw/` ở nhiều mức `phash_dist`.
3. **Một lần AI sai/thiếu và cách sửa:** Trong bản nháp đầu của `autofix.py`, khi xử lý `BAD_CLASS_NAME`, nếu `class_names.run` trả về **2 issue `BAD_CLASS_NAME` liên tiếp** cho cùng file `data.yaml` (vì cả id 1 `'Person'` và id 3 `'Bus'` đều sai), code không có cờ đánh dấu đã sửa sẽ ghi đè `data.yaml` 2 lần và sinh 2 dòng `rename_classes` trùng nhau trong `03_fixes.csv` (dòng thứ 2 có `before == after`); tôi đã phát hiện khi đối chiếu `02_error_list_v1.txt` (có 2 dòng `BAD_CLASS_NAME`) với `03_fixes.csv` và sửa bằng cách thêm cờ `renamed = True` để mỗi lần chạy `autofix.fix` chỉ ghi lại `data.yaml` và xuất đúng 1 dòng fix `rename_classes`.

### (c) *(Thưởng +2)* Đối chiếu bộ lọc CVAT `width < 20` với `BOX_TINY` và thuộc tính `can_review`
- **Kết quả lọc `width < 20` (px) trên 202 ảnh đã xuất (`submission/export/clean_v1/labels/`) và trong 20 ảnh đầu hàng đợi `05_review_queue.csv`:**
  - Trên toàn bộ `202` ảnh (`744` box ở v3), bộ lọc CVAT `width < 20` khớp **47 box trên 25 ảnh** (trong đó nếu xét riêng 20 ảnh đầu `05_review_queue.csv` được nạp vào task CVAT theo `docs/CVAT_FILTER.md`, bộ lọc `width < 20` khớp **10 box trên 5 ảnh**: `img_0020` có 3 box ở dòng 5, 6, 8 với `width = 15.9, 17.6, 16.3 px`; `img_0031` `0` box; `img_0053` có 1 box dòng 2 `width = 16.5 px`; `img_0135` có 2 box dòng 5, 7 `width = 16.5, 18.7 px`; `img_0067` có 1 box dòng 7 `width = 17.5 px`; `img_0199` có 4 box dòng 3, 4, 5, 6 `width = 18.5, 19.3, 18.8, 17.9 px`).
- **Đối chiếu với `BOX_TINY` của pipeline (`min_box_px = 12`):**
  - Ở vòng 3 (`07_error_list_v3.txt`), pipeline chỉ báo **7 box `BOX_TINY` trên 5 ảnh**: `img_0026:6` (`11.4x29.8 px`), `img_0051:5` (`8.9x44.1 px`), `img_0069:2` (`11.2x31.6 px`), `img_0161:2,3,4` (`10.3x32.3 px`, `11.4x43.8 px`, `11.9x43.6 px`), và `img_0183:11` (`11.8x52.7 px`). (Ở vòng 2 trước khi người duyệt sửa `img_0030`, còn có thêm `img_0030:9` với `width = 9.8 px` sau khi `clip_box`).
  - **Nhận xét:** Cả 7/7 box `BOX_TINY` của pipeline đều là tập con nằm trọn trong 47 box khớp `width < 20` của CVAT (cùng các ảnh `img_0026`, `img_0051`, `img_0069`, `img_0161`, `img_0183`). Sự khác biệt `47` box vs `7` box là do: (1) slide/CVAT dùng ngưỡng rộng hơn (`width < 20 px`) để người duyệt lướt xem nhanh các đối tượng hẹp ngang (đa số là người đứng từ xa có bề ngang `12..19.9 px` nhưng chiều cao `22..75 px`, hoàn toàn là đối tượng hợp lệ), trong khi pipeline dùng ngưỡng chặt hơn (`min(width, height) < 12 px` cố định trong `configs/pipeline.yaml`) để tránh làm ngập hàng đợi cảnh báo bằng các box người đứng ở xa.
- **Ý nghĩa của thuộc tính `can_review` trong `cvat/labels.json`:** Người gán nhãn bật checkbox `can_review = true` trên CVAT khi gặp ca mơ hồ/khó quyết định (vật bị che khuất nặng, nhoè, hoặc giáp ranh giữa `truck` và `bus`) để đánh dấu nhờ reviewer/QA trưởng kiểm tra lại; tương ứng trong pipeline tự động, vai trò chuyển tiếp thông tin "ca nghi ngờ cần người có kinh nghiệm xem lại" này được thực hiện bởi các cờ cảnh báo `WARN` của `second_opinion` và danh sách `codes` + điểm `priority` trong file `05_review_queue.csv`.
