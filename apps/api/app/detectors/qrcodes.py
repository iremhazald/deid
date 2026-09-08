from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pymupdf

from app.domain.models import DetectionMethod, EntityCandidate, EntityType, ManualRect

DETECTOR_NAME = "QR_CODE_VISUAL"
RENDER_SCALE = 2.0
PAD_PTS = 6.0
MERGE_IOU = 0.45
MAX_PAGE_SHARE = 0.22
MAX_UNDECODED_PAGE_SHARE = 0.12
MAX_DETECT_EDGE = 1400
MIN_IMAGE_EDGE = 40
# Payload-bearing boxes keep the existing wide aspect window.
MIN_DECODED_ASPECT = 0.45
MAX_DECODED_ASPECT = 2.2
# Undecoded candidates need near-square, regular-quad evidence.
MIN_UNDECODED_ASPECT = 0.72
MAX_UNDECODED_ASPECT = 1.40
MAX_UNDECODED_SIDE_RATIO = 1.25
MAX_UNDECODED_ANGLE_DEV = 12.0
# Dense legal body text inside a clip is never a QR, even if OpenCV "decodes".
_BODY_TEXT_WORD = re.compile(r"[A-Za-zÀ-ÿİıĞğÜüŞşÖöÇç]{2,}")
MIN_BODY_TEXT_WORDS = 1
# Printed codes sit well under 4cm. Taller body-text quads are false positives.
MAX_QR_EDGE = 130.0

_OPEN_ERRORS = (OSError, ValueError, RuntimeError)
_CV_ERRORS = (TypeError, ValueError, AttributeError, RuntimeError, OSError)


def detect_qrcodes(source_path: Path, document_text: str) -> list[EntityCandidate]:
    """Find QR codes on a PDF by decoding embedded images, then the page render.

    Only real detections with a plausible locator box are returned.
    """
    cv2, np = _opencv()
    if cv2 is None or np is None:
        return []
    detector = _make_qr_detector(cv2)
    if detector is None:
        return []
    document = None
    try:
        document = pymupdf.open(str(source_path))
        found: list[tuple[int, ManualRect, str]] = []
        for page_number in range(document.page_count):
            page = document[page_number]
            boxes = _detect_on_embedded_images(cv2, np, detector, page)
            if not boxes:
                boxes = _detect_on_page(cv2, np, detector, page)
            accepted = [
                (rect, payload)
                for rect, payload, points in boxes
                if _accept_qr_candidate(rect, page.rect, payload, points, page=page)
            ]
            for rect, payload in _merge_boxes(accepted):
                if not _rect_is_plausible(rect, page.rect, decoded=bool(payload.strip())):
                    continue
                found.append((page_number, rect, payload))
        return [
            _to_entity(document_text, index, page, rect, payload)
            for index, (page, rect, payload) in enumerate(found)
        ]
    except _OPEN_ERRORS:
        return []
    except _CV_ERRORS:
        return []
    finally:
        if document is not None:
            document.close()


def _opencv() -> tuple[Any, Any] | tuple[None, None]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None, None
    return cv2, np


def _make_qr_detector(cv2: Any) -> Any | None:
    """Instantiate OpenCV's QR detector without calling a stub-typed factory."""
    qr_cls: Any = getattr(cv2, "QRCodeDetector", None)
    if qr_cls is None:
        return None
    try:
        detector: Any = type.__call__(qr_cls) if isinstance(qr_cls, type) else qr_cls
    except TypeError:
        detector = qr_cls
    if detector is None:
        return None
    if not (hasattr(detector, "detectAndDecode") or hasattr(detector, "detect")):
        return None
    return detector


def _detect_on_page(
    cv2: Any, np: Any, detector: Any, page: pymupdf.Page
) -> list[tuple[ManualRect, str, Any]]:
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
    image = _pixmap_to_bgr(cv2, np, pixmap)
    if image is None:
        return []
    hits: list[tuple[ManualRect, str, Any]] = []
    for points, payload in _decode_qr_boxes(cv2, detector, image):
        rect = _points_to_page_rect(points, RENDER_SCALE, page.rect)
        if rect is not None:
            hits.append((rect, payload, points))
    return hits


