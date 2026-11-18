"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_LINE = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMG = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip_line(text: str) -> str | None:
    cls_id, x, y, w, h = parse_yolo_line(text)
    x1, y1 = max(0.0, min(1.0, x - w / 2)), max(0.0, min(1.0, y - h / 2))
    x2, y2 = max(0.0, min(1.0, x + w / 2)), max(0.0, min(1.0, y + h / 2))
    nw, nh = x2 - x1, y2 - y1
    if nw <= 0 or nh <= 0:
        return None
    return f"{cls_id} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {nw:.6f} {nh:.6f}"


def fix(ds, issues, cfg):
    fixes = []
    removed_imgs = set()
    by_file: dict[str, dict[int, str]] = defaultdict(dict)
    renamed = False

    for i in issues:
        if i.severity != ERROR:
            continue
        if i.code in REMOVE_IMG and i.image not in removed_imgs:
            ip, lp = ds.image_path(i.image), ds.label_path(i.image)
            if ip and ip.exists():
                ip.unlink()
            if lp.exists():
                lp.unlink()
            removed_imgs.add(i.image)
            fixes.append(dict(image=i.image, line="", action="remove_image", before=i.code, after="deleted"))
        elif i.code == "BAD_CLASS_NAME" and ds.yaml_path.exists() and not renamed:
            d = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
            before = str(d.get("names"))
            d["names"] = {idx: name for idx, name in enumerate(cfg["classes"])}
            ds.yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")
            renamed = True
            fixes.append(dict(image="data.yaml", line="", action="rename_classes", before=before, after=str(d["names"])))
        elif i.code == "MISSING_LABEL_FILE":
            fixes.append(dict(image=i.image, line="", action="needs_label", before="(không có file)", after="chuyển người gán"))
        elif i.code in DROP_LINE and i.line:
            by_file[i.image][i.line] = "drop"
        elif i.code == "BOX_OUT_OF_IMAGE" and i.line:
            by_file[i.image].setdefault(i.line, "clip")

    for stem, actions in sorted(by_file.items()):
        if stem in removed_imgs:
            continue
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        kept = []
        for lineno, raw in enumerate(raw_lines, 1):
            act = actions.get(lineno)
            if act == "drop":
                fixes.append(dict(image=stem, line=lineno, action="drop_line", before=raw, after=""))
            elif act == "clip":
                clipped = _clip_line(raw)
                if clipped is None:
                    fixes.append(dict(image=stem, line=lineno, action="drop_line", before=raw, after=""))
                else:
                    kept.append(clipped)
                    fixes.append(dict(image=stem, line=lineno, action="clip_box", before=raw, after=clipped))
            else:
                kept.append(raw)
        lp.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    return fixes
