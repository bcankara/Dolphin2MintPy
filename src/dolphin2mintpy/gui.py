"""
Tkinter-based graphical interface for Dolphin2MintPy.

Replaces the terminal wizard with a point-and-click form where users select
directories and files via native file-chooser dialogs. Designed for Linux
desktops (GNOME, KDE, XFCE) but works anywhere Tk is available.

Features:
    - Directory / file pickers for every path parameter
    - Per-field "?" help icons that reveal tooltips on hover
    - Reference date auto-detection from baseline directory
    - Load / Save settings to dolphin2mintpy_settings.json
    - Background worker thread so the UI stays responsive
    - Progress bar and scrollable log of generator output
"""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from dolphin2mintpy.config import generate_mintpy_config
from dolphin2mintpy.metadata import auto_detect_ref_date, count_files
from dolphin2mintpy.prepare import prepare_stack
from dolphin2mintpy.settings import (
    SETTINGS_FILENAME,
    find_settings_file,
    load_settings,
    save_settings,
)

logger = logging.getLogger(__name__)


# --- Field definitions ---------------------------------------------------
#
# Each entry describes one input row rendered in the form. ``kind`` controls
# the picker widget ("dir" -> directory chooser, "file" -> file chooser,
# "text" -> free text). ``required`` is only enforced at run-time validation.
FIELDS = [
    {
        "key": "unw_dir",
        "label": "Unwrapped directory",
        "kind": "dir",
        "required": True,
        "help": (
            "Directory containing the unwrapped interferograms (*.unw.tif) "
            "produced by Dolphin/SNAPHU.\n\n"
            "Required. File names must follow the YYYYMMDD_YYYYMMDD.unw.tif "
            "pattern so reference/secondary dates can be parsed."
        ),
    },
    {
        "key": "cor_dir",
        "label": "Coherence directory",
        "kind": "dir",
        "required": False,
        "help": (
            "Directory containing coherence rasters (*.cor.tif or "
            "*.int.cor.tif).\n\n"
            "Optional. If left blank the unwrapped directory is used."
        ),
    },
    {
        "key": "baseline_dir",
        "label": "Baseline directory",
        "kind": "dir",
        "required": False,
        "help": (
            "ISCE2 baseline directory containing YYYYMMDD_YYYYMMDD/ "
            "sub-folders with baseline text files.\n\n"
            "Used to compute perpendicular baseline (Bperp). Optional: if "
            "omitted, Bperp is set to 0 for every pair."
        ),
    },
    {
        "key": "ref_xml",
        "label": "Reference XML",
        "kind": "file",
        "required": False,
        "help": (
            "ISCE2 reference product XML, e.g. reference/IW1.xml or "
            "reference/IW2.xml.\n\n"
            "Used to extract radar metadata (wavelength, heading, "
            "incidence angle). If omitted, default Sentinel-1 values are "
            "used as a fallback."
        ),
    },
    {
        "key": "ref_date",
        "label": "Reference date",
        "kind": "text",
        "required": False,
        "help": (
            "Reference (super-master) acquisition date in YYYYMMDD format, "
            "e.g. 20240919.\n\n"
            "Use the 'Auto-detect' button to infer it from the baseline "
            "directory."
        ),
    },
    {
        "key": "geometry_dir",
        "label": "Geometry directory",
        "kind": "dir",
        "required": False,
        "help": (
            "Directory containing DEM, incidence angle and azimuth angle "
            "rasters.\n\n"
            "Optional helper: when set, the DEM / incidence / azimuth / "
            "lookup file fields below are auto-populated from this folder "
            "if matching files (hgt.rdr.full, los.rdr.full, lat.rdr.full, "
            "lon.rdr.full) exist."
        ),
    },
    {
        "key": "dem_file",
        "label": "DEM file",
        "kind": "file",
        "required": False,
        "help": (
            "Path to the DEM file used by MintPy — typically "
            "hgt.rdr.full produced by ISCE2 topsStack.\n\n"
            "Written to mintpy.load.demFile."
        ),
    },
    {
        "key": "inc_angle_file",
        "label": "Incidence angle file",
        "kind": "file",
        "required": False,
        "help": (
            "Path to the incidence angle raster — typically "
            "los.rdr.full (band 1) produced by ISCE2.\n\n"
            "Written to mintpy.load.incAngleFile."
        ),
    },
    {
        "key": "az_angle_file",
        "label": "Azimuth angle file",
        "kind": "file",
        "required": False,
        "help": (
            "Path to the azimuth angle raster — typically the same "
            "los.rdr.full file used for the incidence angle.\n\n"
            "Written to mintpy.load.azAngleFile."
        ),
    },
    {
        "key": "lookup_y_file",
        "label": "Lookup Y (latitude) file",
        "kind": "file",
        "required": False,
        "help": (
            "Latitude lookup table — typically ISCE2 lat.rdr.full.\n\n"
            "Required when the stack is in radar geometry so MintPy can "
            "geocode results. Written to mintpy.load.lookupYFile.\n"
            "Skipping this leads to 'No lookup table found' errors."
        ),
    },
    {
        "key": "lookup_x_file",
        "label": "Lookup X (longitude) file",
        "kind": "file",
        "required": False,
        "help": (
            "Longitude lookup table — typically ISCE2 lon.rdr.full.\n\n"
            "Required when the stack is in radar geometry so MintPy can "
            "geocode results. Written to mintpy.load.lookupXFile."
        ),
    },
    {
        "key": "water_mask_file",
        "label": "Water mask file",
        "kind": "file",
        "required": False,
        "help": (
            "Optional water mask raster.\n\n"
            "Written to mintpy.load.waterMaskFile. Leave empty for 'auto'."
        ),
    },
    {
        "key": "mintpy_processor",
        "label": "MintPy processor",
        "kind": "choice",
        "required": False,
        "default": "isce",
        "choices": ("isce", "hyp3"),
        "help": (
            "Value written to mintpy.load.processor:\n\n"
            "  - isce: recommended when geometry files are ISCE2 "
            "*.rdr.full outputs (hybrid ISCE2 / Dolphin pipeline).\n"
            "  - hyp3: use when every input (ifgs + geometry) is a "
            "geocoded HyP3-style GeoTIFF.\n\n"
            "Note: this is independent of the PROCESSOR field inside "
            "the .rsc sidecars, which dolphin2mintpy always writes as "
            "'hyp3' to trigger MintPy's GDAL reader for Dolphin TIFFs."
        ),
    },
    {
        "key": "work_dir",
        "label": "MintPy output directory",
        "kind": "dir_new",
        "required": True,
        "default": "./mintpy",
        "help": (
            "Working directory where mintpy_config.txt will be written.\n\n"
            "Will be created if it does not exist. Default: ./mintpy"
        ),
    },
    {
        "key": "geometry_mode",
        "label": "Geometry mode",
        "kind": "choice",
        "required": False,
        "default": "auto",
        "choices": ("auto", "radar", "geo"),
        "help": (
            "Controls whether .rsc files are written as radar or "
            "geocoded metadata:\n\n"
            "  - auto:  detect from the GeoTIFF (default).\n"
            "  - radar: force radar geometry. Use when Dolphin GeoTIFFs "
            "have no CRS (Origin=0,0 / Pixel=1,1). MintPy will then "
            "produce geometryRadar.h5.\n"
            "  - geo:   force geocoded output. MintPy will expect "
            "geometryGeo.h5.\n\n"
            "If you hit a 'geometryGeo.h5 not found' error after running, "
            "switch to 'radar'."
        ),
    },
]