def _detect_on_embedded_images(
    cv2: Any, np: Any, detector: Any, page: pymupdf.Page
) -> list[tuple[ManualRect, str, Any]]:
    hits: list[tuple[ManualRect, str, Any]] = []
    page_area = max(1.0, page.rect.width * page.rect.height)
    try:
        images = page.get_images(full=True)
    except _OPEN_ERRORS:
        return []
    for image_info in images:
        xref = int(image_info[0])
        document = page.parent
        if document is None:
            continue
        try:
            extracted = document.extract_image(xref)
        except _OPEN_ERRORS:
            continue
        data = extracted.get("image") if extracted else None
        if not data:
            continue
        decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), getattr(cv2, "IMREAD_COLOR", 1))
        if decoded is None:
            continue
        height, width = decoded.shape[:2]
        if min(height, width) < MIN_IMAGE_EDGE:
            continue
        try:
            placements = list(page.get_image_rects(xref) or [])
        except _OPEN_ERRORS:
            continue
        if not placements:
            continue
        qr_hits = _decode_qr_boxes(cv2, detector, decoded)
        if not qr_hits:
            continue
        for placement in placements:
            image_share = (placement.width * placement.height) / page_area
            placement_rect = _clamp_rect(placement, page.rect)
            payload = next((item[1] for item in qr_hits if item[1]), qr_hits[0][1])
            if (
                image_share <= 0.12
                and _rect_is_plausible(placement_rect, page.rect, decoded=bool(payload.strip()))
            ):
                if placement_rect is not None:
                    points = next((item[0] for item in qr_hits if item[1]), qr_hits[0][0])
                    hits.append((placement_rect, payload, points))
                continue
            for points, payload in qr_hits:
                mapped = _map_image_points(points, width, height, placement, page.rect)
                if mapped is not None:
                    hits.append((mapped, payload, points))
    return hits


def _decode_qr_boxes(cv2: Any, detector: Any, image: Any) -> list[tuple[Any, str]]:
    resized, inv_scale = _fit_for_detect(cv2, image)
    results = _read_qr_boxes(detector, resized, inv_scale)
    if results:
        return results
    inverted = _invert(cv2, resized)
    if inverted is None:
        return []
    return _read_qr_boxes(detector, inverted, inv_scale)


def _read_qr_boxes(detector: Any, image: Any, inv_scale: float) -> list[tuple[Any, str]]:
    results = _try_detect_multi(detector, image)
    if not results:
        points, payload = _try_detect_single(detector, image)
        if points is not None:
            results = [(points, payload)]
    if inv_scale == 1.0:
        return results
    scaled: list[tuple[Any, str]] = []
    for points, payload in results:
        scaled.append((_scale_points(points, inv_scale), payload))
    return scaled


def _try_detect_multi(detector: Any, image: Any) -> list[tuple[Any, str]]:
    try:
        _ok, payloads, points, _straight = detector.detectAndDecodeMulti(image)
    except _CV_ERRORS:
        return []
    rows: list[tuple[Any, str]] = []
    for index, quad in enumerate(_iter_quads(points)):
        payload = ""
        if payloads is not None and index < len(payloads):
            payload = str(payloads[index] or "")
        rows.append((quad, payload))
    return rows


def _try_detect_single(detector: Any, image: Any) -> tuple[Any | None, str]:
    try:
        payload, points, _straight = detector.detectAndDecode(image)
        quads = _iter_quads(points)
        if quads:
            return quads[0], str(payload or "")
    except _CV_ERRORS:
        pass
    try:
        found, points = detector.detect(image)
        quads = _iter_quads(points)
        if found and quads:
            return quads[0], ""
    except _CV_ERRORS:
        pass
    return None, ""


def _fit_for_detect(cv2: Any, image: Any) -> tuple[Any, float]:
    height, width = image.shape[:2]
    edge = max(height, width)
    if edge <= MAX_DETECT_EDGE:
        return image, 1.0
    scale = MAX_DETECT_EDGE / edge
    resized = cv2.resize(
        image,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=getattr(cv2, "INTER_AREA", 3),
    )
    return resized, 1.0 / scale


def _invert(cv2: Any, image: Any) -> Any | None:
    invert = getattr(cv2, "bitwise_not", None)
    if invert is None:
        return None
    try:
        return invert(image)
    except _CV_ERRORS:
        return None


def _pixmap_to_bgr(cv2: Any, np: Any, pixmap: pymupdf.Pixmap) -> Any | None:
    try:
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.h, pixmap.w, pixmap.n)
    except (ValueError, TypeError):
        return None
    if pixmap.n == 4:
        return cv2.cvtColor(image, getattr(cv2, "COLOR_RGBA2BGR", 2))
    if pixmap.n == 3:
        return cv2.cvtColor(image, getattr(cv2, "COLOR_RGB2BGR", 4))
    if pixmap.n == 1:
        return cv2.cvtColor(image, getattr(cv2, "COLOR_GRAY2BGR", 8))
    return None


