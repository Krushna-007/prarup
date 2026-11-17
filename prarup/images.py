"""Checks on every figure image: resolution, duplicates, and AI evidence.

AI evidence comes in three layers, strongest first. It is evidence, never a verdict.
1. Declared: a signed C2PA manifest, or the IPTC tag "trainedAlgorithmicMedia".
2. Traces: settings a generator leaves in the file (Stable Diffusion, ComfyUI).
3. Classifier (optional install): a likelihood, run on photos only, because it
   gives false alarms on charts.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from prarup.analyze import Finding
from prarup.manuscript import Manuscript

Image.MAX_IMAGE_PIXELS = 200_000_000

COLUMN_INCHES = 3.5
MIN_DPI = 300
AI_TAGS = ("trainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia", "algorithmicMedia")
GENERATORS = ["Midjourney", "DALL-E", "DALL·E", "OpenAI", "Firefly", "Stable Diffusion", "SDXL",
              "Imagen", "Gemini", "Google Generative AI", "Leonardo.Ai", "Ideogram", "FLUX",
              "ComfyUI", "InvokeAI", "AUTOMATIC1111", "NovelAI", "Craiyon"]
CLASSIFIER = "Ateeqq/ai-vs-human-image-detector"
CHART_SHARE = 0.9            # 8 colours covering 90% of pixels means a chart, not a photo


@dataclass
class ImageReport:
    path: str
    block_id: str
    figure: int
    width_px: int = 0
    height_px: int = 0
    printed_inches: float = 0.0
    dpi: float = 0.0
    declared: str = ""        # layer 1
    traces: str = ""          # layer 2
    ai_score: float | None = None   # layer 3
    ai_note: str = ""
    duplicate_of: str = ""
    readable: bool = True
    error: str = ""

    def verdict(self) -> str:
        if self.declared:
            return "declared AI-generated"
        if self.traces:
            return "AI generator traces"
        if self.ai_score is not None and self.ai_score >= 0.8:
            return "classifier: likely AI"
        return "no AI evidence found"


# ---- layer 1: declared ----------------------------------------------------

def read_c2pa(path: Path) -> str:
    """The C2PA manifest's AI action, or "" if there is none."""
    try:
        import c2pa
        store = json.loads(c2pa.Reader(str(path)).json())
    except Exception:
        return ""
    manifest = store.get("manifests", {}).get(store.get("active_manifest", ""), {})
    signer = manifest.get("claim_generator", "")
    for info in manifest.get("claim_generator_info", []):
        signer = signer or info.get("name", "")
    for assertion in manifest.get("assertions", []):
        if assertion.get("label", "").startswith("c2pa.actions"):
            for action in assertion.get("data", {}).get("actions", []):
                source = action.get("digitalSourceType", "")
                if source.endswith(AI_TAGS):
                    what = action.get("description") or action.get("action", "")
                    state = store.get("validation_state", "not validated").lower()
                    return f"C2PA Content Credentials: {what}; signed by {signer}; signature {state}"
    return ""


def metadata_text(image: Image.Image, raw: bytes) -> str:
    """All text in the file's metadata: PNG chunks, EXIF and XMP."""
    parts = []
    for key, value in image.info.items():
        if isinstance(value, str):
            parts.append(f"{key}: {value}")
    for value in image.getexif().values():
        if isinstance(value, str):
            parts.append(value)
    for packet in re.findall(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S):
        parts.append(packet.decode("utf-8", "ignore"))
    return "\n".join(parts)


# ---- layer 2: generator traces ---------------------------------------------

def find_traces(image: Image.Image, metadata: str) -> str:
    settings = image.info.get("parameters")
    if isinstance(settings, str) and settings.strip():
        steps = re.search(r"Steps:.*", settings)
        return "Stable Diffusion settings in the PNG: " + (steps.group()[:120] if steps else settings[:80])
    if "workflow" in image.info:
        return "ComfyUI workflow embedded in the PNG"
    named = [g for g in GENERATORS if g.lower() in metadata.lower()]
    if named:
        return "metadata names a generator: " + ", ".join(named)
    return ""


# ---- layer 3: classifier (optional) ----------------------------------------

_model = None


