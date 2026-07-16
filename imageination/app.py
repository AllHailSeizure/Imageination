from __future__ import annotations

import json
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from imageination.core import (
    apply_color_map,
    apply_color_map_batch,
    build_cell_color_map,
    build_color_map,
    extract_hex_values,
    flatten_suggested_map,
    parse_manual_map,
)


IMAGE_TYPES = [
    ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff"),
    ("All files", "*.*"),
]


class ImageinationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Imageination")
        self.geometry("1120x760")
        self.minsize(940, 640)

        self.source_path: Path | None = None
        self.target_path: Path | None = None
        self.preview_image: ImageTk.PhotoImage | None = None
        self.last_output_path: Path | None = None

        self.status_var = tk.StringVar(value="Pick a source image to begin.")
        self.source_var = tk.StringVar(value="No source image selected")
        self.target_var = tk.StringVar(value="No comparison image selected")
        self.frame_width_var = tk.StringVar(value="16")
        self.frame_height_var = tk.StringVar(value="16")
        self.use_magick_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self, padding=8)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(1, weight=1)
        toolbar.columnconfigure(3, weight=1)

        ttk.Button(toolbar, text="Pick Source", command=self.pick_source).grid(row=0, column=0, padx=(0, 6))
        ttk.Label(toolbar, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Button(toolbar, text="Pick Comparison", command=self.pick_target).grid(row=0, column=2, padx=(0, 6))
        ttk.Label(toolbar, textvariable=self.target_var).grid(row=0, column=3, sticky="ew")

        panes = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        panes.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        left = ttk.Frame(panes, padding=8)
        middle = ttk.Frame(panes, padding=8)
        right = ttk.Frame(panes, padding=8)
        panes.add(left, weight=1)
        panes.add(middle, weight=2)
        panes.add(right, weight=1)

        self._build_color_panel(left)
        self._build_map_panel(middle)
        self._build_preview_panel(right)

        status = ttk.Label(self, textvariable=self.status_var, padding=(8, 0, 8, 8), anchor="w")
        status.grid(row=2, column=0, sticky="ew")

    def _build_color_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(3, weight=1)

        ttk.Label(parent, text="Source Hex Values").grid(row=0, column=0, sticky="w")
        self.source_colors = tk.Listbox(parent, height=12, exportselection=False)
        self.source_colors.grid(row=1, column=0, sticky="nsew", pady=(4, 12))
        self.source_colors.bind("<Double-Button-1>", lambda _event: self.insert_selected_source())

        ttk.Label(parent, text="Comparison Hex Values").grid(row=2, column=0, sticky="w")
        self.target_colors = tk.Listbox(parent, height=12, exportselection=False)
        self.target_colors.grid(row=3, column=0, sticky="nsew", pady=(4, 8))
        self.target_colors.bind("<Double-Button-1>", lambda _event: self.insert_selected_target())

        ttk.Label(parent, text="Future: layering, frame batch tools, nudging").grid(row=4, column=0, sticky="w")

    def _build_map_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew")
        for index in range(7):
            controls.columnconfigure(index, weight=0)
        controls.columnconfigure(6, weight=1)

        ttk.Button(controls, text="Compare Pixels", command=self.compare_pixels).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(controls, text="Compare Cells", command=self.compare_cells).grid(row=0, column=1, padx=(0, 10))
        ttk.Label(controls, text="Frame").grid(row=0, column=2, padx=(0, 4))
        ttk.Entry(controls, textvariable=self.frame_width_var, width=6).grid(row=0, column=3)
        ttk.Label(controls, text="x").grid(row=0, column=4, padx=2)
        ttk.Entry(controls, textvariable=self.frame_height_var, width=6).grid(row=0, column=5, padx=(0, 12))
        ttk.Button(controls, text="Apply Manual Text", command=self.apply_manual_text).grid(row=0, column=6, sticky="w")

        columns = ("source", "target", "count")
        self.map_tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
        self.map_tree.heading("source", text="Source")
        self.map_tree.heading("target", text="Target")
        self.map_tree.heading("count", text="Count")
        self.map_tree.column("source", width=120, anchor="center")
        self.map_tree.column("target", width=120, anchor="center")
        self.map_tree.column("count", width=80, anchor="center")
        self.map_tree.grid(row=1, column=0, sticky="ew", pady=(8, 8))

        edit = ttk.Frame(parent)
        edit.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        edit.columnconfigure(0, weight=1)
        edit.columnconfigure(1, weight=1)
        self.edit_source = ttk.Entry(edit)
        self.edit_target = ttk.Entry(edit)
        self.edit_source.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.edit_target.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(edit, text="Add/Update", command=self.add_mapping).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(edit, text="Remove", command=self.remove_mapping).grid(row=0, column=3)
        self.map_tree.bind("<<TreeviewSelect>>", self.load_selected_mapping)

        self.manual_text = tk.Text(parent, height=8, wrap="none", undo=True)
        self.manual_text.grid(row=3, column=0, sticky="nsew")
        self.manual_text.insert("1.0", "#FF0000 -> #00FF00\n#0000FF, #111111")

        actions = ttk.Frame(parent)
        actions.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Load Map", command=self.load_map).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="Save Map", command=self.save_map).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Checkbutton(actions, text="Use ImageMagick on export", variable=self.use_magick_var).pack(side=tk.LEFT)
        ttk.Button(actions, text="Preview", command=self.preview_transform).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(actions, text="Export", command=self.export_transform).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Batch Folder", command=self.batch_transform).pack(side=tk.RIGHT, padx=(0, 6))

    def _build_preview_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Preview").grid(row=0, column=0, sticky="w")
        self.preview_label = ttk.Label(parent, anchor="center")
        self.preview_label.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        ttk.Label(parent, text="Double-click colors to stage manual map entries.").grid(row=2, column=0, sticky="w")

    def pick_source(self):
        path = filedialog.askopenfilename(title="Pick source image", filetypes=IMAGE_TYPES)
        if path:
            self.source_path = Path(path)
            self.source_var.set(str(self.source_path))
            self.load_hex_values(self.source_path, self.source_colors)
            self.show_image_preview(self.source_path)
            self.status_var.set(f"Loaded source: {self.source_path.name}")

    def pick_target(self):
        path = filedialog.askopenfilename(title="Pick comparison image", filetypes=IMAGE_TYPES)
        if path:
            self.target_path = Path(path)
            self.target_var.set(str(self.target_path))
            self.load_hex_values(self.target_path, self.target_colors)
            self.status_var.set(f"Loaded comparison: {self.target_path.name}")

    def load_hex_values(self, path: Path, listbox: tk.Listbox):
        listbox.delete(0, tk.END)
        for color in extract_hex_values(path):
            listbox.insert(tk.END, color)

    def compare_pixels(self):
        if not self.require_two_images():
            return
        suggested = build_color_map(self.source_path, self.target_path)
        self.replace_tree(flatten_suggested_map(suggested), suggested)
        self.status_var.set(f"Mapped {len(suggested)} colors by aligned pixels.")

    def compare_cells(self):
        if not self.require_two_images():
            return
        try:
            frame_width = int(self.frame_width_var.get())
            frame_height = int(self.frame_height_var.get())
            suggested = build_cell_color_map(self.source_path, self.target_path, frame_width, frame_height)
        except ValueError as exc:
            messagebox.showerror("Invalid frame size", str(exc))
            return
        self.replace_tree(flatten_suggested_map(suggested), suggested)
        self.status_var.set(f"Mapped {len(suggested)} colors by {frame_width}x{frame_height} cells.")

    def apply_manual_text(self):
        try:
            mappings = parse_manual_map(self.manual_text.get("1.0", tk.END))
        except ValueError as exc:
            messagebox.showerror("Invalid manual map", str(exc))
            return
        self.replace_tree(mappings)
        self.status_var.set(f"Loaded {len(mappings)} manual mappings.")

    def add_mapping(self):
        source = self.edit_source.get().strip()
        target = self.edit_target.get().strip()
        try:
            mapping = parse_manual_map(f"{source} {target}")
        except ValueError as exc:
            messagebox.showerror("Invalid mapping", str(exc))
            return
        current = self.current_map()
        current.update(mapping)
        self.replace_tree(current)

    def remove_mapping(self):
        selected = self.map_tree.selection()
        if not selected:
            return
        for item in selected:
            self.map_tree.delete(item)

    def load_selected_mapping(self, _event=None):
        selected = self.map_tree.selection()
        if not selected:
            return
        values = self.map_tree.item(selected[0], "values")
        self.edit_source.delete(0, tk.END)
        self.edit_target.delete(0, tk.END)
        self.edit_source.insert(0, values[0])
        self.edit_target.insert(0, values[1])

    def insert_selected_source(self):
        self._insert_selected_color(self.source_colors, self.edit_source)

    def insert_selected_target(self):
        self._insert_selected_color(self.target_colors, self.edit_target)

    def _insert_selected_color(self, listbox: tk.Listbox, entry: ttk.Entry):
        selection = listbox.curselection()
        if not selection:
            return
        entry.delete(0, tk.END)
        entry.insert(0, listbox.get(selection[0]))

    def replace_tree(self, mappings: dict[str, str], suggested: dict[str, dict[str, int | str]] | None = None):
        for item in self.map_tree.get_children():
            self.map_tree.delete(item)
        for source, target in sorted(mappings.items()):
            count = ""
            if suggested and source in suggested:
                count = suggested[source].get("count", "")
            self.map_tree.insert("", tk.END, values=(source, target, count))

    def current_map(self) -> dict[str, str]:
        mappings = {}
        for item in self.map_tree.get_children():
            source, target, _count = self.map_tree.item(item, "values")
            mappings[source] = target
        return mappings

    def preview_transform(self):
        if not self.require_source_and_map():
            return
        preview_path = Path(tempfile.gettempdir()) / "imageination_preview.png"
        apply_color_map(self.source_path, preview_path, self.current_map(), use_imagemagick=False)
        self.show_image_preview(preview_path)
        self.last_output_path = preview_path
        self.status_var.set("Preview updated.")

    def export_transform(self):
        if not self.require_source_and_map():
            return
        default_name = f"{self.source_path.stem}_imageinated{self.source_path.suffix}"
        path = filedialog.asksaveasfilename(
            title="Export transformed image",
            initialfile=default_name,
            defaultextension=self.source_path.suffix,
            filetypes=IMAGE_TYPES,
        )
        if not path:
            return
        output_path = apply_color_map(
            self.source_path,
            path,
            self.current_map(),
            use_imagemagick=self.use_magick_var.get(),
        )
        self.show_image_preview(output_path)
        self.last_output_path = output_path
        self.status_var.set(f"Exported: {output_path}")

    def batch_transform(self):
        if not self.current_map():
            messagebox.showinfo("Map needed", "Create or enter at least one transform mapping first.")
            return
        input_dir = filedialog.askdirectory(title="Pick folder of images to transform")
        if not input_dir:
            return
        output_dir = filedialog.askdirectory(title="Pick output folder")
        if not output_dir:
            return
        outputs = apply_color_map_batch(
            input_dir,
            output_dir,
            self.current_map(),
            use_imagemagick=self.use_magick_var.get(),
        )
        if outputs:
            self.show_image_preview(outputs[0])
        self.status_var.set(f"Batch exported {len(outputs)} image(s) to {output_dir}.")

    def load_map(self):
        path = filedialog.askopenfilename(title="Load transform map", filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
        mappings = payload.get("mappings", payload)
        self.replace_tree({str(source): str(target) for source, target in mappings.items()})
        self.status_var.set(f"Loaded map: {path}")

    def save_map(self):
        path = filedialog.asksaveasfilename(
            title="Save transform map",
            initialfile="imageination-map.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        payload = {"mappings": self.current_map()}
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        self.status_var.set(f"Saved map: {path}")

    def show_image_preview(self, path: Path):
        with Image.open(path).convert("RGBA") as image:
            image.thumbnail((320, 320))
            self.preview_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_image)

    def require_two_images(self) -> bool:
        if not self.source_path or not self.target_path:
            messagebox.showinfo("Images needed", "Pick both a source image and a comparison image first.")
            return False
        return True

    def require_source_and_map(self) -> bool:
        if not self.source_path:
            messagebox.showinfo("Source needed", "Pick a source image first.")
            return False
        if not self.current_map():
            messagebox.showinfo("Map needed", "Create or enter at least one transform mapping first.")
            return False
        return True


def main():
    app = ImageinationApp()
    app.mainloop()


if __name__ == "__main__":
    main()