def _iter_quads(points: Any) -> list[Any]:
    if points is None:
        return []
    try:
        import numpy as np

        array = np.asarray(points, dtype=float)
    except (TypeError, ValueError):
        return []
    if array.size == 0:
        return []
    if array.ndim == 3 and array.shape[-1] == 2 and array.shape[-2] == 4:
        return [quad for quad in array]
    if array.ndim == 2 and array.shape == (4, 2):
        return [array]
    if array.size >= 8 and array.size % 8 == 0:
        return list(array.reshape(-1, 4, 2))
    return []


def _scale_points(points: Any, factor: float) -> Any:
    return [[float(point[0]) * factor, float(point[1]) * factor] for point in points]


def _points_to_page_rect(points: Any, scale: float, page_rect: pymupdf.Rect) -> ManualRect | None:
    xs = [float(point[0]) / scale for point in points]
    ys = [float(point[1]) / scale for point in points]
    if not xs or not ys:
        return None
    return _clamp_rect(
        pymupdf.Rect(min(xs) - PAD_PTS, min(ys) - PAD_PTS, max(xs) + PAD_PTS, max(ys) + PAD_PTS),
        page_rect,
    )


def _map_image_points(
    points: Any,
    image_w: int,
    image_h: int,
    placement: pymupdf.Rect,
    page_rect: pymupdf.Rect,
) -> ManualRect | None:
    width = max(1, image_w)
    height = max(1, image_h)
    xs = [placement.x0 + (float(point[0]) / width) * placement.width for point in points]
    ys = [placement.y0 + (float(point[1]) / height) * placement.height for point in points]
    if not xs or not ys:
        return None
    return _clamp_rect(
        pymupdf.Rect(min(xs) - PAD_PTS, min(ys) - PAD_PTS, max(xs) + PAD_PTS, max(ys) + PAD_PTS),
        page_rect,
    )


def _clamp_rect(rect: pymupdf.Rect, bounds: pymupdf.Rect) -> ManualRect | None:
    padded = pymupdf.Rect(rect)
    if padded.width < 12:
        padded.x1 = padded.x0 + 12
    if padded.height < 12:
        padded.y1 = padded.y0 + 12
    clipped = padded & bounds
    if clipped.is_empty or clipped.width < 8 or clipped.height < 8:
        return None
    return ManualRect(
        x0=float(clipped.x0),
        y0=float(clipped.y0),
        x1=float(clipped.x1),
        y1=float(clipped.y1),
    )


def _rect_metrics(rect: ManualRect, page_rect: pymupdf.Rect) -> tuple[float, float, float, float]:
    width = max(0.0, rect.x1 - rect.x0)
    height = max(0.0, rect.y1 - rect.y0)
    page_area = max(1.0, page_rect.width * page_rect.height)
    share = (width * height) / page_area
    ratio = width / height if height else 0.0
    return width, height, share, ratio


def _quad_regularity(points: Any) -> tuple[float, float] | None:
    """Return (longest/shortest side, max |angle-90|) for a 4-corner quad."""
    try:
        pts = [(float(point[0]), float(point[1])) for point in points]
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) != 4:
        return None
    sides = [
        math.hypot(pts[(index + 1) % 4][0] - pts[index][0], pts[(index + 1) % 4][1] - pts[index][1])
        for index in range(4)
    ]
    if min(sides) <= 0:
        return None
    side_ratio = max(sides) / min(sides)
    deviations: list[float] = []
    for index in range(4):
        ax = pts[(index - 1) % 4][0] - pts[index][0]
        ay = pts[(index - 1) % 4][1] - pts[index][1]
        bx = pts[(index + 1) % 4][0] - pts[index][0]
        by = pts[(index + 1) % 4][1] - pts[index][1]
        na = math.hypot(ax, ay)
        nb = math.hypot(bx, by)
        if not na or not nb:
            return None
        cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
        deviations.append(abs(math.degrees(math.acos(cosine)) - 90.0))
    return side_ratio, max(deviations)


def _rect_is_plausible(
    rect: ManualRect | None,
    page_rect: pymupdf.Rect,
    *,
    decoded: bool = True,
) -> bool:
    if rect is None:
        return False
    width, height, share, ratio = _rect_metrics(rect, page_rect)
    if width < 10 or height < 10:
        return False
    if share > MAX_PAGE_SHARE:
        return False
    if decoded:
        return MIN_DECODED_ASPECT <= ratio <= MAX_DECODED_ASPECT
    # Undecoded body-text quads are large. Printed codes stay compact.
    if max(width, height) > MAX_QR_EDGE:
        return False
    if share > MAX_UNDECODED_PAGE_SHARE:
        return False
    return MIN_UNDECODED_ASPECT <= ratio <= MAX_UNDECODED_ASPECT