def classifier_installed() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def ai_score(path: Path) -> float | None:
    """The classifier's probability that the image is AI-generated."""
    global _model
    if not classifier_installed():
        return None
    if _model is None:
        from transformers import pipeline
        _model = pipeline("image-classification", model=CLASSIFIER)
    with Image.open(path) as image:
        scores = _model(image.convert("RGB"))
    for s in scores:
        if s["label"].lower() in ("ai", "artificial", "fake", "ai_generated", "ai-generated"):
            return float(s["score"])
    return None


def photo_like(image: Image.Image) -> bool:
    """False for charts, diagrams and logos: few colours cover most pixels."""
    small = image.convert("RGB")
    small.thumbnail((256, 256))
    counts = {}
    for r, g, b in small.get_flattened_data():
        key = (r // 32, g // 32, b // 32)
        counts[key] = counts.get(key, 0) + 1
    top = sum(sorted(counts.values(), reverse=True)[:8])
    return top / max(1, sum(counts.values())) < CHART_SHARE


# ---- duplicates --------------------------------------------------------------

def dhash(image: Image.Image) -> int:
    """64-bit difference hash: survives resizing and recompression."""
    small = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.get_flattened_data())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def same_picture(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 4


# ---- one file, then the whole paper ----------------------------------------

def inspect_file(path: Path, classify: bool = False) -> tuple[ImageReport, int | None]:
    report = ImageReport(path=str(path), block_id="", figure=0)
    try:
        with Image.open(path) as image:
            report.width_px, report.height_px = image.size
            metadata = metadata_text(image, path.read_bytes())
            report.declared = read_c2pa(path)
            if not report.declared and any(tag in metadata for tag in AI_TAGS):
                report.declared = "IPTC DigitalSourceType says trainedAlgorithmicMedia"
            report.traces = find_traces(image, metadata)
            image.load()
            if classify:
                if photo_like(image):
                    report.ai_score = ai_score(path)
                else:
                    report.ai_note = "chart or diagram, so the classifier was not run"
            return report, dhash(image)
    except Exception as exc:
        report.readable = False
        report.error = str(exc)[:120]
        return report, None


def inspect(m: Manuscript, project: Path, classify: bool = False,
            printed: dict | None = None) -> list[ImageReport]:
    reports, hashes = [], []
    for number, fig in enumerate(m.figures(), start=1):
        share = COLUMN_INCHES * 0.98 / max(1, len(fig.images))
        for path in fig.images:
            file = project / path
            if not file.is_file() or file.suffix.lower() == ".pdf":
                continue
            report, h = inspect_file(file, classify)
            report.path, report.block_id, report.figure = path, fig.id, number
            report.printed_inches = (printed or {}).get(path, share)
            if report.width_px:
                report.dpi = report.width_px / report.printed_inches
            if h is not None:
                report.duplicate_of = next((p for p, other in hashes if same_picture(h, other)), "")
                hashes.append((path, h))
            reports.append(report)
    return reports


def findings(reports: list[ImageReport]) -> list[Finding]:
    out = []
    for r in reports:
        name = f"Fig. {r.figure} ({Path(r.path).name})"

        def add(code, severity, message):
            out.append(Finding(code, severity, f"{name} {message}", r.block_id, "Images"))

        if r.dpi and r.dpi < MIN_DPI:
            add("IMG-01", "warning", f"is {r.dpi:.0f} dpi when printed {r.printed_inches:.1f} in wide "
                f"({r.width_px} px); IEEE asks for at least {MIN_DPI}.")
        if r.declared:
            add("IMG-02", "error", f"is declared AI-generated: {r.declared}. Disclose it, or replace it.")
        elif r.traces:
            add("IMG-03", "warning", f"carries AI generator traces: {r.traces}.")
        elif r.ai_score is not None and r.ai_score >= 0.8:
            add("IMG-04", "warning", f"is rated {r.ai_score:.0%} likely AI by the classifier "
                "(a likelihood, not proof).")
        if r.duplicate_of:
            add("IMG-05", "warning", f"looks the same as {Path(r.duplicate_of).name}, used in another figure.")
        if not r.readable:
            add("IMG-06", "warning", f"could not be read: {r.error}")
    return out
