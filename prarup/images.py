"""Image forensics for the figures of a paper.

For every image: its printed resolution, any evidence that it was made by
a generative model, and whether it duplicates another figure.

AI evidence comes in three layers, strongest first, and is reported as
evidence, never as a verdict:

1. Declared provenance: a C2PA manifest (Content Credentials) whose
   actions name a generative source, or the IPTC DigitalSourceType
   "trainedAlgorithmicMedia" in the image's XMP. Tested on a real
   Gemini-generated image signed by Google.
2. Generator traces: settings a generator writes into the file, such as
   Stable Diffusion's "parameters" PNG chunk or ComfyUI's "workflow", or a
   generator named as the creating software. Tested on a real Stable
   Diffusion image from Wikimedia Commons.
3. A classifier (optional install): a pretrained AI-or-not model run
   locally. A likelihood only: it was trained on photos and art, not
   scientific figures.

Finding nothing proves nothing: Word, screenshots and most editors strip
metadata. The report says so.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

from prarup.analyze import Finding
from prarup.manuscript import Manuscript

Image.MAX_IMAGE_PIXELS = 200_000_000          # large figures are normal; refuse only absurd ones

COLUMN_INCHES = 3.5                           # IEEE conference column
MIN_DPI = 300                                 # IEEE: photographs and colour figures
GENERATORS = [
    "Midjourney", "DALL·E", "DALL-E", "DALLE", "OpenAI", "ChatGPT", "Firefly", "Stable Diffusion",
    "StableDiffusion", "SDXL", "NovelAI", "Imagen", "Gemini", "Leonardo.Ai", "Ideogram",
    "FLUX", "ComfyUI", "InvokeAI", "AUTOMATIC1111", "NightCafe", "Craiyon", "Bing Image Creator",
    "Google Generative AI", "Adobe Firefly", "Playground AI", "Runway",
]
AI_SOURCE_TYPES = ("trainedAlgorithmicMedia", "compositeWithTrainedAlgorithmicMedia",
                   "algorithmicMedia")
CLASSIFIER = "Ateeqq/ai-vs-human-image-detector"


@dataclass
class Evidence:
    layer: int             # 1 declared, 2 generator traces, 3 classifier
    text: str


@dataclass
class ImageReport:
    path: str
    block_id: str
    figure: int                       # figure number in the paper
    width_px: int = 0
    height_px: int = 0
    format: str = ""
    printed_inches: float = 0.0
    dpi: float = 0.0
    evidence: list = field(default_factory=list)
    ai_score: float | None = None     # classifier likelihood, if it ran
    duplicate_of: str = ""
    readable: bool = True
    error: str = ""

    @property
    def verdict(self) -> str:
        layers = {e.layer for e in self.evidence}
        if 1 in layers:
            return "declared AI-generated"
        if 2 in layers:
            return "AI generator traces"
        if self.ai_score is not None and self.ai_score >= 0.8:
            return "classifier: likely AI"
        return "no AI evidence found"


# ---------------------------------------------------------------- layer 1

def _c2pa(path: Path) -> list[Evidence]:
    """Read and validate a C2PA manifest, if the file has one."""
    try:
        import c2pa
    except ImportError:
        return []
    try:
        reader = c2pa.Reader(str(path))
        store = json.loads(reader.json())
    except Exception:                       # no manifest, or not a supported format
        return []
    manifest = store.get("manifests", {}).get(store.get("active_manifest", ""), {})
    generator = manifest.get("claim_generator") or ", ".join(
        g.get("name", "") for g in manifest.get("claim_generator_info", []) if isinstance(g, dict))
    valid = store.get("validation_state", "")
    found = []
    for assertion in manifest.get("assertions", []):
        label = assertion.get("label", "")
        data = assertion.get("data", {})
        if label.startswith("c2pa.actions"):
            for action in data.get("actions", []):
                source = action.get("digitalSourceType", "")
                if source.endswith(AI_SOURCE_TYPES):
                    what = action.get("description") or action.get("action", "")
                    found.append(Evidence(1, f"C2PA Content Credentials: {what} "
                                             f"({source.rsplit('/', 1)[-1]}); signed by {generator}; "
                                             f"signature {valid.lower() or 'not validated'}"))
        if "ai-disclosure" in label or "ai_generative" in label:
            found.append(Evidence(1, f"C2PA AI disclosure assertion ({label})"))
    return found


def _metadata_text(image: Image.Image, raw: bytes) -> str:
    """Every piece of text metadata in the file: PNG chunks, EXIF, XMP."""
    parts = []
    for key, value in image.info.items():
        if isinstance(value, (str, bytes)) and key not in ("icc_profile", "exif"):
            text = value.decode("utf-8", "ignore") if isinstance(value, bytes) else value
            parts.append(f"{key}: {text}")
    try:
        for tag, value in image.getexif().items():
            if isinstance(value, (str, bytes)):
                parts.append(value.decode("utf-8", "ignore") if isinstance(value, bytes) else value)
    except Exception:
        pass
    for packet in re.findall(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S):
        parts.append(packet.decode("utf-8", "ignore"))
    return "\n".join(parts)


def _declared(metadata: str) -> list[Evidence]:
    for source in AI_SOURCE_TYPES:
        if source in metadata:
            return [Evidence(1, f"IPTC DigitalSourceType = {source} in the image's metadata")]
    return []


# ---------------------------------------------------------------- layer 2

def _traces(image: Image.Image, metadata: str) -> list[Evidence]:
    found = []
    params = image.info.get("parameters")
    if isinstance(params, str) and params.strip():
        settings = re.search(r"Steps:.*", params)
        found.append(Evidence(2, "Stable Diffusion generation settings in the PNG: "
                                 + (settings.group()[:120] if settings else params[:80])))
    if "workflow" in image.info or ("prompt" in image.info and "{" in str(image.info["prompt"])):
        found.append(Evidence(2, "ComfyUI workflow embedded in the PNG"))
    named = sorted({g for g in GENERATORS if re.search(re.escape(g), metadata, re.I)})
    if named and not found:
        found.append(Evidence(2, "Metadata names a generator: " + ", ".join(named)))
    return found


# ---------------------------------------------------------------- layer 3

_pipeline = None


def classifier_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def ai_likelihood(path: Path) -> float | None:
    """Probability the classifier gives for "AI-generated", or None if not installed."""
    global _pipeline
    if not classifier_available():
        return None
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline("image-classification", model=CLASSIFIER)
    with Image.open(path) as im:
        scores = _pipeline(im.convert("RGB"))
    for s in scores:
        if s["label"].lower() in ("ai", "artificial", "fake", "ai_generated", "ai-generated"):
            return float(s["score"])
    return None


# ---------------------------------------------------------------- duplicates

def dhash(image: Image.Image) -> int:
    """64-bit difference hash: survives resizing and recompression."""
    small = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def _close(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 4


# ---------------------------------------------------------------- report

def inspect_file(path: Path) -> tuple[ImageReport, int | None]:
    """Everything about one image file, plus its hash (None if unreadable)."""
    report = ImageReport(path=str(path), block_id="", figure=0)
    try:
        raw = path.read_bytes()
        with Image.open(path) as image:
            report.width_px, report.height_px = image.size
            report.format = image.format or path.suffix.lstrip(".").upper()
            metadata = _metadata_text(image, raw)
            report.evidence = _c2pa(path) or _declared(metadata)
            report.evidence += _traces(image, metadata)
            image.load()
            return report, dhash(image)
    except Exception as exc:                        # PDF figures, EMF, damaged files
        report.readable = False
        report.error = str(exc)[:120]
        return report, None


def inspect(m: Manuscript, project: Path, classify: bool = False,
            printed: dict | None = None) -> list[ImageReport]:
    """Report on every figure image. printed maps path -> printed width in inches."""
    reports, hashes = [], []
    for number, fig in enumerate(m.figures(), start=1):
        share = COLUMN_INCHES * 0.98 / max(1, len(fig.images))
        for path in fig.images:
            file = project / path
            if not file.is_file():
                continue
            if file.suffix.lower() == ".pdf":       # vector: resolution does not apply
                continue
            report, h = inspect_file(file)
            report.path, report.block_id, report.figure = path, fig.id, number
            report.printed_inches = (printed or {}).get(path, share)
            if report.width_px and report.printed_inches:
                report.dpi = report.width_px / report.printed_inches
            if classify and report.readable:
                report.ai_score = ai_likelihood(file)
            if h is not None:
                twin = next((p for p, other in hashes if _close(h, other)), "")
                report.duplicate_of = twin
                hashes.append((path, h))
            reports.append(report)
    return reports


def findings(reports: list[ImageReport]) -> list[Finding]:
    out = []
    for r in reports:
        name = f"Fig. {r.figure} ({Path(r.path).name})"
        if r.dpi and r.dpi < MIN_DPI:
            out.append(Finding("IMG-01", "warning",
                               f"{name}: {r.dpi:.0f} dpi when printed {r.printed_inches:.1f} in wide "
                               f"({r.width_px} px); IEEE asks for at least {MIN_DPI}.", r.block_id, "Images"))
        layers = {e.layer for e in r.evidence}
        if 1 in layers:
            out.append(Finding("IMG-02", "error", f"{name} is declared AI-generated: "
                               + next(e.text for e in r.evidence if e.layer == 1)
                               + ". Disclose it, or replace it.", r.block_id, "Images"))
        elif 2 in layers:
            out.append(Finding("IMG-03", "warning", f"{name} carries AI generator traces: "
                               + next(e.text for e in r.evidence if e.layer == 2) + ".",
                               r.block_id, "Images"))
        if r.ai_score is not None and r.ai_score >= 0.8 and not layers:
            out.append(Finding("IMG-04", "warning", f"{name}: the classifier rates it {r.ai_score:.0%} "
                               "likely AI-generated (a likelihood, not proof; it was trained on photos "
                               "and art, not figures).", r.block_id, "Images"))
        if r.duplicate_of:
            out.append(Finding("IMG-05", "warning", f"{name} looks the same as "
                               f"{Path(r.duplicate_of).name}, used in another figure.", r.block_id, "Images"))
        if not r.readable:
            out.append(Finding("IMG-06", "warning", f"{name} could not be read: {r.error}",
                               r.block_id, "Images"))
    return out