def _payload_is_decoded(payload: str) -> bool:
    """True for a compact QR token. Body-text fragments are not payloads."""
    text = (payload or "").strip()
    if not text or any(char.isspace() for char in text):
        return False
    folded = text.casefold()
    if folded.startswith(("http://", "https://", "www.")):
        return True
    if len(text) < 8 or len(text) > 180:
        return False
    if not re.fullmatch(r"[A-Za-z0-9._+/=-]+", text):
        return False
    # OpenCV often "decodes" a run of letters from justified prose.
    if text.isalpha():
        return False
    return True


def _clip_has_body_text(page: pymupdf.Page, rect: ManualRect) -> bool:
    """True when the locator box sits on extractable paragraph text, not an image."""
    width = max(0.0, rect.x1 - rect.x0)
    height = max(0.0, rect.y1 - rect.y0)
    inset = min(PAD_PTS, max(2.0, min(width, height) * 0.12))
    clip = pymupdf.Rect(rect.x0 + inset, rect.y0 + inset, rect.x1 - inset, rect.y1 - inset)
    if clip.width < 8 or clip.height < 8:
        clip = pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    try:
        words = page.get_text("words", clip=clip) or []
    except _OPEN_ERRORS:
        try:
            text = page.get_text("text", clip=clip) or ""
        except _OPEN_ERRORS:
            return False
        return len(_BODY_TEXT_WORD.findall(text)) >= MIN_BODY_TEXT_WORDS
    return len(words) >= MIN_BODY_TEXT_WORDS


def _accept_qr_candidate(
    rect: ManualRect | None,
    page_rect: pymupdf.Rect,
    payload: str,
    points: Any = None,
    page: pymupdf.Page | None = None,
) -> bool:
    """Layered QR acceptance. Precision beats recall for undecoded visual hits.

    Tier A — decoded payload: accept when geometry is merely sane *and* the
    clip is not a paragraph of extractable body text.
    Tier B — no payload: accept only with strong near-square regular-quad evidence.
    Tier C — no payload + weak / huge / skewed body-text geometry: ignore.
    """
    if page is not None and rect is not None and _clip_has_body_text(page, rect):
        return False
    decoded = _payload_is_decoded(payload)
    if not _rect_is_plausible(rect, page_rect, decoded=decoded):
        return False
    if decoded:
        return True
    regularity = _quad_regularity(points) if points is not None else None
    if regularity is None:
        return False
    side_ratio, angle_dev = regularity
    return side_ratio <= MAX_UNDECODED_SIDE_RATIO and angle_dev <= MAX_UNDECODED_ANGLE_DEV


def _merge_boxes(boxes: list[tuple[ManualRect, str]]) -> list[tuple[ManualRect, str]]:
    merged: list[tuple[ManualRect, str]] = []
    for rect, payload in boxes:
        overlap_index = next(
            (index for index, (other, _) in enumerate(merged) if _iou(rect, other) >= MERGE_IOU),
            None,
        )
        if overlap_index is None:
            merged.append((rect, payload))
            continue
        other, other_payload = merged[overlap_index]
        merged[overlap_index] = (
            ManualRect(
                x0=min(rect.x0, other.x0),
                y0=min(rect.y0, other.y0),
                x1=max(rect.x1, other.x1),
                y1=max(rect.y1, other.y1),
            ),
            payload or other_payload,
        )
    return merged


def _iou(left: ManualRect, right: ManualRect) -> float:
    x0 = max(left.x0, right.x0)
    y0 = max(left.y0, right.y0)
    x1 = min(left.x1, right.x1)
    y1 = min(left.y1, right.y1)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    if inter <= 0:
        return 0.0
    area = (left.x1 - left.x0) * (left.y1 - left.y0) + (right.x1 - right.x0) * (right.y1 - right.y0) - inter
    return inter / area if area > 0 else 0.0


def _to_entity(
    document_text: str,
    index: int,
    page: int,
    rect: ManualRect,
    payload: str,
) -> EntityCandidate:
    start = len(document_text) + 1000 + index * 4
    label = payload.strip()[:200] if payload and payload.strip() else "[KAREKOD]"
    return EntityCandidate(
        text=label,
        type=EntityType.QR_CODE,
        start=start,
        end=start + 1,
        page=page,
        detector=DETECTOR_NAME,
        method=DetectionMethod.DETERMINISTIC,
        validated=bool(payload.strip()),
        confidence=0.95 if payload.strip() else 0.8,
        reason="QR code detected on the page.",
        rectangles=[rect],
    )