# Common filename patterns for auto-populating geometry file fields
# from a selected geometry directory. Order matters: first match wins.
GEOMETRY_AUTOFILL = {
    "dem_file": ("hgt.rdr.full", "hgt.rdr", "*dem*.rdr.full", "*dem*.tif", "*height*.rdr.full"),
    "inc_angle_file": ("los.rdr.full", "los.rdr", "*inc*.rdr.full", "*incidence*.tif"),
    "az_angle_file": ("los.rdr.full", "los.rdr", "*az*.rdr.full", "*azimuth*.tif"),
    "lookup_y_file": ("lat.rdr.full", "lat.rdr", "lat.tif"),
    "lookup_x_file": ("lon.rdr.full", "lon.rdr", "lon.tif"),
    "water_mask_file": ("waterMask.rdr.full", "water_mask.tif", "*water*.tif"),
}


# ========================================================================
# Tooltip helper
# ========================================================================
class Tooltip:
    """Lightweight tooltip that appears on hover.

    A small borderless Toplevel window is shown near the mouse cursor after
    a short delay. It is destroyed as soon as the pointer leaves the widget
    or the widget is clicked.
    """

    BG = "#ffffe0"
    FG = "#222222"
    BORDER = "#999999"
    DELAY_MS = 400
    WRAP_PX = 340

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_geometry(f"+{x}+{y}")
        tip.configure(bg=self.BORDER)

        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background=self.BG,
            foreground=self.FG,
            relief="flat",
            borderwidth=0,
            wraplength=self.WRAP_PX,
            padx=8,
            pady=6,
            font=("TkDefaultFont", 9),
        )
        label.pack(padx=1, pady=1)
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


