"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    c = cfg["label_format"]
    tol = c["overflow_tol"]
    min_px = c["min_box_px"]
    max_frac = c["max_box_frac"]
    dup_iou = c["dup_box_iou"]
    n_cls = len(ds.classes)
    issues = []

    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)
        seen = []
        for lineno, raw in ds.read_label_lines(stem) or []:
            try:
                cls_id, x, y, w, h = parse_yolo_line(raw)
            except ValueError as e:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem, str(e), line=lineno))
                continue

            if not (0 <= cls_id < n_cls):
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_CLASS_ID",
                        stem,
                        f"id lớp {cls_id} ngoài 0..{n_cls - 1}",
                        line=lineno,
                        extra={"class_id": cls_id},
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue("label_format", ERROR, "BOX_ZERO", stem, f"kích thước không dương w={w}, h={h}", line=lineno)
                )
                continue

            over = max(-(x - w / 2), (x + w / 2) - 1.0, -(y - h / 2), (y + h / 2) - 1.0, 0.0)
            if over > tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"box tràn mép {over:.4f}",
                        line=lineno,
                        extra={"overflow": round(over, 4)},
                    )
                )

            box = (x, y, w, h)
            if any(prev_cls == cls_id and iou_xywh(box, prev_box) > dup_iou for prev_cls, prev_box in seen):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem, "box trùng lặp cùng lớp", line=lineno))
            seen.append((cls_id, box))

            if w * h > max_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem, f"box chiếm {w * h:.1%} ảnh", line=lineno))

            if size:
                short = min(w * size[0], h * size[1])
                if short < min_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"cạnh ngắn {short:.1f}px < {min_px}px",
                            line=lineno,
                        )
                    )

    return issues
