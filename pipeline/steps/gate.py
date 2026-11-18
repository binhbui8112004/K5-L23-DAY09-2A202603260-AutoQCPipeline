"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stems = set(image_stems)
    rev = set(reviewed or ())
    hold_th = cfg["gate"]["warn_ratio_hold"]

    errors = [i for i in issues if i.severity == ERROR]
    warn_imgs = {i.image for i in issues if i.severity == WARN and i.image in stems and i.image not in rev}
    n_img = len(stems)
    ratio = len(warn_imgs) / n_img if n_img else 0.0

    reasons = []
    if errors:
        decision = "Rework"
        reasons.append(f"còn {len(errors)} lỗi bắt buộc chưa sửa")
    elif ratio >= hold_th:
        decision = "Hold"
        reasons.append(f"{len(warn_imgs)}/{n_img} ảnh ({ratio:.1%}) còn cảnh báo >= ngưỡng {hold_th:.0%}")
    else:
        decision = "Release"
        reasons.append(f"0 lỗi bắt buộc; cảnh báo {len(warn_imgs)}/{n_img} ảnh ({ratio:.1%}) < {hold_th:.0%}")

    return dict(
        decision=decision,
        n_errors=len(errors),
        n_warn_images=len(warn_imgs),
        n_images=n_img,
        warn_ratio=round(ratio, 4),
        reasons=reasons,
    )