# ========================================================================
# Main application
# ========================================================================
class Dolphin2MintPyApp(tk.Tk):
    """Main application window."""

    PAD = 6

    def __init__(self) -> None:
        super().__init__()
        self.title("Dolphin2MintPy")
        self.geometry("820x900")
        self.minsize(720, 760)

        self._entries: dict[str, tk.StringVar] = {}
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._build_style()
        self._build_widgets()
        self._preload_settings()

        self.after(120, self._drain_log_queue)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Help.TLabel", foreground="#1565c0", font=("TkDefaultFont", 9, "bold"))
        style.configure("Hint.TLabel", foreground="#666666", font=("TkDefaultFont", 8))
        style.configure("Heading.TLabel", font=("TkDefaultFont", 13, "bold"))
        style.configure("SubHeading.TLabel", foreground="#555555")

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Dolphin2MintPy", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Bridge Dolphin InSAR GeoTIFF outputs to MintPy format.",
            style="SubHeading.TLabel",
        ).pack(anchor="w")

        form = ttk.LabelFrame(outer, text="  Inputs  ", padding=10)
        form.pack(fill="x", pady=(0, 8))
        form.columnconfigure(1, weight=1)

        for row, field in enumerate(FIELDS):
            self._build_field_row(form, row, field)

        action_bar = ttk.Frame(outer)
        action_bar.pack(fill="x", pady=(0, 8))

        load_btn = ttk.Button(action_bar, text="Load settings", command=self._load_settings_clicked)
        load_btn.pack(side="left")
        Tooltip(load_btn, f"Load previously saved settings from {SETTINGS_FILENAME}.")

        save_btn = ttk.Button(action_bar, text="Save settings", command=self._save_settings_clicked)
        save_btn.pack(side="left", padx=(6, 0))
        Tooltip(save_btn, f"Save the current form values to {SETTINGS_FILENAME} for future runs.")

        self.run_btn = ttk.Button(action_bar, text="Run", command=self._run_clicked)
        self.run_btn.pack(side="right")
        Tooltip(self.run_btn, "Generate .rsc sidecar files and write the MintPy configuration.")

        quit_btn = ttk.Button(action_bar, text="Quit", command=self.destroy)
        quit_btn.pack(side="right", padx=(0, 6))

        progress_frame = ttk.Frame(outer)
        progress_frame.pack(fill="x", pady=(0, 6))
        self.progress = ttk.Progressbar(progress_frame, mode="determinate", maximum=100)
        self.progress.pack(fill="x")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(progress_frame, textvariable=self.status_var, style="Hint.TLabel").pack(
            anchor="w", pady=(2, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="  Log  ", padding=6)
        log_frame.pack(fill="both", expand=True)
        self.log = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            state="disabled",
            wrap="word",
            font=("TkFixedFont", 9),
        )
        self.log.pack(fill="both", expand=True)

    def _build_field_row(self, parent: ttk.Frame, row: int, field: dict) -> None:
        """Render one labelled input row with picker + help icon."""
        key = field["key"]
        required = field.get("required", False)

        label_text = field["label"] + ("  *" if required else "")
        lbl = ttk.Label(parent, text=label_text)
        lbl.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)

        var = tk.StringVar(value=field.get("default", ""))
        self._entries[key] = var

        kind = field["kind"]
        if kind == "choice":
            entry = ttk.Combobox(
                parent,
                textvariable=var,
                values=list(field.get("choices", ())),
                state="readonly",
            )
        else:
            entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", pady=4)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=2, sticky="e", padx=(6, 0), pady=4)

        if kind == "dir" or kind == "dir_new":
            browse = ttk.Button(
                button_frame, text="Browse...", width=10,
                command=lambda k=key, must_exist=(kind == "dir"): self._browse_dir(k, must_exist),
            )
            browse.pack(side="left")
            Tooltip(browse, "Open a directory picker.")
        elif kind == "file":
            browse = ttk.Button(
                button_frame, text="Browse...", width=10,
                command=lambda k=key: self._browse_file(k),
            )
            browse.pack(side="left")
            Tooltip(browse, "Open a file picker.")
        elif kind == "text" and key == "ref_date":
            auto = ttk.Button(
                button_frame, text="Auto-detect", width=12,
                command=self._auto_detect_ref_date,
            )
            auto.pack(side="left")
            Tooltip(
                auto,
                "Try to infer the reference date from the baseline directory "
                "by looking at which date is common to every sub-folder name.",
            )

        help_icon = ttk.Label(
            button_frame, text=" ? ", style="Help.TLabel", cursor="question_arrow"
        )
        help_icon.pack(side="left", padx=(6, 0))
        Tooltip(help_icon, field["help"])

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def _preload_settings(self) -> None:
        """Populate form with saved settings if present."""
        path = find_settings_file()
        if not path:
            return
        data = load_settings(path)
        if not data:
            return
        for key, var in self._entries.items():
            value = data.get(key)
            if value:
                var.set(str(value))
        self._log(f"Loaded settings from {path}")

    def _collect(self) -> dict[str, str | None]:
        """Read the form into a settings dict (empty strings become None)."""
        result: dict[str, str | None] = {}
        for key, var in self._entries.items():
            value = var.get().strip()
            result[key] = value if value else None
        return result

    def _load_settings_clicked(self) -> None:
        path = filedialog.askopenfilename(
            title="Load settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=SETTINGS_FILENAME,
        )
        if not path:
            return
        data = load_settings(path)
        if not data:
            messagebox.showwarning("Load settings", "Could not read settings from that file.")
            return
        for key, var in self._entries.items():
            var.set(str(data.get(key) or ""))
        self._log(f"Loaded settings from {path}")
        self.status_var.set(f"Loaded settings: {path}")

    def _save_settings_clicked(self) -> None:
        settings = self._collect()
        path = filedialog.asksaveasfilename(
            title="Save settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=SETTINGS_FILENAME,
        )
        if not path:
            return
        save_settings(settings, settings_path=path)
        self._log(f"Saved settings to {path}")
        self.status_var.set(f"Saved settings: {path}")

    # ------------------------------------------------------------------
    # Pickers / helpers
    # ------------------------------------------------------------------
    def _browse_dir(self, key: str, must_exist: bool) -> None:
        initial = self._entries[key].get().strip() or str(Path.cwd())
        if must_exist and not Path(initial).exists():
            initial = str(Path.cwd())
        path = filedialog.askdirectory(
            title=f"Select {key}", initialdir=initial, mustexist=must_exist
        )
        if path:
            self._entries[key].set(path)
            if key == "geometry_dir":
                self._autofill_geometry_files(path)

    def _autofill_geometry_files(self, geometry_dir: str) -> None:
        """Populate empty geometry / lookup file fields from a directory.

        Helps the user by filling in the DEM, incidence, azimuth and
        (critically) lookup Y / X paths when the selected geometry
        directory contains the expected ISCE2 topsStack file names.
        Fields that already have a value are left untouched so the user
        stays in control.
        """
        geom_dir = Path(geometry_dir)
        if not geom_dir.is_dir():
            return

        filled: list[str] = []
        for field_key, patterns in GEOMETRY_AUTOFILL.items():
            if self._entries.get(field_key) is None:
                continue
            if self._entries[field_key].get().strip():
                continue
            resolved = self._first_match(geom_dir, patterns)
            if resolved is not None:
                self._entries[field_key].set(str(resolved))
                filled.append(f"{field_key} -> {resolved.name}")

        if filled:
            self._log("Auto-filled from geometry directory:")
            for line in filled:
                self._log(f"  - {line}")

    @staticmethod
    def _first_match(directory: Path, patterns: tuple[str, ...]) -> Path | None:
        """Return the first path inside *directory* matching any pattern."""
        for pattern in patterns:
            exact = directory / pattern
            if exact.is_file():
                return exact
            matches = sorted(directory.glob(pattern))
            if matches:
                return matches[0]
        return None

    def _browse_file(self, key: str) -> None:
        initial = self._entries[key].get().strip() or str(Path.cwd())
        start_dir = initial if Path(initial).is_dir() else str(Path(initial).parent or Path.cwd())
        path = filedialog.askopenfilename(title=f"Select {key}", initialdir=start_dir)
        if path:
            self._entries[key].set(path)

    def _auto_detect_ref_date(self) -> None:
        baseline = self._entries["baseline_dir"].get().strip()
        if not baseline:
            messagebox.showinfo(
                "Auto-detect reference date",
                "Please select a baseline directory first.",
            )
            return
        detected = auto_detect_ref_date(baseline)
        if detected:
            self._entries["ref_date"].set(detected)
            self._log(f"Auto-detected reference date: {detected}")
            self.status_var.set(f"Auto-detected reference date: {detected}")
        else:
            messagebox.showwarning(
                "Auto-detect reference date",
                "Could not determine a reference date from the baseline directory.",
            )

    # ------------------------------------------------------------------
    # Validation + execution
    # ------------------------------------------------------------------
    def _validate(self, settings: dict) -> list[str]:
        errors: list[str] = []

        unw = settings.get("unw_dir")
        if not unw:
            errors.append("Unwrapped directory is required.")
        elif not Path(unw).is_dir():
            errors.append(f"Unwrapped directory does not exist: {unw}")

        for key in ("cor_dir", "baseline_dir", "geometry_dir"):
            value = settings.get(key)
            if value and not Path(value).is_dir():
                errors.append(f"{key} does not exist: {value}")

        ref_xml = settings.get("ref_xml")
        if ref_xml and not Path(ref_xml).is_file():
            errors.append(f"Reference XML file does not exist: {ref_xml}")

        for file_key in (
            "dem_file",
            "inc_angle_file",
            "az_angle_file",
            "lookup_y_file",
            "lookup_x_file",
            "water_mask_file",
        ):
            value = settings.get(file_key)
            if value and not Path(value).is_file():
                errors.append(f"{file_key} does not exist: {value}")

        processor = settings.get("mintpy_processor")
        if processor and processor not in ("isce", "hyp3"):
            errors.append(
                f"MintPy processor must be 'isce' or 'hyp3' (got {processor!r})."
            )

        ref_date = settings.get("ref_date")
        if ref_date and (len(ref_date) != 8 or not ref_date.isdigit()):
            errors.append("Reference date must be in YYYYMMDD format.")

        if not settings.get("work_dir"):
            errors.append("MintPy output directory is required.")

        mode = settings.get("geometry_mode")
        if mode and mode not in ("auto", "radar", "geo"):
            errors.append(f"Geometry mode must be auto, radar or geo (got {mode!r}).")

        return errors

    def _run_clicked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("Run", "A run is already in progress.")
            return

        settings = self._collect()
        errors = self._validate(settings)
        if errors:
            messagebox.showerror("Invalid inputs", "\n".join(f"- {e}" for e in errors))
            return

        unw_count = count_files(settings["unw_dir"], "*.unw.tif")
        if unw_count == 0:
            if not messagebox.askyesno(
                "No unwrapped files",
                "No *.unw.tif files were found in the selected directory. "
                "Run anyway?",
            ):
                return

        self._log(f"Found {unw_count} unwrapped files in {settings['unw_dir']}")
        self.run_btn.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_var.set("Running...")

        self._worker = threading.Thread(
            target=self._run_worker,
            args=(settings,),
            daemon=True,
        )
        self._worker.start()

    def _run_worker(self, settings: dict) -> None:
        """Background worker: runs prepare_stack + generate_mintpy_config."""
        try:
            def progress_cb(current: int, total: int) -> None:
                pct = (current / total * 100.0) if total else 0.0
                self._log_queue.put(f"__progress__:{pct:.1f}:{current}/{total}")

            self._log_queue.put("Generating .rsc sidecar files...")

            result = prepare_stack(
                unw_dir=settings["unw_dir"],
                cor_dir=settings.get("cor_dir"),
                conncomp_dir=settings["unw_dir"],
                geometry_dir=settings.get("geometry_dir"),
                baseline_dir=settings.get("baseline_dir"),
                ref_xml=settings.get("ref_xml"),
                ref_date=settings.get("ref_date"),
                progress_callback=progress_cb,
                geometry_mode=settings.get("geometry_mode") or "auto",
            )

            self._log_queue.put(
                f"Wrote {result['rsc_written']} .rsc files "
                f"({len(result.get('errors', []))} errors)."
            )
            for err in result.get("errors", [])[:5]:
                self._log_queue.put(f"  ! {err.get('file')}: {err.get('error')}")
            if len(result.get("errors", [])) > 5:
                self._log_queue.put(f"  ... and {len(result['errors']) - 5} more errors")

            self._log_queue.put("Generating MintPy configuration...")
            work_dir = settings.get("work_dir") or "./mintpy"
            config_path = generate_mintpy_config(
                work_dir=work_dir,
                unw_dir=settings["unw_dir"],
                cor_dir=settings.get("cor_dir"),
                conncomp_dir=settings["unw_dir"],
                dem_file=settings.get("dem_file"),
                inc_angle_file=settings.get("inc_angle_file"),
                az_angle_file=settings.get("az_angle_file"),
                lookup_y_file=settings.get("lookup_y_file"),
                lookup_x_file=settings.get("lookup_x_file"),
                water_mask_file=settings.get("water_mask_file"),
                processor=settings.get("mintpy_processor") or "isce",
            )
            self._log_queue.put(f"MintPy config written: {config_path}")
            for key in ("lookup_y_file", "lookup_x_file"):
                if not settings.get(key):
                    self._log_queue.put(
                        f"  WARNING: {key} not set -- MintPy may fail with "
                        "'No lookup table found' during geocoding."
                    )
            self._log_queue.put("__done__:ok")
        except Exception as exc:
            logger.exception("GUI run failed")
            self._log_queue.put(f"ERROR: {exc}")
            self._log_queue.put("__done__:error")

    # ------------------------------------------------------------------
    # Log pump (called on the Tk main loop)
    # ------------------------------------------------------------------
    def _drain_log_queue(self) -> None:
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg.startswith("__progress__:"):
                    _, pct, counts = msg.split(":", 2)
                    self.progress.configure(value=float(pct))
                    self.status_var.set(f"Running... {counts} ({float(pct):.1f}%)")
                elif msg == "__done__:ok":
                    self.progress.configure(value=100)
                    self.status_var.set("Done.")
                    self.run_btn.configure(state="normal")
                    messagebox.showinfo("Done", "All outputs generated successfully.")
                elif msg == "__done__:error":
                    self.status_var.set("Failed. See log for details.")
                    self.run_btn.configure(state="normal")
                    messagebox.showerror(
                        "Run failed",
                        "The run did not complete successfully. See the log for details.",
                    )
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        finally:
            self.after(120, self._drain_log_queue)

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")


# ========================================================================
# Entry point
# ========================================================================
def run_gui() -> None:
    """Launch the Dolphin2MintPy Tkinter GUI."""
    try:
        app = Dolphin2MintPyApp()
    except tk.TclError as exc:
        raise SystemExit(
            "Could not initialize the GUI. Is a display available and is "
            "python3-tk installed?\n"
            f"Original error: {exc}"
        ) from exc
    app.mainloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_gui()
